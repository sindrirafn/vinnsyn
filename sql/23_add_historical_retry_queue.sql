-- Durable retry state for archive fetches. The discovery row remains the
-- checkpoint, so the worker can stop and resume without losing progress.

alter table market_historical_discoveries
    add column if not exists attempt_count integer not null default 0,
    add column if not exists next_retry_at timestamptz,
    add column if not exists last_attempt_at timestamptz,
    add column if not exists last_http_status integer;

create index if not exists idx_market_historical_retry_queue
    on market_historical_discoveries (discovery_status, next_retry_at, attempt_count)
    where discovery_status = 'discovered';
