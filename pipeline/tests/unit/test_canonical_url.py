"""F001 — URL canonicalization for deduplication.

Traces: REQ-F01-006.
"""
import pytest

from nup_pipeline.infra.canonical import canonical_url


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
@pytest.mark.parametrize(
    "given, expected",
    [
        ("https://Example.com/Path", "https://example.com/Path"),
        ("https://example.com/a?utm_source=foo&id=1", "https://example.com/a?id=1"),
        ("https://example.com/a?utm_medium=x&utm_campaign=y", "https://example.com/a"),
        ("https://example.com/a#fragment", "https://example.com/a"),
        ("https://example.com/a?fbclid=Z&id=2", "https://example.com/a?id=2"),
        ("  https://example.com/a\n", "https://example.com/a"),
        ("HTTPS://EXAMPLE.com/path?a=1&b=2", "https://example.com/path?a=1&b=2"),
    ],
    ids=[
        "host-lowercase",
        "drop-utm-keep-others",
        "drop-all-utm",
        "drop-fragment",
        "drop-fbclid",
        "trim-whitespace",
        "scheme-lowercase",
    ],
)
def test_canonical_url(given: str, expected: str) -> None:
    assert canonical_url(given) == expected


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_canonical_is_idempotent() -> None:
    a = canonical_url("https://Example.com/a?utm_source=x&id=1#frag")
    b = canonical_url(a)
    assert a == b
