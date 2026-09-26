"""Parse the structured, first-party taxonomy embedded in Alfreð job pages."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Iterable

from vinnsyn.market_skills import CorpusPart, SkillMatch, alfred_skill_dimension


_NEXT_DATA_RE = re.compile(
    r'<script id=["\']__NEXT_DATA__["\'] type=["\']application/json["\']>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


@dataclass(frozen=True, slots=True)
class JobArea:
    key: str
    name: str
    display_order: int


@dataclass(frozen=True, slots=True)
class SourceCategory:
    area: JobArea
    source_category_id: str | None
    source_name: str
    source_slug: str | None


@dataclass(frozen=True, slots=True)
class ProfessionTag:
    source_tag_id: str | None
    name: str
    source_category_id: str | None


# These source categories are role families, so labels intentionally say
# "Job area" rather than attempting to infer an employer's industry.
_KNOWN_JOB_AREAS: dict[str, JobArea] = {
    "upplysingataekni": JobArea("technology", "Technology", 10),
    "idnadarstorf": JobArea("industrial-trades", "Industrial & trades", 20),
    "heilbrigdithjonusta": JobArea("health-care", "Health & care", 30),
    "kennsla-og-rannsoknir": JobArea("education-research", "Education & research", 40),
    "thjonustustorf": JobArea("customer-service", "Customer service", 50),
    "veitingastorf": JobArea("hospitality-food", "Hospitality & food", 60),
    "skrifstofustorf": JobArea("administration", "Administration", 70),
    "serfraedingastorf": JobArea("professional-services", "Professional services", 80),
    "stjornunarstorf": JobArea("management", "Management", 90),
}
_LANGUAGE_NORMALIZATION = {
    "enska": "English", "íslenska": "Icelandic", "danska": "Danish",
    "norska": "Norwegian", "sænska": "Swedish", "þýska": "German", "pólska": "Polish",
}


def clean_html(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _TextParser()
    parser.feed(html.unescape(value))
    return " ".join(parser.parts)


def alfred_job_from_html(page: str) -> dict[str, Any] | None:
    """Return Alfreð's job object, never generic page data or metadata blobs."""
    match = _NEXT_DATA_RE.search(page)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
        job = value["props"]["pageProps"]["initialJobData"]["job"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return job if isinstance(job, dict) else None


def source_categories(job: dict[str, Any]) -> list[SourceCategory]:
    values: list[SourceCategory] = []
    for category in job.get("categories", []):
        if not isinstance(category, dict) or not isinstance(category.get("name"), str):
            continue
        slug = category.get("slug") if isinstance(category.get("slug"), str) else None
        known = _KNOWN_JOB_AREAS.get(slug or "")
        area = known or JobArea(f"alfred-{slug or str(category.get('id', 'other'))}", category["name"], 999)
        values.append(SourceCategory(area, str(category["id"]) if category.get("id") is not None else None, category["name"], slug))
    return values


def profession_tags(job: dict[str, Any]) -> list[ProfessionTag]:
    values: dict[str, ProfessionTag] = {}
    for category in job.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_id = str(category["id"]) if category.get("id") is not None else None
        for tag in category.get("jobTags", []):
            if isinstance(tag, dict) and isinstance(tag.get("name"), str):
                values.setdefault(tag["name"].casefold(), ProfessionTag(
                    str(tag["id"]) if tag.get("id") is not None else None,
                    tag["name"], category_id,
                ))
    return sorted(values.values(), key=lambda value: value.name.casefold())


def structured_skill_matches(job: dict[str, Any]) -> list[SkillMatch]:
    """Import source-labelled skills and languages without lexical guessing."""
    matches: dict[tuple[str, str], SkillMatch] = {}
    for skill in job.get("skills", []):
        if not isinstance(skill, dict) or not isinstance(skill.get("name"), str):
            continue
        categories = [item.get("name", "") for item in skill.get("subCategories", []) if isinstance(item, dict)]
        dimension = alfred_skill_dimension(skill["name"], categories)
        if dimension is None:
            continue
        match = SkillMatch(skill["name"].strip(), dimension, "mentioned", "alfred:skills", skill["name"], skill["name"])
        matches[(match.name.casefold(), match.dimension)] = match
    for language in job.get("languages", []):
        if not isinstance(language, dict) or not isinstance(language.get("languageName"), str):
            continue
        source_name = language["languageName"].strip()
        name = _LANGUAGE_NORMALIZATION.get(source_name.casefold(), source_name)
        level = language.get("skillName") if isinstance(language.get("skillName"), str) else None
        evidence = f"{source_name}{f' — {level}' if level else ''}"
        match = SkillMatch(name, "language", "required" if language.get("required") else "preferred", "alfred:languages", source_name, evidence)
        matches[(match.name.casefold(), match.dimension)] = match
    return sorted(matches.values(), key=lambda value: (value.dimension, value.name.casefold()))


def job_text_parts(job: dict[str, Any]) -> list[CorpusPart]:
    """Return only job-owned prose suitable for deterministic lexical matching."""
    parts: list[CorpusPart] = []
    for key in ("description", "bodyhtml"):
        value = clean_html(job.get(key))
        if value:
            parts.append(CorpusPart(f"alfred:job:{key}", value))
    for key, source in (("jobQualifications", "alfred:qualifications"), ("jobResponsibilities", "alfred:responsibilities")):
        for item in job.get(key, []):
            value = clean_html(item.get("description")) if isinstance(item, dict) else ""
            if value:
                parts.append(CorpusPart(source, value))
    for section in job.get("customSections", []):
        if not isinstance(section, dict):
            continue
        label = section.get("label") if isinstance(section.get("label"), str) else ""
        if label not in {"qualifications", "responsibilities"}:
            continue
        value = clean_html(section.get("content"))
        if value:
            parts.append(CorpusPart(f"alfred:custom:{label}", value))
    return parts


def merge_skill_matches(*groups: Iterable[SkillMatch]) -> list[SkillMatch]:
    """Prefer source-labelled evidence over lexical matches for one skill."""
    found: dict[tuple[str, str], SkillMatch] = {}
    for group in groups:
        for match in group:
            key = (match.name.casefold(), match.dimension)
            existing = found.get(key)
            if existing is None or match.source.startswith("alfred:"):
                found[key] = match
    return sorted(found.values(), key=lambda value: (value.dimension, value.name.casefold()))
