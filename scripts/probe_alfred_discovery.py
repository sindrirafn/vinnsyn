"""Quickly probe non-Common-Crawl sources for historical Alfreð URLs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from vinnsyn.urls import canonicalize_url


USER_AGENT = "vinnsyn-alfred-discovery-probe/0.1"
LISTING_RE = re.compile(r"https?://(?:www\.)?alfred\.is/(?:starf|job|jobs|atvinna)/[^\s\"'<>#]+", re.I)
LISTING_PATH_RE = re.compile(r"^/(?:starf|job|jobs|atvinna)/[^/]+", re.I)


def get(url: str, timeout: int = 20) -> tuple[bytes, str | None]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with urlopen(request, timeout=timeout) as response:
            return response.read(), None
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return b"", f"{type(error).__name__}: {error}"


def extract_listing_urls(text: str) -> set[str]:
    urls = set()
    for match in LISTING_RE.findall(text):
        urls.add(canonicalize_url(match.rstrip(".,;:)")))
    return urls


def is_listing_candidate(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.netloc.lower().removeprefix("www.") == "alfred.is" and bool(LISTING_PATH_RE.match(parsed.path))


def probe_live_metadata() -> tuple[set[str], list[str]]:
    urls: set[str] = set()
    errors: list[str] = []
    candidates = [
        "https://alfred.is/robots.txt",
        "https://alfred.is/sitemap.xml",
        "https://alfred.is/sitemap_index.xml",
        "https://www.alfred.is/sitemap.xml",
    ]
    for candidate in candidates:
        print(f"Checking {candidate}...", flush=True)
        body, error = get(candidate)
        if error:
            errors.append(f"{candidate}: {error}")
            continue
        text = body.decode("utf-8", "replace")
        urls.update(extract_listing_urls(text))
        # Sitemap indexes point to additional XML files. Fetch those too.
        try:
            root = ElementTree.fromstring(body)
            for loc in root.iter():
                if loc.tag.lower().endswith("loc") and loc.text and "alfred.is" in loc.text:
                    child = loc.text.strip()
                    if child.startswith("http") and child != candidate:
                        child_body, child_error = get(child)
                        if child_error:
                            errors.append(f"{child}: {child_error}")
                        else:
                            urls.update(extract_listing_urls(child_body.decode("utf-8", "replace")))
        except ElementTree.ParseError:
            pass
    return urls, errors


def probe_wayback(patterns: list[str]) -> tuple[set[str], list[str]]:
    urls: set[str] = set()
    errors: list[str] = []
    for pattern in patterns:
        query = urlencode({
            "url": pattern,
            "output": "json",
            "fl": "original,timestamp,statuscode,mimetype",
            "filter": "statuscode:200",
            "collapse": "urlkey",
            "limit": "100000",
        })
        endpoint = f"https://web.archive.org/cdx/search/cdx?{query}"
        print(f"Checking Internet Archive: {pattern}...", flush=True)
        body, error = get(endpoint, timeout=20)
        if error:
            errors.append(f"{pattern}: {error}")
            continue
        try:
            payload = json.loads(body.decode("utf-8", "replace"))
            for row in payload[1:]:
                if row and row[0]:
                    candidate = canonicalize_url(str(row[0]))
                    if is_listing_candidate(candidate):
                        urls.add(candidate)
        except (json.JSONDecodeError, IndexError, TypeError) as error:
            errors.append(f"{pattern}: invalid CDX response: {error}")
    return urls, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    # Broad host queries are faster and catch old route names as well as the
    # modern /starf/ route. Narrow route probes can be added later if needed.
    patterns = ["alfred.is/*", "www.alfred.is/*"]
    live_urls, live_errors = probe_live_metadata()
    wayback_urls, wayback_errors = probe_wayback(patterns)
    all_urls = sorted(live_urls | wayback_urls)
    report = {
        "sources": {
            "alfred_public_metadata": sorted(live_urls),
            "internet_archive_cdx": sorted(wayback_urls),
        },
        "errors": live_errors + wayback_errors,
        "unique_listing_urls": all_urls,
    }
    print(f"Alfred metadata/sitemap URLs: {len(live_urls)}")
    print(f"Internet Archive likely listing URLs: {len(wayback_urls)}")
    print(f"Combined unique listing URLs: {len(all_urls)}")
    if report["errors"]:
        print(f"Source errors: {len(report['errors'])}", file=sys.stderr)
        for error in report["errors"]:
            print(f"  {error}", file=sys.stderr)
    for url in all_urls[:25]:
        print(f"  {url}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"Wrote report: {args.output}")


if __name__ == "__main__":
    main()
