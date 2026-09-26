-- URL-level evidence discovered in web archives before detail-page fetching.
-- These rows are not job listings yet: titles and companies are only promoted
-- after the archived page itself has been fetched and parsed.

create table if not exists market_historical_discoveries (
    id bigserial primary key,
    source_key text not null references market_sources(source_key),
    url text not null,
    canonical_url text not null,
    archive_index text not null,
    crawl_timestamp text not null,
    content_digest text,
    http_status integer,
    mime_type text,
    warc_filename text,
    warc_offset bigint,
    warc_length integer,
    discovery_status text not null default 'discovered' check (
        discovery_status in ('discovered', 'fetched', 'imported', 'failed', 'not_a_listing')
    ),
    fetch_error text,
    discovered_at timestamptz not null default now(),
    fetched_at timestamptz,
    unique (source_key, canonical_url, archive_index, crawl_timestamp)
);

alter table market_historical_discoveries
    add column if not exists warc_filename text,
    add column if not exists warc_offset bigint,
    add column if not exists warc_length integer;

create index if not exists idx_market_historical_discoveries_source_url
    on market_historical_discoveries (source_key, canonical_url);

create index if not exists idx_market_historical_discoveries_status
    on market_historical_discoveries (discovery_status, discovered_at);
