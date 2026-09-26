-- Structured market taxonomy.
--
-- Alfreð's categories describe a role's job area, not necessarily its
-- employer's business sector. Keep those source classifications relational and
-- versioned, alongside profession tags and dimensioned skills.

drop view if exists market_profession_demand_v1;
drop view if exists market_job_area_demand_v1;

-- These columns were introduced before the listing-page document archive.
-- requirements is empty in every market row; application_url is always url.
alter table market_job_listings drop column if exists requirements;
alter table market_job_listings drop column if exists application_url;

create table if not exists market_job_areas (
    key text primary key,
    name text not null,
    display_order integer not null default 999,
    created_at timestamptz not null default now(),
    check (key = lower(key))
);

create table if not exists market_listing_job_areas (
    enrichment_id bigint not null references market_job_listing_enrichments(id) on delete cascade,
    listing_id bigint not null references market_job_listings(id) on delete cascade,
    job_area_key text not null references market_job_areas(key),
    source_category_id text,
    source_name text not null,
    source_slug text,
    confidence numeric(5, 4) not null default 1.0 check (confidence between 0 and 1),
    created_at timestamptz not null default now(),
    primary key (enrichment_id, listing_id, job_area_key)
);

create index if not exists idx_market_listing_job_areas_listing
    on market_listing_job_areas (listing_id, enrichment_id desc);

create table if not exists market_profession_tags (
    id bigserial primary key,
    source_key text not null references market_sources(source_key),
    source_tag_id text,
    name text not null,
    normalized_name text not null,
    created_at timestamptz not null default now(),
    unique (source_key, normalized_name)
);

create table if not exists market_listing_profession_tags (
    enrichment_id bigint not null references market_job_listing_enrichments(id) on delete cascade,
    listing_id bigint not null references market_job_listings(id) on delete cascade,
    profession_tag_id bigint not null references market_profession_tags(id) on delete cascade,
    source_category_id text,
    confidence numeric(5, 4) not null default 1.0 check (confidence between 0 and 1),
    created_at timestamptz not null default now(),
    primary key (enrichment_id, listing_id, profession_tag_id)
);

create index if not exists idx_market_profession_mentions_listing
    on market_listing_profession_tags (listing_id, enrichment_id desc);

create view market_job_area_demand_v1 as
select area.key, area.name,
       count(distinct mention.listing_id) as listing_count,
       count(distinct mention.listing_id) filter (where listing.is_currently_active) as active_listing_count
from market_job_areas area
join market_listing_job_areas mention on mention.job_area_key = area.key
join market_job_listings listing on listing.id = mention.listing_id
join (
    select distinct on (listing_id) id, listing_id
    from market_job_listing_enrichments
    where status = 'succeeded'
    order by listing_id, created_at desc, id desc
) latest on latest.id = mention.enrichment_id
group by area.key, area.name;

create view market_profession_demand_v1 as
select tag.id as profession_tag_id, tag.name,
       count(distinct mention.listing_id) as listing_count,
       count(distinct mention.listing_id) filter (where listing.is_currently_active) as active_listing_count
from market_profession_tags tag
join market_listing_profession_tags mention on mention.profession_tag_id = tag.id
join market_job_listings listing on listing.id = mention.listing_id
join (
    select distinct on (listing_id) id, listing_id
    from market_job_listing_enrichments
    where status = 'succeeded'
    order by listing_id, created_at desc, id desc
) latest on latest.id = mention.enrichment_id
group by tag.id, tag.name;
