"""
ReviewEditCancelledAnswer — вышли из edit-mode обратно в pending.

## Трассируемость
Feature: F003 — Review callbacks (edit mode cancel)
"""
from __future__ import annotations

from typing import Any


def _initial_kb(review_id: str) -> dict:
    """Снова те же 3 кнопки, что были при первом appearance видео."""
    return {
        "inline_keyboard": [
            [{"text": "✅ Опубликовать", "callback_data": f"review:approve:{review_id}"}],
            [{"text": "✏️ Редактировать", "callback_data": f"review:edit:{review_id}"}],
            [{"text": "❌ Отклонить", "callback_data": f"review:decline:{review_id}"}],
        ]
    }


class ReviewEditCancelledAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        review_id = data.get("review_id", "")
        try:
            await event.message.edit_reply_markup(reply_markup=_initial_kb(review_id))
        except Exception:
            pass
