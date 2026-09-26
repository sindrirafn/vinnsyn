"""Discover historical Alfreð listing URLs from Common Crawl indexes."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from vinnsyn.db import connect, transaction
from vinnsyn.urls import canonicalize_url


COLLECTIONS_URL = "https://index.commoncrawl.org/collinfo.json"
USER_AGENT = "vinnsyn-historical-discovery/0.1"


def fetch_json_lines(index_id: str, pattern: str, include_all_responses: bool = False) -> tuple[list[dict[str, object]], str | None]:
    query_parts = [("url", pattern), ("output", "json")]
    if not include_all_responses:
        query_parts.extend([("filter", "status:200"), ("filter", "mime:text/html")])
    query_parts.append(("collapse", "urlkey"))
    query = urlencode(query_parts)
    url = f"https://index.commoncrawl.org/{index_id}-index?{query}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    body = ""
    for attempt in range(3):
        try:
            with urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
            break
        except (HTTPError, URLError, RemoteDisconnected, TimeoutError, OSError) as error:
            if attempt == 2:
                return [], f"{type(error).__name__}: {error}"
            time.sleep(2 ** attempt)
    rows: list[dict[str, object]] = []
    malformed = 0
    for line in body.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    if malformed:
        print(f"  skipped {malformed} malformed/truncated index line(s) from {index_id} {pattern}")
    return rows, None


def collection_indexes(all_collections: bool, from_year: int) -> list[str]:
    request = Request(COLLECTIONS_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        collections = json.loads(response.read().decode("utf-8"))

    by_year: dict[str, list[str]] = defaultdict(list)
    for collection in collections:
        index_id = collection.get("id", "")
        if index_id.startswith("CC-MAIN-"):
            by_year[index_id.split("-")[2]].append(index_id)
    if all_collections:
        return sorted(index_id for values in by_year.values() for index_id in values)
    return [sorted(values)[-1] for year, values in sorted(by_year.items()) if int(year) >= from_year]


def discover(
    indexes: list[str],
    patterns: list[str],
    include_all_responses: bool,
    request_interval: float,
) -> tuple[list[dict[str, object]], int, int]:
    discovered: list[dict[str, object]] = []
    errors = 0
    successful_queries = 0
    for index_id in indexes:
        for pattern in patterns:
            rows, error = fetch_json_lines(index_id, pattern, include_all_responses)
            if error:
                errors += 1
                print(f"  {index_id} {pattern}: ERROR {error}")
                time.sleep(request_interval)
                continue
            successful_queries += 1
            print(f"  {index_id} {pattern}: {len(rows)} captures")
            for row in rows:
                url = str(row.get("url") or "")
                if not url:
                    continue
                discovered.append({
                    "source_key": "alfred",
                    "url": url,
                    "canonical_url": canonicalize_url(url),
                    "archive_index": index_id,
                    "crawl_timestamp": str(row.get("timestamp") or ""),
                    "content_digest": row.get("digest"),
                        "http_status": int(row["status"]) if row.get("status") else None,
                        "mime_type": row.get("mime"),
                        "warc_filename": row.get("filename"),
                        "warc_offset": int(row["offset"]) if row.get("offset") else None,
                        "warc_length": int(row["length"]) if row.get("length") else None,
                })
            time.sleep(request_interval)
    return discovered, errors, successful_queries


def store(rows: list[dict[str, object]]) -> int:
    with transaction():
        with connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        """
                        insert into market_historical_discoveries (
                            source_key, url, canonical_url, archive_index,
                            crawl_timestamp, content_digest, http_status, mime_type,
                            warc_filename, warc_offset, warc_length
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        on conflict (source_key, canonical_url, archive_index, crawl_timestamp)
                        do update set content_digest = excluded.content_digest,
                                      http_status = excluded.http_status,
                                      mime_type = excluded.mime_type,
                                      warc_filename = excluded.warc_filename,
                                      warc_offset = excluded.warc_offset,
                                      warc_length = excluded.warc_length
                        """,
                        tuple(row[field] for field in (
                            "source_key", "url", "canonical_url", "archive_index",
                            "crawl_timestamp", "content_digest", "http_status", "mime_type",
                            "warc_filename", "warc_offset", "warc_length",
                        )),
                    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="append", help="Specific Common Crawl index ID; repeatable.")
    parser.add_argument("--all-collections", action="store_true", help="Search every available Common Crawl collection, not only the latest collection per year.")
    parser.add_argument("--from-year", type=int, default=2019, help="When using yearly mode, include collections from this year onward (default: 2019).")
    parser.add_argument("--all-responses", action="store_true", help="Keep redirects/non-200/non-HTML responses too; direct retrieval will validate them later.")
    parser.add_argument("--request-interval", type=float, default=1.0, help="Seconds between Common Crawl index requests (default: 1).")
    parser.add_argument("--pattern", action="append", help="URL pattern to search; repeatable. Defaults include current and legacy Alfreð listing paths.")
    args = parser.parse_args()
    patterns = args.pattern or [
        # Whole-host probes are important for old site versions whose listing
        # route was not /starf/.  The narrower probes below preserve useful
        # behavior for modern and known legacy routes.
        "alfred.is/*",
        "www.alfred.is/*",
        "*.alfred.is/*",
        "alfred.is/starf/*",
        "www.alfred.is/starf/*",
        "alfred.is/job/*",
        "www.alfred.is/job/*",
        "alfred.is/jobs/*",
        "www.alfred.is/jobs/*",
        "alfred.is/atvinna/*",
        "www.alfred.is/atvinna/*",
    ]
    indexes = args.index or collection_indexes(args.all_collections, args.from_year)
    print(f"Searching {len(indexes)} Common Crawl collections: {', '.join(indexes)}")
    print(f"URL patterns: {', '.join(patterns)}")
    if args.all_responses:
        print("Keeping all response types; the direct Alfreð fetcher will validate them later.")
    rows, errors, successful_queries = discover(indexes, patterns, args.all_responses, max(0.0, args.request_interval))
    if errors:
        print(f"Index request errors: {errors}; successful queries: {successful_queries}.")
    if errors and successful_queries == 0:
        raise SystemExit("Common Crawl returned no successful index responses; nothing was stored. Retry later rather than treating this as zero historical coverage.")
    unique_urls = len({row["canonical_url"] for row in rows})
    stored = store(rows)
    print(f"Discovered {stored} archive captures for {unique_urls} unique listing URLs.")


if __name__ == "__main__":
    main()
