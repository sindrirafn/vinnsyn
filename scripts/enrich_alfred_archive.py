"""Create local, evidence-backed market taxonomy enrichments from saved Alfreð pages."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vinnsyn.alfred_taxonomy import (
    JobArea,
    alfred_job_from_html,
    job_text_parts,
    merge_skill_matches,
    profession_tags,
    source_categories,
    structured_skill_matches,
)
from vinnsyn.db import connect, transaction
from vinnsyn.market_skills import CorpusPart, SkillMatch, extract_explicit_skills
from scripts.fetch_alfred_history import record_html


EXTRACTOR = "alfred_structured_market_taxonomy"
PARSER_VERSION = "market_taxonomy_v2"
BATCH_SIZE = 100


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _decode_document(document: dict[str, Any]) -> str | None:
    try:
        decoded = gzip.decompress(bytes(document["raw_gzip"])).decode("utf-8", errors="replace")
    except (OSError, EOFError):
        return None
    return record_html(decoded) if document["warc_record"] else decoded


def _best_job(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Select the richest first-party job object; never parse generic page JSON."""
    best: tuple[int, dict[str, Any], str] | None = None
    for document in row["documents"]:
        page = _decode_document(document)
        if not page:
            continue
        job = alfred_job_from_html(page)
        if not job:
            continue
        category_count = len(job.get("categories", []))
        tag_count = sum(len(item.get("jobTags", [])) for item in job.get("categories", []) if isinstance(item, dict))
        score = (100 * category_count) + (10 * tag_count) + (5 * len(job.get("skills", []))) + len(job.get("languages", []))
        candidate = (score, job, str(document["source"]))
        if best is None or candidate[0] > best[0]:
            best = candidate
    return (best[1], best[2]) if best else (None, None)


