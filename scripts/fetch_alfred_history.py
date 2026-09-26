"""Fetch and promote verified historical Alfreð pages from Common Crawl."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from psycopg.rows import dict_row

from vinnsyn.db import connect, transaction
from vinnsyn.alfred_taxonomy import alfred_job_from_html
from vinnsyn.market_ingestion import MarketListingInput, ingest_market_listings


USER_AGENT = "vinnsyn-historical-fetch/0.1"
PARSER_VERSION = "alfred-history-metadata-v3"
TAG_RE = re.compile(r"<[^>]+>")
JSON_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
META_RE = re.compile(r"<meta[^>]+(?:property|name)=[\"']([^\"']+)[\"'][^>]+content=[\"']([^\"']*)[\"'][^>]*>", re.I | re.S)
META_RE_REVERSE = re.compile(r"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]+(?:property|name)=[\"']([^\"']+)[\"'][^>]*>", re.I | re.S)
ITEMPROP_RE = re.compile(r"<[^>]+itemprop=[\"']([^\"']+)[\"'][^>]+(?:content|datetime)=[\"']([^\"']*)[\"'][^>]*>", re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
DATE_RE = r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def fetch_record(row: dict[str, object]) -> str:
    start = int(row["warc_offset"])
    length = int(row["warc_length"])
    request = Request(
        f"https://data.commoncrawl.org/{row['warc_filename']}",
        headers={"User-Agent": USER_AGENT, "Range": f"bytes={start}-{start + length - 1}"},
    )
    with urlopen(request, timeout=90) as response:
        return gzip.decompress(response.read()).decode("utf-8", errors="replace")


def record_html(record: str) -> str:
    separator_match = re.search(r"\r?\n\r?\n", record)
    payload = record[separator_match.end():] if separator_match else record
    if payload.lstrip().startswith("HTTP/"):
        http_separator_match = re.search(r"\r?\n\r?\n", payload)
        if http_separator_match:
            payload = payload[http_separator_match.end():]
    return payload


def clean_fragment(value: str | None) -> str | None:
    if not value:
        return None
    parser = TextParser()
    parser.feed(html.unescape(value))
    cleaned = " ".join(parser.parts).strip()
    return cleaned or None


def json_objects(source: str) -> list[dict[str, object]]:
    objects = []
    for fragment in JSON_LD_RE.findall(source):
        try:
            parsed = json.loads(html.unescape(fragment).strip())
        except json.JSONDecodeError:
            continue
        values = parsed if isinstance(parsed, list) else [parsed]
        for value in values:
            if not isinstance(value, dict):
                continue
            objects.append(value)
            graph = value.get("@graph")
            if isinstance(graph, list):
                objects.extend(item for item in graph if isinstance(item, dict))
    return objects


def all_meta_entries(page: str) -> list[tuple[str, str]]:
    entries = [(name.lower(), html.unescape(content).strip()) for name, content in META_RE.findall(page)]
    entries.extend((name.lower(), html.unescape(content).strip()) for content, name in META_RE_REVERSE.findall(page))
    return entries


def labeled_date(text: str, labels: str) -> str | None:
    match = re.search(rf"(?:{labels})[^0-9]{{0,80}}({DATE_RE})", text, re.I)
    return match.group(1) if match else None


def metadata_snapshot(row: dict[str, object], source: str) -> dict[str, object]:
    """Keep structured page metadata beside the immutable raw capture."""
    page = record_html(source)
    alfred_job = alfred_job_from_html(page) or {}
    visible_text = clean_fragment(page) or ""
    meta_entries = [{"name": name, "content": content} for name, content in all_meta_entries(page)]
    itemprop_entries = [
        {"property": name, "value": html.unescape(content).strip()}
        for name, content in ITEMPROP_RE.findall(page)
    ]
    posted_candidates = [
        entry["value"] for entry in itemprop_entries
        if str(entry["property"]).lower() in {"dateposted", "datepublished"}
    ]
    deadline_candidates = [
        entry["value"] for entry in itemprop_entries
        if str(entry["property"]).lower() in {"validthrough", "applicationdeadline"}
    ]
    posted_candidates += [
        entry["content"] for entry in meta_entries
        if entry["name"] in {"dateposted", "datepublished"}
    ]
    deadline_candidates += [
        entry["content"] for entry in meta_entries
        if entry["name"] in {"validthrough", "applicationdeadline"}
    ]
    posted_candidates.append(labeled_date(visible_text, r"datePosted|date published|published|posted|birtist|skráð") or "")
    deadline_candidates.append(labeled_date(visible_text, r"validThrough|application deadline|deadline|umsóknarfrestur|sækja um fyrir") or "")
    for obj in json_objects(page):
        types = obj.get("@type")
        is_job = types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types)
        if is_job:
            if obj.get("datePosted"):
                posted_candidates.append(str(obj["datePosted"]))
            if obj.get("validThrough"):
                deadline_candidates.append(str(obj["validThrough"]))
    if alfred_job.get("published"):
        posted_candidates.insert(0, str(alfred_job["published"]))
    if alfred_job.get("deadline"):
        deadline_candidates.insert(0, str(alfred_job["deadline"]))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    h1_match = H1_RE.search(page)
    return {
        "parser_version": PARSER_VERSION,
        "archive_index": row.get("archive_index"),
        "crawl_timestamp": row.get("crawl_timestamp"),
        "page_title": clean_fragment(title_match.group(1)) if title_match else None,
        "h1": clean_fragment(h1_match.group(1)) if h1_match else None,
        "meta": meta_entries,
        "itemprop": itemprop_entries,
        "json_ld": json_objects(page),
        "alfred_job": {
            "id": alfred_job.get("id"), "slug": alfred_job.get("slug"),
            "title": alfred_job.get("title"),
            "company": (alfred_job.get("brand") or {}).get("name") if isinstance(alfred_job.get("brand"), dict) else None,
            "published": alfred_job.get("published"),
        } if alfred_job else None,
        "posted_date_candidates": [value for value in posted_candidates if value],
        "deadline_candidates": [value for value in deadline_candidates if value],
    }


def extract_listing(row: dict[str, object], source: str) -> MarketListingInput | None:
    page = record_html(source)
    alfred_job = alfred_job_from_html(page) or {}
    requested_slug = str(row["canonical_url"]).rstrip("/").rsplit("/", 1)[-1]
    if alfred_job and alfred_job.get("slug") != requested_slug:
        # A generic or redirected page must not be promoted as this URL's job.
        return None
    objects = json_objects(page)
    job = next((obj for obj in objects if obj.get("@type") == "JobPosting" or (isinstance(obj.get("@type"), list) and "JobPosting" in obj["@type"])), {})
    metas = dict(all_meta_entries(page))
    head_title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    meta_title = clean_fragment(metas.get("og:title") or metas.get("twitter:title") or metas.get("title") or (head_title_match.group(1) if head_title_match else None))
    meta_title_parts = [part.strip() for part in re.split(r"\s*[|–—·]\s*", meta_title)] if meta_title else []
    title = clean_fragment(str(alfred_job.get("title") or job.get("title") or "")) or clean_fragment(H1_RE.search(page).group(1) if H1_RE.search(page) else None) or (meta_title_parts[0] if meta_title_parts else meta_title)
    brand = alfred_job.get("brand") or {}
    organization = job.get("hiringOrganization") or {}
    company = brand.get("name") if isinstance(brand, dict) else None
    if not company:
        company = organization.get("name") if isinstance(organization, dict) else None
    if not company:
        company = metas.get("author") or metas.get("og:site_name") or metas.get("article:author") or (meta_title_parts[1] if len(meta_title_parts) > 1 else None)
    if isinstance(company, str) and company.strip().casefold() in {"alfreð", "alfred"}:
        company = None
    if not company and meta_title_parts:
        company = meta_title_parts[-1] if len(meta_title_parts) > 1 else None
    if isinstance(company, str) and company.strip().casefold() in {"alfreð", "alfred"}:
        company = None
    if not title or not company:
        return None

    location = job.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else None
    if isinstance(location, dict):
        address = location.get("address") or {}
        location = ", ".join(str(address.get(key)) for key in ("addressLocality", "addressRegion", "addressCountry") if address.get(key))
    if not isinstance(location, str):
        location = None
    if not location and isinstance(alfred_job.get("address"), dict):
        location = str(alfred_job["address"].get("formatted") or "") or None
    snapshot = metadata_snapshot(row, source)
    posted = alfred_job.get("published") or job.get("datePosted") or (snapshot["posted_date_candidates"] or [None])[0]
    deadline = alfred_job.get("deadline") or job.get("validThrough") or (snapshot["deadline_candidates"] or [None])[0]
    observed_on = None
    try:
        observed_on = datetime.strptime(str(row["crawl_timestamp"]), "%Y%m%d%H%M%S").date()
    except ValueError:
        pass
    description = clean_fragment(str(alfred_job.get("bodyhtml") or alfred_job.get("description") or job.get("description") or ""))
    return MarketListingInput(
        source_key="alfred",
        source_listing_id=requested_slug,
        title=title,
        company=str(company),
        url=str(row["url"]),
        location=location,
        job_type=str(alfred_job.get("jobType") or job.get("employmentType")) if alfred_job.get("jobType") or job.get("employmentType") else None,
        posted_date=str(posted) if posted else None,
        deadline=str(deadline) if deadline else None,
        description=description,
        activate=False,
        observed_on=observed_on,
        raw_payload={
            "archive_index": row["archive_index"],
            "crawl_timestamp": row["crawl_timestamp"],
            "content_digest": row.get("content_digest"),
            "retrieval_method": row.get("retrieval_method", "common_crawl"),
            "metadata_parser_version": PARSER_VERSION,
        },
    )


def rows_to_fetch(limit: int | None) -> list[dict[str, object]]:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
            """
            select distinct on (canonical_url)
                   id, url, canonical_url, archive_index, crawl_timestamp,
                   content_digest, warc_filename, warc_offset, warc_length
            from market_historical_discoveries
            where discovery_status = 'discovered'
              and warc_filename is not null
            order by canonical_url, crawl_timestamp desc
            """
            )
            rows = cur.fetchall()
    return rows[:limit] if limit else rows


def mark_failed(row_id: int, message: str) -> None:
    with transaction():
        with connect() as conn:
            conn.execute(
                "update market_historical_discoveries set discovery_status = 'failed', fetch_error = %s, fetched_at = now() where id = %s",
                (message[:1000], row_id),
            )


def mark_imported(row_ids: list[int]) -> None:
    if not row_ids:
        return
    with transaction():
        with connect() as conn:
            conn.execute("update market_historical_discoveries set discovery_status = 'imported', fetched_at = now(), fetch_error = null where id = any(%s)", (row_ids,))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Fetch only this many historical URLs first.")
    parser.add_argument("--workers", type=int, default=6, help="Parallel archive fetches (default: 6).")
    args = parser.parse_args()
    rows = rows_to_fetch(args.limit)
    print(f"Fetching {len(rows)} archived listing URLs with {args.workers} workers.")
    successes: list[tuple[dict[str, object], MarketListingInput]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_record, row): row for row in rows}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                listing = extract_listing(row, future.result())
                if listing is None:
                    mark_failed(int(row["id"]), "Archived page did not expose a reliable title and company.")
                else:
                    successes.append((row, listing))
            except Exception as error:
                mark_failed(int(row["id"]), str(error))
            if index % 100 == 0:
                print(f"  fetched {index}/{len(rows)}; parsed {len(successes)}")

    for start in range(0, len(successes), 100):
        batch = successes[start:start + 100]
        ingest_market_listings(
            [listing for _, listing in batch],
            discovery_method="common_crawl_historical_detail_fetch",
            expected_count=len(batch),
            complete_scan=False,
        )
        mark_imported([int(row["id"]) for row, _ in batch])
    print(f"Imported {len(successes)} verified historical listings.")


if __name__ == "__main__":
    main()
