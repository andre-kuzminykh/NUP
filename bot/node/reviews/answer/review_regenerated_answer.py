"""
ReviewRegeneratedAnswer — бэкенд завершил полную пересборку видео.

## Трассируемость
Feature: F003 — Review callbacks (regenerate)

## Бизнес-контекст
К моменту, когда бот получает payload, бэкенд уже:
  1. Заново прогнал summary → voiceover → TTS → keywords → search → ffmpeg.
  2. Заменил видео в сообщении оператора через editMessageMedia.
  3. Поставил новый caption + главную клавиатуру.

Бот тут просто no-op — Telegram уже всё показал. Но на всякий случай
переуставим caption + клавиатуру (Idempotent).
"""
from __future__ import annotations

from typing import Any

from node.reviews.answer.review_edit_cancelled_answer import _initial_kb


class ReviewRegeneratedAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        review_id = data.get("review_id", "")
        caption = data.get("caption") or ""
        try:
            if caption:
                await event.message.edit_caption(
                    caption=caption,
                    reply_markup=_initial_kb(review_id),
                    parse_mode="Markdown",
                )
            else:
                await event.message.edit_reply_markup(reply_markup=_initial_kb(review_id))
        except Exception:
            pass
