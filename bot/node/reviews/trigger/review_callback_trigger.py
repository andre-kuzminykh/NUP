"""
ReviewCallbackTrigger — парсит callback_data вида review:{action}:{id}.

## Трассируемость
Feature: F003 — Review callbacks
Scenarios: SC001, SC002, SC003, SC004 (malformed)

## Бизнес-контекст
Trigger делает только разбор входа + acknowledge нажатия (callback.answer()),
чтобы Telegram убрал «часики» с кнопки. Решение «что делать» — в Code.
"""
from __future__ import annotations

from typing import Any


class ReviewCallbackTrigger:
    async def run(self, callback: Any, state: Any) -> dict:
        # Acknowledge the callback so the spinner goes away immediately.
        await callback.answer()

        data = callback.data or ""
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "review":
            return {"action": None, "review_id": None, "raw": data}
        _, action, review_id = parts
        return {"action": action, "review_id": review_id, "raw": data}
