"""
Глобальные фикстуры для бота.

## Бизнес-контекст
Бот = UI-слой. Тесты не поднимают реальный aiogram-Bot и не делают
сетевых вызовов. Используем AsyncMock для message/state и патчим
RendersAPI на уровне импорта в Code-нодах.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make bot/ importable without installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def mock_state() -> AsyncMock:
    state = AsyncMock()
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.set_data = AsyncMock()
    state.update_data = AsyncMock()
    return state


@pytest.fixture
def make_message():
    """Factory: returns a fresh AsyncMock message with the given .text."""
    def _factory(text: str = "/start", user_id: int = 12345) -> AsyncMock:
        msg = AsyncMock()
        msg.from_user = MagicMock(id=user_id, username="op")
        msg.text = text
        msg.answer = AsyncMock()
        return msg

    return _factory
