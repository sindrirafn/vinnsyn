"""Recover and preserve metadata for historical Alfreð listings already imported."""

from __future__ import annotations

import argparse
import gzip
import sys
import time
from pathlib import Path

from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vinnsyn.db import connect, transaction
from scripts.fetch_alfred_history import extract_listing, metadata_snapshot
from scripts.retry_alfred_history import (
    ArchiveCapture,
    fetch_live_record,
    fetch_record,
    store_capture_document,
    store_live_document,
)


def rows_to_recover(limit: int | None, all_listings: bool) -> list[dict[str, object]]:
    condition = "" if all_listings else "and (nullif(trim(j.posted_date_raw), '') is null or nullif(trim(j.deadline_raw), '') is null)"
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select j.id as listing_id, j.canonical_url, j.url,
                       j.posted_date_raw, j.deadline_raw,
                       d.id as id, d.id as discovery_id, d.archive_index, d.crawl_timestamp,
                       d.content_digest, d.warc_filename, d.warc_offset,
                       d.warc_length, doc.raw_record_gzip
                from market_job_listings j
                join lateral (
                    select d.*
                    from market_historical_discoveries d
                    where d.canonical_url = j.canonical_url
                      and d.warc_filename is not null
                      and d.discovery_status in ('imported', 'fetched', 'discovered')
                    order by (exists (
                        select 1 from market_historical_capture_documents stored
                        where stored.discovery_id = d.id
                    )) desc, d.crawl_timestamp desc
                    limit 1
                ) d on true
                left join market_historical_capture_documents doc
                  on doc.discovery_id = d.id
                where j.latest_raw_payload ? 'archive_index'
                  {condition}
                order by j.id
                """
            )
            rows = cur.fetchall()
    return rows[:limit] if limit else rows


def update_listing_dates(row: dict[str, object], posted: str | None, deadline: str | None) -> bool:
    if not posted and not deadline:
        return False
    with transaction():
        with connect() as conn:
            conn.execute(
                """
                update market_job_listings
                set posted_date_raw = coalesce(nullif(trim(posted_date_raw), ''), %s),
                    deadline_raw = coalesce(nullif(trim(deadline_raw), ''), %s),
                    latest_raw_payload = latest_raw_payload || %s::jsonb,
                    updated_at = now()
                where id = %s
                """,
                (
                    posted,
                    deadline,
                    '{"metadata_recovered": true}',
                    row["listing_id"],
                ),
            )
            conn.execute(
                """
                update market_job_listing_observations
                set posted_date_raw = coalesce(nullif(trim(posted_date_raw), ''), %s),
                    deadline_raw = coalesce(nullif(trim(deadline_raw), ''), %s)
                where listing_id = %s
                  and discovery_method like 'common_crawl%%'
                """,
                (posted, deadline, row["listing_id"]),
            )
    return True


def first_value(values: object) -> str | None:
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Recover only this many historical listings.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between archive requests when a document is not stored.")
    parser.add_argument("--all", action="store_true", help="Preserve documents for all historical listings, not only missing-date listings.")
    parser.add_argument("--verbose", action="store_true", help="Print each listing and recovery outcome.")
    args = parser.parse_args()
    if args.interval < 0:
        parser.error("--interval must be non-negative")

    rows = rows_to_recover(args.limit, args.all)
    print(f"Recovering metadata for {len(rows)} historical listings.")
    recovered = 0
    stored = 0
    failed = 0
    last_request = 0.0
    for index, row in enumerate(rows, start=1):
        try:
            live_row = dict(row)
            live_row["retrieval_method"] = "direct_alfred"
            live_row["archive_index"] = "direct_alfred"
            try:
                live_capture = fetch_live_record(live_row)
            except (TimeoutError, OSError, ValueError):
                live_capture = None
            if live_capture and live_capture.status and 200 <= live_capture.status < 300 and extract_listing(live_row, live_capture.record):
                store_live_document(live_row, live_capture)
                capture = live_capture
                stored += 1
            elif row["raw_record_gzip"] is not None:
                raw = bytes(row["raw_record_gzip"])
                record = gzip.decompress(raw).decode("utf-8", errors="replace")
                capture = ArchiveCapture(record, raw, None, None)
            else:
                wait = args.interval - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
                last_request = time.monotonic()
                capture = fetch_record(row)
                if capture.status in {403, 408, 425, 429, 500, 502, 503, 504}:
                    failed += 1
                    print(f"  archive retryable response for {row['canonical_url']}: HTTP {capture.status}")
                    continue
                store_capture_document(row, capture)
                stored += 1

            snapshot = metadata_snapshot(row, capture.record)
            posted = first_value(snapshot.get("posted_date_candidates"))
            deadline = first_value(snapshot.get("deadline_candidates"))
            changed = update_listing_dates(row, posted, deadline)
            recovered += int(changed)
            if args.verbose:
                print(f"  {index}/{len(rows)} {row['canonical_url']}: posted={posted!r}, deadline={deadline!r}, updated={changed}")
            elif index % 25 == 0:
                print(f"  progress: {index}/{len(rows)}, date updates={recovered}, documents stored={stored}")
        except Exception as error:
            failed += 1
            print(f"  failed {row['canonical_url']}: {error}")

    print(f"Recovery complete: {recovered} listings updated, {stored} documents stored, {failed} failures.")


if __name__ == "__main__":
    main()
