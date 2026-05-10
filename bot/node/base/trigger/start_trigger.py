"""
StartTrigger — обработка входа в /start.

## Трассируемость
Feature: F001 — Welcome and main menu
Scenario: SC001

## Бизнес-контекст
Сбрасывает FSM-состояние пользователя (BR001) и подготавливает
данные для Code-ноды.
"""
from __future__ import annotations

from typing import Any


class StartTrigger:
    async def run(self, message: Any, state: Any) -> dict:
        await state.clear()
        return {"user_id": message.from_user.id}
