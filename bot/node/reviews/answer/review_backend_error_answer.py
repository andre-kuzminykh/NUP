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
        await event.message.answer(bi(REVIEW_BACKEND_ERROR_RU, REVIEW_BACKEND_ERROR_EN))
