-- Immutable archive evidence for historical market listings.
-- The discovery row identifies where a Common Crawl capture lives; this table
-- preserves what was actually retrieved so future parsers do not need to
-- contact the archive again.

create table if not exists market_historical_capture_documents (
    discovery_id bigint primary key
        references market_historical_discoveries(id) on delete cascade,
    archive_index text not null,
    crawl_timestamp text not null,
    content_digest text,
    raw_record_gzip bytea not null,
    raw_record_sha256 text not null,
    record_bytes integer not null,
    http_status integer,
    content_type text,
    metadata_snapshot jsonb not null default '{}'::jsonb,
    parser_version text not null,
    fetched_at timestamptz not null default now(),
    created_at timestamptz not null default now(),

    check (jsonb_typeof(metadata_snapshot) = 'object'),
    check (record_bytes > 0)
);

create index if not exists idx_market_capture_documents_archive
    on market_historical_capture_documents (archive_index, crawl_timestamp desc);

create index if not exists idx_market_capture_documents_digest
    on market_historical_capture_documents (raw_record_sha256);
