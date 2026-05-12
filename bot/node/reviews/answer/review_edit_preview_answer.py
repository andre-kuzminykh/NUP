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

import logging
from typing import Any

from aiogram.types import InputMediaVideo

log = logging.getLogger("review_edit_preview")


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
                {"text": "🔄 Найти ещё",
                 "callback_data": f"edit:{review_id}:refresh"},
            ],
            [
                {"text": "💾 Сохранить",
                 "callback_data": f"edit:{review_id}:save"},
            ],
            [
                {"text": "↩️ Отмена",
                 "callback_data": f"edit:{review_id}:cancel"},
            ],
        ]
    }


def _caption(p: dict) -> str:
    seg_text = (p.get("segment_text") or "").strip()
    preview_url = p.get("active_preview_url") or p.get("active_video_url") or ""
    preview_line = f"\n[👁 Посмотреть клип]({preview_url})" if preview_url else ""
    return (
        f"✏️ *Редактирование*\n"
        f"Кадр *{p.get('cursor', 0) + 1}/{p.get('total', 0)}*: "
        f"_{seg_text[:200]}_\n"
        f"Клип *{p.get('candidate_idx', 0) + 1}/{p.get('candidate_total', 0)}*"
        f"{preview_line}"
    )


class ReviewEditPreviewAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        review_id = data.get("review_id", "")
        kb = _kb(review_id)
        caption = _caption(data)
        msg = event.message
        # Если на кандидате есть file_id — подменяем САМО видео (instant,
        # т.к. Telegram уже хранит mp4). Иначе fallback на caption-only.
        file_id = data.get("active_file_id")
        if file_id:
            try:
                await msg.edit_media(
                    InputMediaVideo(
                        media=file_id,
                        caption=caption,
                        parse_mode="Markdown",
                    ),
                    reply_markup=kb,
                )
                return
            except Exception as e:
                log.warning("edit_media failed: %s; falling back to caption-only", e)
        try:
            await msg.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            try:
                await msg.edit_reply_markup(reply_markup=kb)
            except Exception:
                pass
