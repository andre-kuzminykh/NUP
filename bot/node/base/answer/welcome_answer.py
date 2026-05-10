"""
WelcomeAnswer — отрисовывает приветственный экран.

## Трассируемость
Feature: F001 — Welcome and main menu
Scenario: SC001
"""
from __future__ import annotations

from typing import Any

from core.vocab import WELCOME


class WelcomeAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        await event.answer(WELCOME)
