"""Segment value object and subtitle chunking rule (F08).

Tested by:
- tests/unit/test_subtitle_chunking.py  (REQ-F08-012)
- tests/unit/test_ffmpeg_builder.py     (REQ-F08-005, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    audio_uri: str
    video_uri: str
    audio_duration_sec: float
    subtitle_text: str = ""


def chunk_subtitle(text: str, n: int = 3) -> list[str]:
    """Split subtitle text into chunks of `n` words each.

    Empty input → exactly one empty chunk so that downstream timing logic
    (length / max(len(chunks), 1)) stays well-defined.
    """
    words = text.split()
    if not words:
        return [""]
    return [" ".join(words[i : i + n]) for i in range(0, len(words), n)]
