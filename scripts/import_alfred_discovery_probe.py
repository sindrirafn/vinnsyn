"""Import Internet Archive listing candidates into the historical retry queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vinnsyn.db import connect, transaction
from vinnsyn.urls import canonicalize_url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default="data/market/alfred-discovery-probe.json",
        help="Probe report produced by probe_alfred_discovery.py.",
    )
    args = parser.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    urls = report.get("unique_listing_urls", [])
    if not isinstance(urls, list):
        raise SystemExit("The report does not contain unique_listing_urls.")

    inserted = 0
    with transaction():
        with connect() as conn:
            with conn.cursor() as cur:
                for raw_url in urls:
                    url = str(raw_url).strip()
                    if not url:
                        continue
                    cur.execute(
                        """
                        insert into market_historical_discoveries (
                            source_key, url, canonical_url, archive_index,
                            crawl_timestamp, http_status, mime_type
                        ) values (%s, %s, %s, %s, %s, %s, %s)
                        on conflict (source_key, canonical_url, archive_index, crawl_timestamp)
                        do nothing
                        """,
                        (
                            "alfred",
                            url,
                            canonicalize_url(url),
                            "internet_archive_cdx",
                            "wayback-index",
                            200,
                            "text/html",
                        ),
                    )
                    inserted += cur.rowcount
    print(f"Internet Archive candidates in report: {len(urls)}")
    print(f"New discovery rows queued: {inserted}")
    print("These rows will be fetched directly from Alfred; the Wayback index is only URL evidence.")


if __name__ == "__main__":
    main()
