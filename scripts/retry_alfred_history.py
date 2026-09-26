"""Patient, resumable Common Crawl worker for historical Alfreð pages.

The worker is intentionally conservative with the archive service. It keeps
retry state in PostgreSQL, respects retryable HTTP failures with exponential
backoff, and tries older captures for a URL when a newer capture is unusable.
Run it repeatedly; completed and permanently rejected rows are skipped.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psycopg.rows import dict_row

# Support direct execution from the repository root without requiring a
# packaging-only `scripts` module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vinnsyn.db import connect, transaction
from vinnsyn.market_ingestion import MarketListingInput, ingest_market_listings
from scripts.fetch_alfred_history import PARSER_VERSION, extract_listing, metadata_snapshot


USER_AGENT = "vinnsyn-historical-retry/0.1"
RETRYABLE_STATUS_CODES = {403, 408, 425, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 6
MAX_BACKOFF_HOURS = 48
NUMERIC_URL_PATTERN = "'/starf/[0-9]+/?([?#].*)?$'"


def queue_filter(skip_numeric_urls: bool, alias: str = "") -> str:
    """Use the same URL selection for loading, resetting, and retry waits."""
    prefix = f"{alias}." if alias else ""
    return f"and not ({prefix}canonical_url ~ {NUMERIC_URL_PATTERN})" if skip_numeric_urls else ""


def unfinished_filter(alias: str) -> str:
    return f"""and not exists (
        select 1 from market_historical_discoveries completed
        where completed.source_key = {alias}.source_key
          and completed.canonical_url = {alias}.canonical_url
          and completed.discovery_status = 'imported'
    )"""


@dataclass(frozen=True, slots=True)
class ArchiveCapture:
    record: str
    compressed_record: bytes
    status: int | None
    retry_after: str | None


def retry_delay(attempt: int, retry_after: str | None = None) -> timedelta:
    if retry_after and retry_after.isdigit():
        return timedelta(seconds=min(int(retry_after), MAX_BACKOFF_HOURS * 3600))
    seconds = min(900 * (2 ** max(attempt - 1, 0)), MAX_BACKOFF_HOURS * 3600)
    return timedelta(seconds=seconds)


class RequestPacer:
    """Keep a minimum gap between archive requests, including fallback captures."""

    def __init__(self, interval: float) -> None:
        self.interval = max(interval, 0.0)
        self.last_request_at: float | None = None

    def wait(self) -> None:
        if self.last_request_at is not None:
            remaining = self.interval - (time.monotonic() - self.last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request_at = time.monotonic()


def fetch_record(row: dict[str, object]) -> ArchiveCapture:
    start = int(row["warc_offset"])
    length = int(row["warc_length"])
    request = Request(
        f"https://data.commoncrawl.org/{row['warc_filename']}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "identity",
            "Range": f"bytes={start}-{start + length - 1}",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = response.read()
            status = getattr(response, "status", None)
            retry_after = response.headers.get("Retry-After")
    except HTTPError as error:
        if error.code in RETRYABLE_STATUS_CODES:
            return ArchiveCapture("", b"", error.code, error.headers.get("Retry-After"))
        raise
    except (TimeoutError, URLError, ConnectionError) as error:
        raise TimeoutError(str(error)) from error
    try:
        record = gzip.decompress(payload).decode("utf-8", errors="replace")
    except (OSError, EOFError) as error:
        raise ValueError(f"Invalid compressed WARC payload: {error}") from error
    return ArchiveCapture(record, payload, status, retry_after)


def fetch_live_record(row: dict[str, object]) -> ArchiveCapture:
    """Fetch the actual Alfreð URL; Common Crawl is only the fallback."""
    request = Request(
        str(row["url"]),
        headers={
            "User-Agent": "vinnsyn-alfred-live/0.1",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            status = getattr(response, "status", None)
            retry_after = response.headers.get("Retry-After")
            compressed = gzip.compress(payload, compresslevel=6)
            return ArchiveCapture(
                payload.decode("utf-8", errors="replace"), compressed, status, retry_after
            )
    except HTTPError as error:
        return ArchiveCapture("", b"", error.code, error.headers.get("Retry-After"))
    except (TimeoutError, URLError, ConnectionError, OSError) as error:
        raise TimeoutError(str(error)) from error


def store_capture_document(row: dict[str, object], capture: ArchiveCapture) -> None:
    """Persist the exact compressed archive response before parsing it."""
    if not capture.compressed_record:
        return
    raw_hash = hashlib.sha256(capture.compressed_record).hexdigest()
    metadata = metadata_snapshot(row, capture.record)
    content_type_match = re.search(r"(?im)^content-type:\s*([^;\r\n]+)", capture.record)
    with transaction():
        with connect() as conn:
            conn.execute(
                """
                insert into market_historical_capture_documents (
                    discovery_id, archive_index, crawl_timestamp, content_digest,
                    raw_record_gzip, raw_record_sha256, record_bytes, http_status,
                    content_type, metadata_snapshot, parser_version
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                )
                on conflict (discovery_id) do update set
                    raw_record_gzip = excluded.raw_record_gzip,
                    raw_record_sha256 = excluded.raw_record_sha256,
                    record_bytes = excluded.record_bytes,
                    http_status = excluded.http_status,
                    content_type = excluded.content_type,
                    metadata_snapshot = excluded.metadata_snapshot,
                    parser_version = excluded.parser_version,
                    fetched_at = now()
                """,
                (
                    row["id"], row["archive_index"], row["crawl_timestamp"],
                    row.get("content_digest"), capture.compressed_record, raw_hash,
                    len(capture.compressed_record), capture.status,
                    content_type_match.group(1).strip() if content_type_match else None,
                    json.dumps(metadata, ensure_ascii=False), PARSER_VERSION,
                ),
            )


def store_live_document(row: dict[str, object], capture: ArchiveCapture) -> None:
    """Preserve the direct Alfreð response without replacing archive evidence."""
    if not capture.compressed_record:
        return
    raw_hash = hashlib.sha256(capture.compressed_record).hexdigest()
    metadata = metadata_snapshot(row, capture.record)
    content_type_match = re.search(r"(?im)^content-type:\s*([^;\r\n]+)", capture.record)
    with transaction():
        with connect() as conn:
            conn.execute(
                """
                insert into market_historical_live_documents (
                    discovery_id, listing_url, raw_html_gzip, raw_html_sha256,
                    response_bytes, http_status, content_type,
                    metadata_snapshot, parser_version
                ) values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (discovery_id) do update set
                    listing_url = excluded.listing_url,
                    raw_html_gzip = excluded.raw_html_gzip,
                    raw_html_sha256 = excluded.raw_html_sha256,
                    response_bytes = excluded.response_bytes,
                    http_status = excluded.http_status,
                    content_type = excluded.content_type,
                    metadata_snapshot = excluded.metadata_snapshot,
                    parser_version = excluded.parser_version,
                    fetched_at = now()
                """,
                (
                    row["id"], row["url"], capture.compressed_record, raw_hash,
                    len(capture.compressed_record), capture.status,
                    content_type_match.group(1).strip() if content_type_match else "text/html",
                    json.dumps(metadata, ensure_ascii=False), PARSER_VERSION,
                ),
            )


def load_capture_groups(limit: int | None, skip_numeric_urls: bool = False) -> list[list[dict[str, object]]]:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select *
                from (
                    select distinct on (canonical_url)
                           canonical_url
                    from market_historical_discoveries
                    where discovery_status = 'discovered'
                      and (next_retry_at is null or next_retry_at <= now())
                      {queue_filter(skip_numeric_urls)}
                      {unfinished_filter('market_historical_discoveries')}
                    order by canonical_url, attempt_count, crawl_timestamp desc
                ) queued
                join lateral (
                    select d.*
                    from market_historical_discoveries d
                    where d.canonical_url = queued.canonical_url
                      and d.discovery_status = 'discovered'
                      and (d.next_retry_at is null or d.next_retry_at <= now())
                      {queue_filter(skip_numeric_urls, 'd')}
                    order by d.attempt_count, d.crawl_timestamp desc
                ) captures on true
                order by queued.canonical_url, captures.attempt_count,
                         captures.crawl_timestamp desc
                """
            )
            rows = cur.fetchall()
    groups: list[list[dict[str, object]]] = []
    by_url: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_url.setdefault(str(row["canonical_url"]), []).append(row)
    for captures in by_url.values():
        groups.append(captures)
    return groups[:limit] if limit else groups


