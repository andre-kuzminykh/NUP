"""
RenderInvalidUuidAnswer — пользователь дал невалидный UUID.

## Трассируемость
Feature: F002, Scenario: SC003
"""
from __future__ import annotations

from typing import Any

from core.vocab import RENDER_INVALID_UUID


class RenderInvalidUuidAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        await event.answer(RENDER_INVALID_UUID)
