"""Conservative public identities for Alfreð advertiser names.

The source exposes one company/brand string, not a verified legal entity or
ultimate hiring employer. Keep the raw value in the private listing archive.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict

LEGAL_SUFFIXES = {"ehf", "hf", "sf", "slf", "bs", "ses"}

# These are descriptions rather than identifiable organizations in the archive.
UNIDENTIFIED = {
    "fyrirtæki á höfuðborgarsvæðinu",
    "fjármála- og fasteignafyrirtæki",
    "fjárfestinga- og fasteignafyrirtæki í 101 reykjavík",
    "aðstoð óskast",
    "aðstoðarfólk óskast",
    "aðstoðarmaður óskast",
    "persónulegt aðstoðarfólk óskast",
    "unknown company",
}

# Source names known to advertise recruitment for clients. Other agencies may
# still exist; this is a disclosure marker, not an entity-resolution claim.
INTERMEDIARIES = {
    "alfreð", "alfreð starfsmannaleit", "hagvangur", "intellecta",
    "ceek recruitment solutions",
}


def clean_name(value: str | None) -> str:
    """Normalize only typography that cannot distinguish an organization."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip().rstrip("., ")


def folded(value: str | None) -> str:
    return clean_name(value).casefold()


def legal_root(value: str) -> tuple[str, str | None]:
    base, separator, suffix = value.rpartition(" ")
    return (base, suffix) if separator and suffix in LEGAL_SUFFIXES else (value, None)


def public_key(value: str) -> str:
    stem = re.sub(r"[^\w]+", "-", value, flags=re.UNICODE).strip("-")[:66] or "employer"
    digest = hashlib.blake2s(value.encode("utf-8"), digest_size=4).hexdigest()
    return f"{stem}-{digest}"


def build_employers(rows: list[tuple[int, str | None]]) -> tuple[list[dict], dict[int, str], dict]:
    raw_counts = Counter(name or "" for _, name in rows)
    folded_counts = Counter(folded(name) for _, name in rows)
    suffixes: dict[str, set[str]] = defaultdict(set)
    for name in folded_counts:
        root, suffix = legal_root(name)
        if suffix:
            suffixes[root].add(suffix)

    def identity(name: str | None) -> str:
        value = folded(name)
        if not value or value in UNIDENTIFIED:
            return "unidentified"
        root, suffix = legal_root(value)
        # A bare name is joined to one suffixed form only. Two distinct legal
        # suffixes, and names with no bare counterpart, remain separate.
        if suffix and root in folded_counts and len(suffixes[root]) == 1:
            return root
        return value

    groups: dict[str, Counter[str]] = defaultdict(Counter)
    by_listing: dict[int, str] = {}
    for listing_id, raw in rows:
        group = identity(raw)
        groups[group][clean_name(raw)] += 1
        by_listing[listing_id] = public_key(group)

    employers = []
    for group, aliases in groups.items():
        kind = "unidentified" if group == "unidentified" else "intermediary" if group in INTERMEDIARIES else "advertiser"
        label = "Employer not identified" if kind == "unidentified" else sorted(aliases, key=lambda name: (-aliases[name], name.casefold()))[0]
        employers.append({"key": public_key(group), "label": label, "kind": kind, "sourceNames": sorted(aliases), "listings": sum(aliases.values())})
    employers.sort(key=lambda entry: (-entry["listings"], entry["label"].casefold()))
    stats = {
        "sourceField": "market_job_listings_v1.company (Alfreð brand/advertiser)",
        "rawDistinct": len(raw_counts),
        "normalizedDistinct": len(employers),
        "missingSourceNames": sum(not clean_name(name) for _, name in rows),
        "unidentifiedListings": groups["unidentified"].total() if "unidentified" in groups else 0,
        "intermediaryListings": sum(entry["listings"] for entry in employers if entry["kind"] == "intermediary"),
        "rawSingletonNames": sum(count == 1 for count in raw_counts.values()),
    }
    return employers, by_listing, stats
