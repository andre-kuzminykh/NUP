"""
ReviewEditPreviewAnswer — главный экран edit-mode.

## Трассируемость
Feature: F003 — Review callbacks (edit mode)
Scenarios: SC003 (frame nav), SC004 (clip nav)

## UI
Caption обновляется на текущее состояние, inline-keyboard:

  Кадр 1/5: «текст сегмента»
  Клип 2/3

  ──────────────
  [◀ Кадр]  [Кадр ▶]
  [◀ Клип]  [Клип ▶]
  [✅ Опубликовать]
  [❌ Отклонить]

Кнопка ✏️ убрана — мы уже в edit-mode.
"""
from __future__ import annotations

from typing import Any


def _kb(review_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "◀ Кадр",   "callback_data": f"edit:{review_id}:frame_prev"},
                {"text": "Кадр ▶",   "callback_data": f"edit:{review_id}:frame_next"},
            ],
            [
                {"text": "◀ Клип",   "callback_data": f"edit:{review_id}:clip_prev"},
                {"text": "Клип ▶",   "callback_data": f"edit:{review_id}:clip_next"},
            ],
            [
                {"text": "✅ Опубликовать",
                 "callback_data": f"edit:{review_id}:approve"},
            ],
            [
                {"text": "❌ Отклонить",
                 "callback_data": f"edit:{review_id}:decline"},
            ],
        ]
    }


def _caption(p: dict) -> str:
    seg_text = (p.get("segment_text") or "").strip()
    return (
        f"✏️ *Редактирование*\n"
        f"Кадр *{p.get('cursor', 0) + 1}/{p.get('total', 0)}*: "
        f"_{seg_text[:200]}_\n"
        f"Клип *{p.get('candidate_idx', 0) + 1}/{p.get('candidate_total', 0)}*"
    )


class ReviewEditPreviewAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        review_id = data.get("review_id", "")
        kb = _kb(review_id)
        caption = _caption(data)
        msg = event.message
        # Меняем caption (под видео) + новую keyboard. Если caption тот же,
        # Telegram вернёт 400 — игнорируем.
        try:
            await msg.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            # Caption может быть identical → 400. Хоть kb обновим.
            try:
                await msg.edit_reply_markup(reply_markup=kb)
            except Exception:
                pass
