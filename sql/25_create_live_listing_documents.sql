-- Direct Alfreð page responses. Common Crawl remains URL discovery and an
-- archive fallback; live Alfreð responses are stored separately so neither
-- source overwrites the other.

create table if not exists market_historical_live_documents (
    discovery_id bigint primary key
        references market_historical_discoveries(id) on delete cascade,
    listing_url text not null,
    raw_html_gzip bytea not null,
    raw_html_sha256 text not null,
    response_bytes integer not null,
    http_status integer,
    content_type text,
    metadata_snapshot jsonb not null default '{}'::jsonb,
    parser_version text not null,
    fetched_at timestamptz not null default now(),
    created_at timestamptz not null default now(),

    check (jsonb_typeof(metadata_snapshot) = 'object'),
    check (response_bytes > 0)
);

create index if not exists idx_market_live_documents_hash
    on market_historical_live_documents (raw_html_sha256);
