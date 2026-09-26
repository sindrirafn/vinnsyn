"""Export allowlisted facts from the structured Alfreð market enrichment.

This remains a static public snapshot. It contains public advertiser labels,
but no raw listing text, personal records, or database credentials.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from vinnsyn.db import connect
from employer_normalization import build_employers
from geography import LOCATIONS, classify_location
from profession_classification import RULES, classify_profession


# Spatial order is deliberate and stable across refreshes. These are Alfreð's
# role categories, not the industries of the employers advertising the roles.
AREAS = [
    ("health-care", "Health & care", "Care, clinical and support roles"),
    ("technology", "Technology", "Software, data and IT roles"),
    ("education-research", "Education & research", "Teaching, learning and research roles"),
    ("hospitality-food", "Hospitality & food", "Food, hotels and guest services"),
    ("industrial-trades", "Industrial & trades", "Building, production and technical trades"),
    ("customer-service", "Customer service", "Customer-facing service roles"),
    ("professional-services", "Professional services", "Specialist and advisory roles"),
    ("administration", "Administration", "Office and administrative roles"),
    ("management", "Management", "Leadership and management roles"),
    ("sales-marketing", "Sales & marketing", "Commercial and marketing roles"),
    ("unclassified", "Not yet classified", "Listings without a source job area in this snapshot"),
]
ALIASES = {
    "alfred-heilbrigdisthjonusta": "health-care",
    "alfred-serfraedistorf": "professional-services",
    "alfred-solu-og-markadsstorf": "sales-marketing",
}

# These source labels are occupation names or qualifications, not capabilities.
# Keep them in the private taxonomy for profession and credential work, but do
# not present them as skills on the public map.
NON_SKILLS = {
    "Hjúkrunarfræðingur", "Verkfræðingur", "Tæknifræðingur", "Þroskaþjálfi",
    "Viðskiptafræðingur", "Félagsráðgjafi", "Sálfræðingur", "Sjúkraliði",
    "Tölvunarfræðingur", "Iðnfræðingur", "Læknir", "Hagfræðingur",
    "Skipulagsfræðingur", "Tanntæknir", "Löggiltur fasteignasali",
    "Lyfjafræðingur", "Lífeindafræðingur", "Vélstjóri", "Lyfjatæknir",
    "Byggingafræðingur", "Þjónn", "Gjaldkeri", "Kennari",
    "Meistarapróf í iðngrein", "Sveinspróf",
}

# High-confidence display translations. Shared English labels merge equivalent
# Icelandic and English evidence per listing, without double counting it.
ENGLISH_SKILLS = {
    "Microsoft Azure": "Azure",
    "Gagnagreining": "Data Analysis",
    "Eldhússtörf": "Kitchen work", "Reikningagerð": "Invoicing",
    "Húsasmíði": "Carpentry", "Almenn tæknikunnátta": "General technical skills",
    "Stefnumótun": "Strategy development", "Afgreiðsla": "Counter service",
    "Vöruflutningar": "Goods transport", "Sölumennska": "Sales",
    "Vöruframsetning": "Merchandising", "Útkeyrsla": "Delivery driving",
    "Tölvuöryggi": "Cybersecurity", "Þrif": "Cleaning",
    "Lagerstörf": "Warehouse operations", "Innleiðing ferla": "Process implementation",
    "Verkefnastjórnun": "Project Management", "Barþjónusta": "Bartending",
    "Bremsuviðgerðir": "Brake repair", "Bílarafmagnsviðgerðir": "Automotive electrical repair",
    "Bílvélaviðgerðir": "Engine repair", "Hjólbarðaþjónusta": "Tire service",
    "Smurþjónusta": "Lubrication service", "Bifvélavirkjun": "Auto mechanics",
    "Skýrslur": "Report writing", "Uppgjör": "Financial closing",
    "Birgðahald": "Inventory management", "Mannauðsstjórnun": "Human Resources",
    "Ráðningar": "Recruitment", "Viðskiptasambönd": "Customer relationships",
    "Leiðtogahæfni": "Leadership", "Áætlanagerð": "Planning",
    "Leitarvélabestun (SEO)": "SEO", "Markaðssetning á netinu": "Digital marketing",
    "Vefumsjón": "Website administration", "Opinber stjórnsýsla": "Public administration",
    "Hönnun ferla": "Process design", "Hönnun gagnagrunna": "Database design",
    "Fjárhagsáætlanagerð": "Budgeting", "Ársreikningar": "Annual financial statements",
    "Stálsmíði": "Steel fabrication", "Umsýsla gæðakerfa": "Quality management systems",
    "Áhættugreining": "Risk analysis", "Vinnsla rannsóknargagna": "Research data processing",
    "Framreiðsla": "Table service", "Email markaðssetning": "Email marketing",
    "Pípulagningar": "Plumbing", "Breytingastjórnun": "Change Management",
    "Matreiðsluiðn": "Culinary arts", "Greiningarfærni": "Analytical skills",
    "Verkefnastjórnun í upplýsingatækni": "IT Project Management",
    "Málningarvinna": "Painting", "Skyndihjálp": "First Aid",
    "Auglýsingagerð": "Advertising production",
    "Skilgreining markhópa": "Audience targeting",
}


def main() -> None:
    area_index = {key: index for index, (key, _, _) in enumerate(AREAS)}
    with connect() as connection:
        connection.execute("set transaction isolation level repeatable read read only")
        listings = connection.execute("select id, title, posted_date, location, job_type, company from market_job_listings_v1 order by id").fetchall()
        employers, employer_by_listing, employer_quality = build_employers([(row[0], row[5]) for row in listings])
        latest = """
            select distinct on (listing_id) id, listing_id
            from market_job_listing_enrichments
            where extractor = 'alfred_structured_market_taxonomy'
              and prompt_version = 'market_taxonomy_v2' and status = 'succeeded'
            order by listing_id, created_at desc, id desc
        """
        areas = connection.execute(f"""
            with latest as ({latest})
            select latest.listing_id, area.job_area_key
            from latest join market_listing_job_areas area on area.enrichment_id = latest.id
            order by latest.listing_id, area.job_area_key
        """).fetchall()
        skill_catalog = connection.execute("""
            select id, name from market_skills
            where dimension = 'professional_skill' order by id
        """).fetchall()
        mentions = connection.execute(f"""
            with latest as ({latest})
            select latest.listing_id, skill.id
            from latest
            join market_job_listing_skill_mentions mention on mention.enrichment_id = latest.id
            join market_skills skill on skill.id = mention.skill_id
            where mention.skill_kind = 'explicit' and skill.dimension = 'professional_skill'
            order by latest.listing_id, skill.id
        """).fetchall()
        profession_tags = connection.execute(f"""
            with latest as ({latest})
            select latest.listing_id, tag.name
            from latest
            join market_listing_profession_tags mention on mention.enrichment_id = latest.id
            join market_profession_tags tag on tag.id = mention.profession_tag_id
            order by latest.listing_id, tag.name
        """).fetchall()
        enriched_count = connection.execute(f"with latest as ({latest}) select count(*) from latest").fetchone()[0]

    by_listing: dict[int, set[int]] = defaultdict(set)
    for listing_id, key in areas:
        canonical = ALIASES.get(key, key)
        if canonical not in area_index:
            raise ValueError(f"Unmapped Alfreð job area: {key}")
        by_listing[listing_id].add(area_index[canonical])

    # The full catalog is exported so each field can choose its own leaders.
    # Catalog ID order keeps existing skill indices stable when new skills are
    # added in later snapshots, preserving URLs that include a skill index.
    skill_names: list[str] = []
    label_index: dict[str, int] = {}
    skill_index: dict[int, int] = {}
    for skill_id, name in skill_catalog:
        if name in NON_SKILLS:
            continue
        label = ENGLISH_SKILLS.get(name, name)
        if label not in label_index:
            label_index[label] = len(skill_names)
            skill_names.append(label)
        skill_index[skill_id] = label_index[label]
    skills_by_listing: dict[int, set[int]] = defaultdict(set)
    for listing_id, skill_id in mentions:
        if skill_id in skill_index:
            skills_by_listing[listing_id].add(skill_index[skill_id])

    tags_by_listing: dict[int, set[str]] = defaultdict(set)
    for listing_id, name in profession_tags:
        tags_by_listing[listing_id].add(name)
    profession_index = {rule.key: i for i, rule in enumerate(RULES)}
    location_index = {place["key"]: i for i, place in enumerate(LOCATIONS)}
    method_index = {"title+source_tag": 0, "title_rule": 1, "specific_source_tag": 2}
    method_counts: Counter[str] = Counter()
    location_counts: Counter[str] = Counter()

    jobs = []
    counts = Counter()
    multi_area = 0
    unclassified = area_index["unclassified"]
    for listing_id, title, date, raw_location, job_type, _company in listings:
        memberships = by_listing.get(listing_id, set())
        if len(memberships) > 1:
            multi_area += 1
        # One particle has one map position, so the first field in the stable
        # display order is used when the source supplies several categories.
        primary = min(memberships) if memberships else unclassified
        counts[primary] += 1
        profession, method = classify_profession(title or "", tags_by_listing[listing_id]) if memberships else (None, None)
        method_counts[method or "unclassified"] += 1
        location_key = classify_location(raw_location, job_type)
        location_counts[location_key] += 1
        jobs.append([listing_id, primary, date.strftime("%Y-%m") if date else None,
                     sorted(skills_by_listing.get(listing_id, ())),
                     profession_index[profession] if profession else None,
                     method_index[method] if method else None,
                     location_index[location_key], employer_by_listing[listing_id]])

    payload = {
        "schema": 5,
        "source": "Alfreð market archive",
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "categories": [name for _, name, _ in AREAS],
        "categoryDescriptions": [description for _, _, description in AREAS],
        "skills": skill_names,
        "professions": [{"key": rule.key, "label": rule.label} for rule in RULES],
        "locations": LOCATIONS,
        "employers": [{key: value for key, value in entry.items() if key != "listings"} for entry in employers],
        "employerQuality": employer_quality,
        "employerClassification": "Advertiser/brand names from Alfreð. Case, spacing and terminal punctuation are normalized; a bare name joins a single legal-suffix variant only when no competing suffix exists. Known intermediary advertisers are marked, and generic unidentified labels are grouped. Similar names, departments and historical rebrands are not inferred to be the same entity.",
        "locationClassification": "Source location strings normalized to named settlement, municipality or area centroids using a reviewed GeoNames Iceland catalog. Remote, nationwide, multiple, overseas and unknown are separate non-spatial groups. Coordinates are reference positions, never workplace addresses.",
        "professionMethods": ["title+source_tag", "title_rule", "specific_source_tag"],
        "professionClassification": "Provisional curated title rules corroborated by Alfreð profession tags where available; specific unambiguous source tags can stand alone. Raw titles and all original tags remain in the private versioned archive.",
        "enrichedListings": enriched_count,
        "multipleAreas": multi_area,
        "classification": "Alfreð source job areas; where several apply, the map assigns one primary field in stable display order. Unclassified includes listings without a source area in this snapshot.",
        "skillEvidence": "Explicit professional skills from the latest successful structured enrichment per listing; clear bilingual equivalents are merged, while occupation names and credentials are excluded from this skill view.",
        "jobs": jobs,
    }
    output = Path(__file__).resolve().parent / "web" / "data" / "market.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    temporary.replace(output)
    print(f"Exported {len(jobs):,} listings ({output.stat().st_size / 1024 / 1024:.2f} MiB)")
    print(f"Structured enrichments: {enriched_count:,}; multiple areas: {multi_area:,}")
    print("Profession assignments:", dict(method_counts))
    print("Employer identities:", employer_quality)
    print("Geographic statuses:", {key: location_counts[key] for key in ("remote", "nationwide", "multiple", "outside", "unknown")})
    print("Physical place observations:", len(jobs) - sum(location_counts[key] for key in ("remote", "nationwide", "multiple", "outside", "unknown")))
    print("Displayed fields:", {AREAS[i][1]: counts[i] for i in range(len(AREAS))})


if __name__ == "__main__":
    main()
