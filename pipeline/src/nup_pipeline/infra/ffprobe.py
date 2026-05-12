"""Тонкая обёртка над ffprobe — узнать длительность медиафайла в секундах."""
from __future__ import annotations

import json
import subprocess


def probe_duration_sec(path: str) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", path,
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])
