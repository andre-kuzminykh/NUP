"""
Локальные фикстуры F002.

## Трассируемость
Feature: F002 — Render job status
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

UUID_OK = "11111111-2222-3333-4444-555555555555"
UUID_UNKNOWN = "99999999-9999-9999-9999-999999999999"


@pytest.fixture
def fake_api_factory():
    """Returns a callable that builds an AsyncMock API with a configured behaviour."""
    def _make(get_return=None, get_side_effect=None) -> AsyncMock:
        api = AsyncMock()
        api.get = AsyncMock(return_value=get_return, side_effect=get_side_effect)
        return api

    return _make
