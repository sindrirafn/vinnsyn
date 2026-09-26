"""Conservative location normalization for the public market snapshot.

The source location remains in the private listing table. This module exports
only a named settlement/municipality/area centroid or a non-spatial status.
Centroids are reference positions for reading a density cloud, never workplace
coordinates. The reviewed place catalog is derived from GeoNames' Iceland
gazetteer (CC BY 4.0) and kept local so exports need no geocoding service.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


CATALOG = json.loads((Path(__file__).parent / "geography_places.json").read_text())
PLACES = CATALOG["places"]
SPECIAL = [
    {"key": "remote", "label": "Remote", "kind": "remote", "lat": None, "lon": None, "region": None},
    {"key": "nationwide", "label": "Across Iceland", "kind": "nationwide", "lat": None, "lon": None, "region": None},
    {"key": "multiple", "label": "Multiple locations", "kind": "multiple", "lat": None, "lon": None, "region": None},
    {"key": "outside", "label": "Outside Iceland", "kind": "outside", "lat": None, "lon": None, "region": None},
    {"key": "unknown", "label": "Location unknown", "kind": "unknown", "lat": None, "lon": None, "region": None},
]
LOCATIONS = [{k: v for k, v in place.items() if k != "aliases"} for place in PLACES] + SPECIAL
BY_ALIAS = {
    alias.casefold(): place["key"]
    for place in PLACES
    for alias in place["aliases"]
}
OUTSIDE_MARKERS = (
    "belgium", "scotland", "sweden", "denmark", "greece", "aalborg",
    "faroe islands", "tórshavn", "noregur", "erlendis",
)


def classify_location(raw: str | None, job_type: str | None) -> str:
    value = (raw or "").strip()
    lowered = value.casefold()
    if job_type == "REMOTE" or "fjarvinna" in lowered:
        return "remote"
    if not value:
        return "unknown"
    if any(marker in lowered for marker in OUTSIDE_MARKERS):
        return "outside"
    if re.search(r"\(\+\d+\)", value):
        return "multiple"
    if lowered in {"ísland", "ísland, iceland", "iceland"}:
        return "nationwide"
    place = re.sub(r",\s*Iceland$", "", value, flags=re.I).split(";")[0].strip()
    return BY_ALIAS.get(place.casefold(), "unknown")
