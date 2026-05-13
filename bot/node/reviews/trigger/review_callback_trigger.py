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
        data = callback.data or ""
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "review":
            try:
                await callback.answer()
            except Exception:
                pass
            return {"action": None, "review_id": None, "raw": data}
        _, action, review_id = parts
        # «Перегенерировать» — долгая операция, шлём оператору тост заранее.
        toast = "🔁 Перегенерирую видео… (~3-5 мин)" if action == "regenerate" else ""
        try:
            await callback.answer(text=toast or "", show_alert=False)
        except Exception:
            pass
        return {"action": action, "review_id": review_id, "raw": data}