def _row_taxonomy(row: dict[str, Any]) -> None:
    job, document_source = _best_job(row)
    if job:
        areas = source_categories(job)
        tags = profession_tags(job)
        structured_matches = structured_skill_matches(job)
        parts = job_text_parts(job)
        lexical_matches = extract_explicit_skills(parts)
        matches = merge_skill_matches(structured_matches, lexical_matches)
        row.update(job=job, document_source=document_source, areas=areas, tags=tags, matches=matches, parts=parts)
    else:
        # Browser-card-only rows still get conservative text extraction, but no
        # fabricated job area or profession classification.
        parts = [CorpusPart("listing:description", _text(row["description"]))]
        row.update(job=None, document_source=None, areas=[], tags=[], matches=extract_explicit_skills(parts), parts=[part for part in parts if part.text])
    material = {
        "parts": [(part.source, part.text) for part in row["parts"]],
        "areas": [(area.area.key, area.source_category_id, area.source_name) for area in row["areas"]],
        "tags": [(tag.source_tag_id, tag.name) for tag in row["tags"]],
        "skills": [(match.name, match.dimension, match.importance, match.source) for match in row["matches"]],
    }
    row["source_content_hash"] = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_rows_after(after_listing_id: int, batch_size: int) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select j.id as listing_id, j.source_key, j.title, j.description,
                       coalesce(documents.items, '[]'::jsonb) as documents
                from market_job_listings j
                left join lateral (
                    select jsonb_agg(jsonb_build_object(
                        'source', source, 'raw_gzip', encode(raw_gzip, 'base64'), 'warc_record', warc_record
                    ) order by source) as items
                    from (
                        select 'historical_capture:' || discovery.id as source, d.raw_record_gzip as raw_gzip, true as warc_record
                        from market_historical_discoveries discovery
                        join market_historical_capture_documents d on d.discovery_id = discovery.id
                        where discovery.canonical_url = j.canonical_url
                        union all
                        select 'live_alfred:' || discovery.id as source, d.raw_html_gzip as raw_gzip, false as warc_record
                        from market_historical_discoveries discovery
                        join market_historical_live_documents d on d.discovery_id = discovery.id
                        where discovery.canonical_url = j.canonical_url
                    ) documents_raw
                ) documents on true
                where j.id > %s
                order by j.id
                limit %s
                """,
                (after_listing_id, batch_size),
            )
            rows = cur.fetchall()
    for row in rows:
        for document in row["documents"]:
            document["raw_gzip"] = base64.b64decode(document["raw_gzip"])
        _row_taxonomy(row)
    return rows


def processed_hashes() -> set[tuple[int, str]]:
    with connect() as conn:
        return {
            (int(listing_id), source_hash)
            for listing_id, source_hash in conn.execute(
                """select listing_id, source_content_hash from market_job_listing_enrichments
                   where extractor = %s and prompt_version = %s and status = 'succeeded'""",
                (EXTRACTOR, PARSER_VERSION),
            )
        }


def _skill_ids(conn) -> dict[str, int]:
    return {normalized_name: skill_id for skill_id, normalized_name in conn.execute("select id, normalized_name from market_skills")}


def _upsert_area(cur, area: JobArea) -> None:
    cur.execute(
        """insert into market_job_areas (key, name, display_order) values (%s, %s, %s)
           on conflict (key) do update set name = excluded.name, display_order = excluded.display_order""",
        (area.key, area.name, area.display_order),
    )


def _upsert_profession_tag(cur, source_key: str, source_tag_id: str | None, name: str) -> int:
    cur.execute(
        """insert into market_profession_tags (source_key, source_tag_id, name, normalized_name)
           values (%s, %s, %s, %s)
           on conflict (source_key, normalized_name) do update set source_tag_id = excluded.source_tag_id, name = excluded.name
           returning id""",
        (source_key, source_tag_id, name, name.casefold()),
    )
    return int(cur.fetchone()[0])


def save_batch(rows: list[dict[str, Any]]) -> None:
    with transaction():
        with connect() as conn:
            skill_ids = _skill_ids(conn)
            with conn.cursor() as cur:
                for row in rows:
                    listing_id = int(row["listing_id"])
                    payload = {
                        "extractor": EXTRACTOR, "parser_version": PARSER_VERSION,
                        "source_content_hash": row["source_content_hash"], "document_source": row["document_source"],
                        "job_area_count": len(row["areas"]), "profession_tag_count": len(row["tags"]),
                        "explicit_skills": [match.name for match in row["matches"]],
                        "skill_matches": [
                            {"name": match.name, "dimension": match.dimension, "importance": match.importance,
                             "source": match.source, "matched_text": match.matched_text, "source_text": match.source_text}
                            for match in row["matches"]
                        ],
                    }
                    cur.execute(
                        """insert into market_job_listing_enrichments (
                               listing_id, extractor, model, prompt_version, source_content_hash, status, raw_response, completed_at
                           ) values (%s, %s, null, %s, %s, 'succeeded', %s::jsonb, now()) returning id""",
                        (listing_id, EXTRACTOR, PARSER_VERSION, row["source_content_hash"], json.dumps(payload, ensure_ascii=False)),
                    )
                    enrichment_id = int(cur.fetchone()[0])
                    for category in row["areas"]:
                        _upsert_area(cur, category.area)
                        cur.execute(
                            """insert into market_listing_job_areas (
                                   enrichment_id, listing_id, job_area_key, source_category_id, source_name, source_slug
                               ) values (%s, %s, %s, %s, %s, %s)""",
                            (enrichment_id, listing_id, category.area.key, category.source_category_id, category.source_name, category.source_slug),
                        )
                    for tag in row["tags"]:
                        tag_id = _upsert_profession_tag(cur, row["source_key"], tag.source_tag_id, tag.name)
                        cur.execute(
                            """insert into market_listing_profession_tags (
                                   enrichment_id, listing_id, profession_tag_id, source_category_id
                               ) values (%s, %s, %s, %s)""",
                            (enrichment_id, listing_id, tag_id, tag.source_category_id),
                        )
                    for match in row["matches"]:
                        normalized = match.name.casefold()
                        skill_id = skill_ids.get(normalized)
                        if skill_id is None:
                            cur.execute(
                                """insert into market_skills (name, normalized_name, dimension) values (%s, %s, %s)
                                   on conflict (normalized_name) do update set name = excluded.name, dimension = excluded.dimension
                                   returning id""",
                                (match.name, normalized, match.dimension),
                            )
                            skill_id = int(cur.fetchone()[0])
                            skill_ids[normalized] = skill_id
                        else:
                            cur.execute("update market_skills set dimension = %s where id = %s", (match.dimension, skill_id))
                        cur.execute(
                            """insert into market_job_listing_skill_mentions (
                                   enrichment_id, listing_id, skill_id, skill_kind, importance, source_text, confidence
                               ) values (%s, %s, %s, 'explicit', %s, %s, 1.0)""",
                            (enrichment_id, listing_id, skill_id, match.importance, match.source_text),
                        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Process only this many listings.")
    parser.add_argument("--after-id", type=int, default=0, help="Resume or inspect listings after this archive ID.")
    parser.add_argument("--all", action="store_true", help="Create a new enrichment even for unchanged structured content.")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Listings per transaction (default: {BATCH_SIZE}).")
    parser.add_argument("--verbose", action="store_true", help="Print every classified listing.")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1.")
    processed = set() if args.all else processed_hashes()
    saved = skipped = 0
    after_listing_id = args.after_id
    print(f"Classifying pending listings with {PARSER_VERSION}; only saved documents are read.")
    while True:
        fetched = load_rows_after(after_listing_id, args.batch_size)
        if not fetched:
            break
        after_listing_id = int(fetched[-1]["listing_id"])
        batch = [row for row in fetched if (int(row["listing_id"]), row["source_content_hash"]) not in processed]
        skipped += len(fetched) - len(batch)
        if args.limit is not None:
            batch = batch[:max(args.limit - saved, 0)]
        if batch:
            save_batch(batch)
            saved += len(batch)
            if args.verbose:
                for row in batch:
                    print(f"  {row['title']}: {', '.join(area.area.name for area in row['areas']) or 'no job area'}")
            else:
                print(f"  progress: {saved} saved; {skipped} unchanged skipped", flush=True)
        if args.limit is not None and saved >= args.limit:
            break
    print(f"Classification complete: {saved} results saved; {skipped} unchanged skipped.")


if __name__ == "__main__":
    main()