def mark_retry(
    row_id: int,
    message: str,
    status: int | None,
    retry_after: str | None,
    current_attempt: int,
) -> None:
    next_attempt = current_attempt + 1
    delay = retry_delay(next_attempt, retry_after)
    with transaction():
        with connect() as conn:
            if next_attempt >= MAX_ATTEMPTS:
                conn.execute(
                    """
                    update market_historical_discoveries
                    set discovery_status = 'failed', fetched_at = now(),
                        attempt_count = %s, last_attempt_at = now(),
                        last_http_status = %s, next_retry_at = null,
                        fetch_error = %s
                    where id = %s
                    """,
                    (next_attempt, status, f"Retry budget exhausted: {message}"[:1000], row_id),
                )
            else:
                conn.execute(
                    """
                    update market_historical_discoveries
                    set attempt_count = %s, last_attempt_at = now(),
                        last_http_status = %s,
                        next_retry_at = now() + %s::interval,
                        fetch_error = %s
                    where id = %s
                    """,
                    (next_attempt, status, str(delay), message[:1000], row_id),
                )


def mark_permanent(row_id: int, message: str, status: int | None = None) -> None:
    with transaction():
        with connect() as conn:
            conn.execute(
                """
                update market_historical_discoveries
                set discovery_status = 'failed', fetched_at = now(),
                    last_attempt_at = now(), last_http_status = %s,
                    fetch_error = %s
                where id = %s
                """,
                (status, message[:1000], row_id),
            )


