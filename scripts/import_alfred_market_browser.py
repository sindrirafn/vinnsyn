"""Import a JSON export captured from the public Alfreð jobs page.

The browser collector uses the normal visible jobs page and its infinite-scroll
UI. This small importer deliberately accepts only the fields visible in each
listing card; descriptions and skills are enriched in a later pass.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from vinnsyn.market_ingestion import MarketListingInput, ingest_market_listings


ALFRED_BASE_URL = "https://alfred.is"
DATE_RE = re.compile(r"^\d{1,2}\.\s+[^\s]+\.$")
JOB_TYPE_RE = re.compile(r"(?:Fullt starf|Hlutastarf|Tímabundið)")


def parse_card(record: dict[str, str]) -> MarketListingInput:
    href = record.get("href", "").strip()
    lines = [line.strip() for line in record.get("text", "").splitlines() if line.strip()]
    if not href or len(lines) < 3:
        raise ValueError("Listing card is missing its link or identity fields.")

    slug = href.rstrip("/").rsplit("/", 1)[-1]
    title = lines[1]
    company = lines[2]
    tail = lines[3:]
    deadline = next((line for line in tail if DATE_RE.fullmatch(line)), None)
    job_type = next((line for line in tail if JOB_TYPE_RE.search(line)), None)
    location_lines = [line for line in tail if line not in {deadline, job_type}]

    url = urljoin(ALFRED_BASE_URL, href)
    return MarketListingInput(
        source_key="alfred",
        source_listing_id=slug,
        title=title,
        company=company,
        url=url,
        location="; ".join(location_lines) or None,
        job_type=job_type,
        posted_date=lines[0],
        deadline=deadline,
        raw_payload={"browser_card_text": record.get("text", ""), "href": href},
    )


def import_snapshot(raw_records) -> None:
    if isinstance(raw_records, dict):
        raw_records = raw_records.get("cards")
    if not isinstance(raw_records, list):
        raise SystemExit("Expected a JSON array or snapshot object of browser listing cards.")

    unique_records = {}
    for record in raw_records:
        if isinstance(record, dict) and isinstance(record.get("href"), str):
            unique_records.setdefault(record["href"], record)

    listings = [parse_card(record) for record in unique_records.values()]
    result = ingest_market_listings(
        listings,
        discovery_method="alfred_public_jobs_browser_infinite_scroll",
        expected_count=len(listings),
        complete_scan=True,
        observed_on=date.today(),
    )
    print(f"Imported current Alfreð listings: {result.observed_listing_count}")
    print(f"Deactivated listings absent from complete scan: {result.deactivated_listing_count}")
    print(f"Collection run ID: {result.collection_run_id}")


def main() -> None:
    if len(sys.argv) > 1:
        raw_records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        raw_records = json.load(sys.stdin)
    import_snapshot(raw_records)


if __name__ == "__main__":
    main()
