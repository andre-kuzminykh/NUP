"""
ReviewInvalidAnswer — невалидный/устаревший callback.

## Трассируемость
Feature: F003, Scenario: SC004
"""
from __future__ import annotations

from typing import Any

from core.i18n import bi
from core.vocab import REVIEW_INVALID_EN, REVIEW_INVALID_RU


class ReviewInvalidAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        # Inline-клавиатуру не трогаем — может ошибка пользователя, а не системы.
        await event.message.answer(bi(REVIEW_INVALID_RU, REVIEW_INVALID_EN))
