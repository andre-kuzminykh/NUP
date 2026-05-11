"""
ReviewApprovedAnswer — bilingual подтверждение публикации.

## Трассируемость
Feature: F003, Scenario: SC001
"""
from __future__ import annotations

from typing import Any

from core.i18n import bi
from core.vocab import REVIEW_APPROVED_EN, REVIEW_APPROVED_RU


class ReviewApprovedAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        # Убираем inline-клавиатуру с исходного сообщения, чтобы оператор
        # не нажал кнопку повторно.
        if event.message is not None:
            await event.message.edit_reply_markup(reply_markup=None)
        await event.message.answer(bi(REVIEW_APPROVED_RU, REVIEW_APPROVED_EN))