def mark_group_complete(row_ids: list[int], imported_id: int) -> None:
    if not row_ids:
        return
    with transaction():
        with connect() as conn:
            conn.execute(
                """
                update market_historical_discoveries
                set discovery_status = case when id = %s then 'imported' else 'fetched' end,
                    fetched_at = now(),
                    last_attempt_at = now(), next_retry_at = null,
                    fetch_error = null
                where id = any(%s)
                """,
                (imported_id, row_ids),
            )


def seconds_until_next_retry(skip_numeric_urls: bool = False) -> float | None:
    with connect() as conn:
        row = conn.execute(
            f"""
            select extract(epoch from (min(next_retry_at) - now()))
            from market_historical_discoveries
            where discovery_status = 'discovered'
              and next_retry_at > now()
              {queue_filter(skip_numeric_urls)}
              {unfinished_filter('market_historical_discoveries')}
            """
        ).fetchone()
    if not row or row[0] is None:
        return None
    return max(float(row[0]), 0.0)


def reset_retryable(include_parse_failures: bool = False, skip_numeric_urls: bool = False, all_failed: bool = False) -> int:
    parse_clause = """or fetch_error ilike 'Archived page did not expose reliable title/company.%%'
                       or fetch_error = 'Direct Alfred response was not a verified listing: HTTP 200'""" if include_parse_failures else ""
    retry_clause = "" if all_failed else f"""and (last_http_status = any(%s)
                       or fetch_error ilike '%%timeout%%'
                       or fetch_error ilike '%%connection reset%%'
                       or fetch_error ilike 'HTTP Error 403%%'
                       or fetch_error ilike 'HTTP Error 408%%'
                       or fetch_error ilike 'HTTP Error 425%%'
                       or fetch_error ilike 'HTTP Error 429%%'
                       or fetch_error ilike 'HTTP Error 5%%'
                       {parse_clause})"""
    with transaction():
        with connect() as conn:
            cur = conn.execute(
                f"""
                update market_historical_discoveries
                set discovery_status = 'discovered', next_retry_at = now(),
                    fetch_error = null, attempt_count = 0,
                    last_attempt_at = null, last_http_status = null
                where discovery_status = 'failed'
                  {queue_filter(skip_numeric_urls)}
                  {unfinished_filter('market_historical_discoveries')}
                  {retry_clause}
                """,
                () if all_failed else (list(RETRYABLE_STATUS_CODES),),
            )
            return cur.rowcount


