from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from vinnsyn.db import connect, transaction
from vinnsyn.urls import canonicalize_url


@dataclass(frozen=True, slots=True)
class MarketListingInput:
    """Source-neutral public listing shape for the market archive."""

    source_key: str
    title: str
    company: str
    url: str
    source_listing_id: str | None = None
    location: str | None = None
    job_type: str | None = None
    posted_date: str | None = None
    deadline: str | None = None
    description: str | None = None
    activate: bool = True
    observed_on: date | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("source_key", "title", "company", "url"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required.")

        for field_name in (
            "source_listing_id",
            "location",
            "job_type",
            "posted_date",
            "deadline",
            "description",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field_name} must be text or null.")

        if not isinstance(self.raw_payload, dict):
            raise ValueError("raw_payload must be a JSON object.")
        if not isinstance(self.activate, bool):
            raise ValueError("activate must be boolean.")
        if self.observed_on is not None and not isinstance(self.observed_on, date):
            raise ValueError("observed_on must be a date or null.")


@dataclass(frozen=True, slots=True)
class MarketIngestionResult:
    """Summary of one complete or partial source collection run."""

    collection_run_id: int
    observed_listing_count: int
    deactivated_listing_count: int


def _content_hash(listing: MarketListingInput) -> str:
    payload = {
        "source_key": listing.source_key,
        "source_listing_id": listing.source_listing_id,
        "url": canonicalize_url(listing.url),
        "title": listing.title,
        "company": listing.company,
        "location": listing.location,
        "job_type": listing.job_type,
        "posted_date": listing.posted_date,
        "deadline": listing.deadline,
        "description": listing.description,
        "raw_payload": listing.raw_payload,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _find_market_listing(cur, listing: MarketListingInput, canonical_url: str):
    if listing.source_listing_id:
        cur.execute(
            """
            select id
            from market_job_listings
            where source_key = %s and source_listing_id = %s
            """,
            (listing.source_key, listing.source_listing_id),
        )
        found = cur.fetchone()
        if found:
            return found[0]

    cur.execute(
        """
        select id
        from market_job_listings
        where source_key = %s and canonical_url = %s
        """,
        (listing.source_key, canonical_url),
    )
    found = cur.fetchone()
    return found[0] if found else None


def _upsert_market_listing(cur, listing: MarketListingInput) -> tuple[int, str]:
    canonical_url = canonicalize_url(listing.url)
    content_hash = _content_hash(listing)
    existing_id = _find_market_listing(cur, listing, canonical_url)
    values = (
        listing.source_key,
        listing.source_listing_id,
        listing.url,
        canonical_url,
        listing.title,
        listing.company,
        listing.location,
        listing.job_type,
        listing.posted_date,
        listing.deadline,
        listing.description,
        listing.activate,
        content_hash,
        json.dumps(listing.raw_payload, ensure_ascii=False, default=str),
    )

    if existing_id is None:
        cur.execute(
            """
            insert into market_job_listings (
                source_key, source_listing_id, url, canonical_url, title,
                company, location, job_type, posted_date_raw, deadline_raw,
                description, is_currently_active,
                last_content_hash,
                latest_raw_payload
            ) values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb
            )
            returning id
            """,
            values,
        )
        listing_id = cur.fetchone()[0]
    else:
        cur.execute(
            """
            update market_job_listings
            set source_listing_id = %s,
                url = %s,
                canonical_url = %s,
                title = %s,
                company = %s,
                location = %s,
                job_type = %s,
                posted_date_raw = %s,
                deadline_raw = %s,
                description = %s,
                is_currently_active = is_currently_active or %s,
                last_seen_at = now(),
                last_content_hash = %s,
                latest_raw_payload = %s::jsonb,
                updated_at = now()
            where id = %s
            """,
            values[1:-3] + (listing.activate, values[-2], values[-1], existing_id),
        )
        listing_id = existing_id

    return listing_id, content_hash


def ingest_market_listings(
    listings: Iterable[MarketListingInput],
    *,
    discovery_method: str,
    expected_count: int | None = None,
    complete_scan: bool = True,
    observed_on: date | None = None,
) -> MarketIngestionResult:
    """Store one source run and optionally reconcile source visibility.

    A source is only reconciled when ``complete_scan`` is true. This is the
    safety boundary that prevents a failed or intentionally partial crawl from
    marking unseen public listings inactive.
    """

    listing_values = list(listings)
    if not discovery_method.strip():
        raise ValueError("discovery_method is required.")
    if not listing_values:
        raise ValueError("At least one listing is required.")

    source_keys = {listing.source_key for listing in listing_values}
    if len(source_keys) != 1:
        raise ValueError("A collection run must contain listings from one source.")
    source_key = next(iter(source_keys))

    with transaction():
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into market_collection_runs (
                        source_key, discovery_method, expected_count
                    ) values (%s, %s, %s)
                    returning id, started_at
                    """,
                    (source_key, discovery_method, expected_count),
                )
                run_id, started_at = cur.fetchone()

                seen_ids: list[int] = []
                for listing in listing_values:
                    observation_date = listing.observed_on or observed_on or date.today()
                    cur.execute(
                        "select source_key from market_sources where source_key = %s",
                        (listing.source_key,),
                    )
                    if cur.fetchone() is None:
                        raise ValueError(f"Unknown market source: {listing.source_key}")

                    listing_id, content_hash = _upsert_market_listing(cur, listing)
                    seen_ids.append(listing_id)
                    cur.execute(
                        """
                        insert into market_job_listing_observations (
                            listing_id, collection_run_id, observed_on,
                            discovery_method, is_active, title, company,
                            location, job_type, posted_date_raw, deadline_raw,
                            content_hash, raw_payload
                        ) values (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s::jsonb
                        )
                        on conflict (listing_id, observed_on) do update
                        set collection_run_id = excluded.collection_run_id,
                            observed_at = now(),
                            discovery_method = excluded.discovery_method,
                            is_active = excluded.is_active,
                            title = excluded.title,
                            company = excluded.company,
                            location = excluded.location,
                            job_type = excluded.job_type,
                            posted_date_raw = excluded.posted_date_raw,
                            deadline_raw = excluded.deadline_raw,
                            content_hash = excluded.content_hash,
                            raw_payload = excluded.raw_payload
                        """,
                        (
                            listing_id,
                            run_id,
                            observation_date,
                            discovery_method,
                            listing.activate,
                            listing.title,
                            listing.company,
                            listing.location,
                            listing.job_type,
                            listing.posted_date,
                            listing.deadline,
                            content_hash,
                            json.dumps(listing.raw_payload, ensure_ascii=False, default=str),
                        ),
                    )

                deactivated_count = 0
                if complete_scan:
                    cur.execute(
                        """
                        update market_job_listings
                        set is_currently_active = false,
                            updated_at = now()
                        where source_key = %s
                          and is_currently_active
                          and last_seen_at < %s
                        """,
                        (source_key, started_at),
                    )
                    deactivated_count = cur.rowcount

                cur.execute(
                    """
                    update market_collection_runs
                    set completed_at = now(), status = 'succeeded',
                        observed_count = %s
                    where id = %s
                    """,
                    (len(seen_ids), run_id),
                )

    return MarketIngestionResult(run_id, len(seen_ids), deactivated_count)
