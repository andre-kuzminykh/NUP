"""URL canonicalization for article deduplication (REQ-F01-006).

Rules:
- scheme and host lowercased;
- strip whitespace;
- drop URL fragment;
- drop tracking query params: utm_*, fbclid, gclid, yclid, ref, source;
- preserve other query params in original order.

Tested by tests/unit/test_canonical_url.py.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset({"fbclid", "gclid", "yclid", "ref", "source"})


def canonical_url(url: str) -> str:
    p = urlparse(url.strip())
    scheme = p.scheme.lower()
    host = p.netloc.lower()
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    return urlunparse((scheme, host, p.path, "", urlencode(query), ""))
