"""
ReviewEditCancelledAnswer — вышли из edit-mode обратно в pending.

## Трассируемость
Feature: F003 — Review callbacks (edit mode cancel)
"""
from __future__ import annotations

from typing import Any


def _initial_kb(review_id: str) -> dict:
    """Главная клавиатура: 🔁 Перегенерировать сверху + 3 в ряд снизу."""
    return {
        "inline_keyboard": [
            [{"text": "🔁 Перегенерировать",
              "callback_data": f"review:regenerate:{review_id}"}],
            [
                {"text": "❌ Отклонить",
                 "callback_data": f"review:decline:{review_id}"},
                {"text": "✏️ Редактировать",
                 "callback_data": f"review:edit:{review_id}"},
                {"text": "✅ Принять",
                 "callback_data": f"review:approve:{review_id}"},
            ],
        ]
    }


class ReviewEditCancelledAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        review_id = data.get("review_id", "")
        # Возвращаем оригинальный caption (без edit-mode счётчиков),
        # чтобы оператор видел заголовок новости + ссылку.
        caption = data.get("caption") or ""
        try:
            if caption:
                await event.message.edit_caption(
                    caption=caption,
                    reply_markup=_initial_kb(review_id),
                    parse_mode="Markdown",
                )
            else:
                await event.message.edit_reply_markup(
                    reply_markup=_initial_kb(review_id),
                )
        except Exception:
            try:
                await event.message.edit_reply_markup(reply_markup=_initial_kb(review_id))
            except Exception:
                pass
