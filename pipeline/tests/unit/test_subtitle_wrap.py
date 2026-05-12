"""F008 — subtitle wrap (max 22 chars per line)."""
import pytest

from nup_pipeline.services.ffmpeg_builder import _wrap_chunk


@pytest.mark.unit
@pytest.mark.parametrize(
    "src, expected",
    [
        ("hello", "hello"),
        ("a b c", "a b c"),
        # 22 chars exactly → no wrap
        ("проектирование система", "проектирование система"),
    ],
    ids=["short", "tiny", "boundary"],
)
def test_short_chunks_unchanged(src: str, expected: str) -> None:
    assert _wrap_chunk(src, max_chars=22) == expected


@pytest.mark.unit
def test_long_chunk_wraps_at_nearest_space_to_middle() -> None:
    src = "this is a much longer line that must wrap"
    out = _wrap_chunk(src, max_chars=22)
    assert "\n" in out
    lines = out.split("\n")
    assert len(lines) == 2
    # both lines reasonably short
    assert max(len(line) for line in lines) <= len(src) // 2 + 5


@pytest.mark.unit
def test_single_long_word_returned_as_is() -> None:
    # No space — cannot wrap. Should return original (drawtext will overflow,
    # but better than crashing).
    src = "supercalifragilisticexpialidocious"
    assert _wrap_chunk(src, max_chars=10) == src
