"""F08 — subtitle chunking rule.

Traces: REQ-F08-005, REQ-F08-012.
"""
import pytest

from nup_pipeline.domain.segment import chunk_subtitle


@pytest.mark.unit
@pytest.mark.req("REQ-F08-012")
@pytest.mark.parametrize(
    "text, expected",
    [
        ("", [""]),
        ("hello", ["hello"]),
        ("one two three", ["one two three"]),
        ("one two three four", ["one two three", "four"]),
        ("a b c d e f g", ["a b c", "d e f", "g"]),
    ],
)
def test_chunk_three_words(text: str, expected: list[str]) -> None:
    assert chunk_subtitle(text, n=3) == expected


@pytest.mark.unit
@pytest.mark.req("REQ-F08-012")
def test_chunk_strips_extra_whitespace() -> None:
    assert chunk_subtitle("  one   two\tthree   four  ", n=3) == ["one two three", "four"]