def process_group(
    captures: list[dict[str, object]],
    pacer: RequestPacer,
    verbose: bool = False,
) -> tuple[MarketListingInput | None, dict[str, object] | None]:
    # The URL itself is the source of truth. Common Crawl captures are used
    # only when the old Alfreð URL is no longer usable.
    live_row = dict(captures[0])
    live_row["retrieval_method"] = "direct_alfred"
    live_row["archive_index"] = "direct_alfred"
    live_row["crawl_timestamp"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    direct_status: int | None = None
    direct_error: str | None = None
    direct_retry_after: str | None = None
    try:
        if verbose:
            print(f"  direct Alfreð fetch {live_row['url']}", flush=True)
        pacer.wait()
        live_capture = fetch_live_record(live_row)
        direct_status = live_capture.status
        direct_retry_after = live_capture.retry_after
        if live_capture.status and 200 <= live_capture.status < 300:
            # Preserve the response even when this parser cannot verify it.
            # A later parser can recover the listing without losing the page.
            store_live_document(live_row, live_capture)
            live_listing = extract_listing(live_row, live_capture.record)
            if live_listing:
                if verbose:
                    print("    verified live Alfreð listing", flush=True)
                return live_listing, live_row
            if verbose:
                print("    live URL returned a page without reliable listing metadata; trying archive", flush=True)
        elif verbose:
            print(f"    live URL returned HTTP {live_capture.status}; trying archive", flush=True)
    except (TimeoutError, OSError, ValueError) as error:
        direct_error = str(error)
        if verbose:
            print(f"    live fetch unavailable: {error}; trying archive", flush=True)

    archive_captures = [
        row for row in captures
        if row.get("warc_filename") and row.get("warc_offset") is not None and row.get("warc_length") is not None
    ]
    if not archive_captures:
        # Internet Archive discovery gives us URLs, not WARC byte ranges. If
        # Alfred is temporarily unavailable, keep the row retryable; if Alfred
        # answered definitively, classify it without attempting archive I/O.
        if direct_error or direct_status in RETRYABLE_STATUS_CODES:
            mark_retry(
                int(captures[0]["id"]),
                direct_error or f"Retryable direct Alfred response: HTTP {direct_status}",
                direct_status,
                direct_retry_after,
                int(captures[0]["attempt_count"]),
            )
        else:
            mark_permanent(
                int(captures[0]["id"]),
                f"Direct Alfred response was not a verified listing: HTTP {direct_status}",
                direct_status,
            )
        return None, None

    for row in archive_captures:
        try:
            if verbose:
                print(
                    f"  fetch {row['canonical_url']} "
                    f"(crawl={row['crawl_timestamp']}, attempt={int(row['attempt_count']) + 1})",
                    flush=True,
                )
            pacer.wait()
            capture = fetch_record(row)
            status = capture.status
            retry_after = capture.retry_after
            if status in RETRYABLE_STATUS_CODES:
                if verbose:
                    print(f"    retryable archive response: HTTP {status}", flush=True)
                mark_retry(
                    int(row["id"]),
                    f"Retryable archive response: HTTP {status}",
                    status,
                    retry_after,
                    int(row["attempt_count"]),
                )
                continue
            store_capture_document(row, capture)
            listing = extract_listing(row, capture.record)
            if listing:
                if verbose:
                    print("    verified listing", flush=True)
                return listing, row
            if verbose:
                print("    no reliable listing metadata; trying next capture", flush=True)
            mark_permanent(int(row["id"]), "Archived page did not expose reliable title/company.", status)
        except HTTPError as error:
            if error.code in RETRYABLE_STATUS_CODES:
                if verbose:
                    print(f"    retryable HTTP error: {error.code}", flush=True)
                mark_retry(
                    int(row["id"]),
                    f"Retryable archive response: HTTP {error.code}",
                    error.code,
                    error.headers.get("Retry-After"),
                    int(row["attempt_count"]),
                )
            else:
                if verbose:
                    print(f"    permanent HTTP error: {error.code}", flush=True)
                mark_permanent(int(row["id"]), str(error), error.code)
        except (TimeoutError, OSError, ValueError) as error:
            if verbose:
                print(f"    transient fetch error: {error}", flush=True)
            mark_retry(int(row["id"]), str(error), None, None, int(row["attempt_count"]))
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Maximum URL groups to process this run.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between archive requests (default: 2).")
    parser.add_argument("--reset-retryable", action="store_true", help="Requeue prior 403/429/5xx/timeouts immediately.")
    parser.add_argument("--reset-parse-failures", action="store_true", help="Requeue live HTTP 200 and archived pages rejected for missing title/company metadata, plus transient failures.")
    parser.add_argument("--reset-failed", action="store_true", help="Requeue all previously failed URL groups once, including 404 and unverified pages.")
    parser.add_argument("--skip-numeric-urls", action="store_true", help="Exclude Alfreð /starf/<digits> URLs from this run without changing their stored status.")
    parser.add_argument("--run-until-empty", action="store_true", help="Keep running until no retryable queue rows remain due.")
    parser.add_argument("--verbose", action="store_true", help="Print each capture attempt and its outcome.")
    args = parser.parse_args()
    if args.interval < 0:
        parser.error("--interval must be non-negative")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.reset_retryable or args.reset_parse_failures or args.reset_failed:
        print(f"Requeued {reset_retryable(args.reset_parse_failures, args.skip_numeric_urls, args.reset_failed)} failures.")

    pacer = RequestPacer(args.interval)
    while True:
        groups = load_capture_groups(args.limit, args.skip_numeric_urls)
        if not groups:
            wait_seconds = seconds_until_next_retry(args.skip_numeric_urls) if args.run_until_empty else None
            if wait_seconds is not None:
                wait_seconds = min(max(wait_seconds, 1.0), 900.0)
                print(f"No due rows; waiting {wait_seconds:.0f}s for the next retry window.")
                time.sleep(wait_seconds)
                continue
            print("Retry queue is empty for now.")
            break
        print(f"Processing {len(groups)} URL groups at one request every {args.interval:g}s.")
        successes: list[tuple[MarketListingInput, dict[str, object]]] = []
        processed = 0
        imported = 0

        def save_successes(batch: list[tuple[MarketListingInput, dict[str, object]]]) -> None:
            if not batch:
                return
            ingest_market_listings(
                [listing for listing, _ in batch],
                discovery_method="common_crawl_historical_retry_fetch",
                expected_count=len(batch),
                complete_scan=False,
            )
            for _, row in batch:
                group_ids = [
                    int(candidate["id"])
                    for group in groups
                    for candidate in group
                    if candidate["canonical_url"] == row["canonical_url"]
                ]
                mark_group_complete(group_ids, int(row["id"]))

        for index, group in enumerate(groups, start=1):
            print(
                f"[{index}/{len(groups)}] {group[0]['canonical_url']}",
                flush=True,
            )
            listing, row = process_group(group, pacer, verbose=args.verbose)
            processed += 1
            if listing and row:
                successes.append((listing, row))
                imported += 1
            if successes and len(successes) >= 50:
                save_successes(successes)
                print(f"  imported {len(successes)} verified listings after {index} URL groups")
                successes.clear()
            elif index % 25 == 0:
                print(f"  progress: {index}/{len(groups)} groups processed, {imported} verified this pass", flush=True)
        if successes:
            save_successes(successes)
            print(f"  imported {len(successes)} verified listings")
        print(f"Pass summary: {processed} groups processed, {imported} verified listings.")
        if not args.run_until_empty:
            break
        if args.limit is not None and len(groups) >= args.limit:
            # A capped pass may leave other ready groups; fetch those before
            # sleeping for a future retry window.
            continue
        wait_seconds = seconds_until_next_retry(args.skip_numeric_urls)
        if wait_seconds is not None:
            wait_seconds = min(max(wait_seconds, 1.0), 900.0)
            print(f"No due rows; waiting {wait_seconds:.0f}s for the next retry window.")
            time.sleep(wait_seconds)
        print("Pass complete; checking for newly due retry rows.")
    print("Retry run complete.")


if __name__ == "__main__":
    main()
