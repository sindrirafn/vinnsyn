"""Collect the complete current Alfreð inventory through the public web UI.

This intentionally uses the rendered jobs page and its infinite-scroll behavior.
It does not call Alfreð's disallowed ``/api`` routes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ALFRED_JOBS_URL = "https://www.alfred.is/jobs"
DISPLAYED_COUNT_RE = re.compile(r"(?:Öll störf|All jobs)\s*\(\s*(\d+)\s*\)", re.IGNORECASE)


def collect_cards(*, headless: bool, max_rounds: int = 80) -> tuple[list[dict[str, str]], int | None]:
    """Render and exhaust the public infinite-scroll listing page."""

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Browser collection requires Playwright. Install dependencies with "
            "'python -m pip install -r requirements.txt' and then "
            "'python -m playwright install chromium'."
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(ALFRED_JOBS_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_selector('a[href*="/starf/"]', timeout=60_000)

        previous_unique_count = 0
        stable_rounds = 0
        for _ in range(max_rounds):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            cards = _read_cards(page)
            unique_count = len({card["href"] for card in cards})
            if unique_count == previous_unique_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                previous_unique_count = unique_count

            displayed_count = _displayed_count(page)
            if displayed_count is not None and unique_count >= displayed_count:
                break
            if stable_rounds >= 5:
                break

        cards = _read_cards(page)
        final_displayed_count = _displayed_count(page)
        browser.close()

    deduplicated: dict[str, dict[str, str]] = {}
    for card in cards:
        href = card.get("href", "")
        if href and href not in deduplicated:
            deduplicated[href] = card
    return list(deduplicated.values()), final_displayed_count


def _read_cards(page) -> list[dict[str, str]]:
    return page.locator('a[href*="/starf/"]').evaluate_all(
        """els => els.map(el => ({
            href: el.getAttribute('href') || '',
            text: el.innerText || ''
        }))"""
    )


def _displayed_count(page) -> int | None:
    match = DISPLAYED_COUNT_RE.search(page.locator("body").inner_text())
    return int(match.group(1)) if match else None


def save_snapshot(path: Path, cards: list[dict[str, str]], displayed_count: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "alfred",
        "source_url": ALFRED_JOBS_URL,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "displayed_count": displayed_count,
        "cards": cards,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data/market/alfred-current.json"),
        help="Where to save the raw browser snapshot.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser while collecting.",
    )
    args = parser.parse_args()

    cards, displayed_count = collect_cards(headless=not args.headed)
    save_snapshot(args.snapshot, cards, displayed_count)
    print(
        f"Saved {len(cards)} unique Alfreð cards to {args.snapshot} "
        f"(page reported {displayed_count or 'unknown'})"
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
