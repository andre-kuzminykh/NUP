"""
ReviewBackendErrorAnswer — backend упал не по 404.

## Трассируемость
Feature: F003 — Review callbacks
"""
from __future__ import annotations

from typing import Any

from core.i18n import bi
from core.vocab import REVIEW_BACKEND_ERROR_EN, REVIEW_BACKEND_ERROR_RU


class ReviewBackendErrorAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        base = bi(REVIEW_BACKEND_ERROR_RU, REVIEW_BACKEND_ERROR_EN)
        # Прокидываем детали из api, иначе оператор только и видит «бэкенд
        # не отвечает» и не понимает где разбираться.
        detail = (data or {}).get("error") or ""
        if detail:
            await event.message.answer(f"{base}\n\n`{detail[:300]}`", parse_mode="Markdown")
        else:
            await event.message.answer(base)
