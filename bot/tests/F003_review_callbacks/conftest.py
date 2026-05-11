"""
Локальные фикстуры F003.

## Трассируемость
Feature: F003 — Review callbacks
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

REVIEW_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def make_callback():
    """Factory for AsyncMock CallbackQuery with .data and .message stubs."""
    def _factory(data: str) -> AsyncMock:
        cb = AsyncMock()
        cb.from_user = MagicMock(id=42, username="op")
        cb.data = data
        cb.answer = AsyncMock()                       # ack the callback
        # .message is the bot's message with inline keyboard.
        cb.message = AsyncMock()
        cb.message.edit_reply_markup = AsyncMock()
        cb.message.answer = AsyncMock()
        return cb

    return _factory


@pytest.fixture
def fake_api_factory():
    def _make(approve_return=None, decline_return=None, edit_return=None,
              approve_exc=None, decline_exc=None, edit_exc=None) -> AsyncMock:
        api = AsyncMock()
        api.approve = AsyncMock(
            return_value=approve_return if approve_return is not None else {"status": "approved"},
            side_effect=approve_exc,
        )
        api.decline = AsyncMock(
            return_value=decline_return if decline_return is not None else {"status": "declined"},
            side_effect=decline_exc,
        )
        api.start_edit = AsyncMock(
            return_value=edit_return if edit_return is not None else {"status": "in_edit"},
            side_effect=edit_exc,
        )
        return api

    return _make
