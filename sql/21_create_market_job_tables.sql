-- Public job-market data, kept separate from the private career workflow.
--
-- These tables are intentionally not connected to raw_job_listings or
-- collected_job_candidates. A public listing can exist in the market archive
-- without ever becoming a personally relevant candidate or application.

drop view if exists market_skill_demand_v1;
drop view if exists market_job_listings_v1;

create table if not exists market_sources (
    source_key text primary key,
    display_name text not null,
    base_url text,
    is_enabled boolean not null default true,
    created_at timestamptz not null default now()
);

insert into market_sources (source_key, display_name, base_url)
values ('alfred', 'Alfreð', 'https://alfred.is')
on conflict (source_key) do update
set display_name = excluded.display_name,
    base_url = excluded.base_url;

create table if not exists market_job_listings (
    id bigserial primary key,
    source_key text not null references market_sources(source_key),
    source_listing_id text,
    url text not null,
    canonical_url text not null,
    title text not null,
    company text not null,
    location text,
    job_type text,
    posted_date_raw text,
    deadline_raw text,
    description text,
    is_currently_active boolean not null default true,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    last_content_hash text,
    latest_raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    check (jsonb_typeof(latest_raw_payload) = 'object'),
    check (length(trim(title)) > 0),
    check (length(trim(company)) > 0)
);

create unique index if not exists idx_market_jobs_source_external_id
    on market_job_listings (source_key, source_listing_id)
    where source_listing_id is not null;

create unique index if not exists idx_market_jobs_source_canonical_url
    on market_job_listings (source_key, canonical_url);

create index if not exists idx_market_jobs_current_status
    on market_job_listings (is_currently_active, last_seen_at desc);

create index if not exists idx_market_jobs_posted_date
    on market_job_listings (posted_date_raw);

create index if not exists idx_market_jobs_company
    on market_job_listings (company);

create table if not exists market_collection_runs (
    id bigserial primary key,
    source_key text not null references market_sources(source_key),
    discovery_method text not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    status text not null default 'running' check (
        status in ('running', 'succeeded', 'failed')
    ),
    expected_count integer,
    observed_count integer not null default 0,
    error_message text
);

create index if not exists idx_market_collection_runs_source_started
    on market_collection_runs (source_key, started_at desc);

-- One observation per listing per UTC calendar day keeps visibility history
-- compact while preserving the dataset needed for trend analysis.
create table if not exists market_job_listing_observations (
    id bigserial primary key,
    listing_id bigint not null references market_job_listings(id) on delete cascade,
    collection_run_id bigint references market_collection_runs(id) on delete set null,
    observed_on date not null,
    observed_at timestamptz not null default now(),
    discovery_method text not null,
    is_active boolean not null,
    title text not null,
    company text not null,
    location text,
    job_type text,
    posted_date_raw text,
    deadline_raw text,
    content_hash text,
    raw_payload jsonb not null default '{}'::jsonb,

    check (jsonb_typeof(raw_payload) = 'object'),
    unique (listing_id, observed_on)
);

create index if not exists idx_market_observations_date
    on market_job_listing_observations (observed_on desc, discovery_method);

create index if not exists idx_market_observations_listing
    on market_job_listing_observations (listing_id, observed_on desc);

create index if not exists idx_market_observations_run
    on market_job_listing_observations (collection_run_id);

-- Enrichment is versioned so new models or prompts never erase earlier results.
create table if not exists market_job_listing_enrichments (
    id bigserial primary key,
    listing_id bigint not null references market_job_listings(id) on delete cascade,
    extractor text not null,
    model text,
    prompt_version text,
    source_content_hash text,
    status text not null default 'succeeded' check (
        status in ('queued', 'running', 'succeeded', 'failed')
    ),
    raw_response jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    check (jsonb_typeof(raw_response) = 'object')
);

create index if not exists idx_market_enrichments_listing_created
    on market_job_listing_enrichments (listing_id, created_at desc, id desc);

create table if not exists market_skills (
    id bigserial primary key,
    name text not null,
    normalized_name text not null unique,
    dimension text not null default 'professional_skill' check (
        dimension in ('professional_skill', 'credential', 'language', 'employer_quality')
    ),
    created_at timestamptz not null default now()
);

alter table market_skills
    add column if not exists dimension text not null default 'professional_skill';

alter table market_skills
    drop constraint if exists market_skills_dimension_check;

alter table market_skills
    add constraint market_skills_dimension_check check (
        dimension in ('professional_skill', 'credential', 'language', 'employer_quality')
    );

create table if not exists market_job_listing_skill_mentions (
    enrichment_id bigint not null references market_job_listing_enrichments(id) on delete cascade,
    listing_id bigint not null references market_job_listings(id) on delete cascade,
    skill_id bigint not null references market_skills(id) on delete cascade,
    skill_kind text not null check (skill_kind in ('explicit', 'inferred')),
    importance text not null default 'mentioned' check (
        importance in ('required', 'preferred', 'mentioned')
    ),
    source_text text,
    confidence numeric(5, 4),
    created_at timestamptz not null default now(),

    primary key (enrichment_id, listing_id, skill_id),
    check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create index if not exists idx_market_skill_mentions_skill
    on market_job_listing_skill_mentions (skill_id, listing_id);

create index if not exists idx_market_skill_mentions_listing
    on market_job_listing_skill_mentions (listing_id, enrichment_id desc);

create view market_job_listings_v1 as
select
    j.id,
    j.source_key,
    s.display_name as source_name,
    j.source_listing_id,
    j.url,
    j.canonical_url,
    j.title,
    j.company,
    j.location,
    j.job_type,
    vinsyn_iso_date(j.posted_date_raw) as posted_date,
    vinsyn_iso_date(j.deadline_raw) as deadline,
    j.posted_date_raw,
    j.deadline_raw,
    j.description,
    j.is_currently_active,
    j.first_seen_at,
    j.last_seen_at,
    j.last_content_hash,
    j.created_at,
    j.updated_at
from market_job_listings j
join market_sources s on s.source_key = j.source_key;

create view market_skill_demand_v1 as
select
    sk.id as skill_id,
    sk.name,
    sk.dimension,
    count(distinct m.listing_id) as listing_count,
    count(distinct m.listing_id) filter (where j.is_currently_active)
        as active_listing_count
from market_skills sk
join market_job_listing_skill_mentions m on m.skill_id = sk.id
join market_job_listing_enrichments e on e.id = m.enrichment_id
join market_job_listings j on j.id = m.listing_id
join (
    select distinct on (listing_id) id, listing_id
    from market_job_listing_enrichments
    where status = 'succeeded'
    order by listing_id, created_at desc, id desc
) latest on latest.id = e.id
where e.status = 'succeeded'
group by sk.id, sk.name;
