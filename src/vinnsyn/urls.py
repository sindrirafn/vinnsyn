"""Public-listing URL identity helpers."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonicalize_url(url: str) -> str:
    """Normalize the known harmless variants of a public listing URL."""
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return url.strip()
    netloc = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parts.path).rstrip("/")
    if netloc == "alfred.is":
        path = re.sub(r"^/(en|is|uk|pl)(?=/starf/)", "", path, flags=re.IGNORECASE)
    query = urlencode([
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "msclkid"}
    ], doseq=True)
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))
