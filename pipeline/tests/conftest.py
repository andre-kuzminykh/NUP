"""Shared fixtures.

Tests are split into:
- unit/ — pure, no I/O (must always run, fast).
- integration/ — require real ffmpeg or testcontainers.
- e2e/ — full FastAPI round-trip with overridden ports (no real services).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

# Make `src/` importable without installing the package.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_collection_modifyitems(config, items):
    """Skip integration tests requiring ffmpeg if it's missing."""
    if shutil.which("ffmpeg") is None:
        skip_marker = pytest.mark.skip(reason="ffmpeg not installed")
        for item in items:
            if "integration" in str(item.fspath) and "ffmpeg" in item.name:
                item.add_marker(skip_marker)
