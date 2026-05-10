"""
RenderNotFoundAnswer — backend вернул 404.

## Трассируемость
Feature: F002, Scenario: SC002
"""
from __future__ import annotations

from typing import Any

from core.vocab import RENDER_NOT_FOUND


class RenderNotFoundAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        await event.answer(RENDER_NOT_FOUND)
