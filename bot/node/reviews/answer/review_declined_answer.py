"""
ReviewDeclinedAnswer — bilingual подтверждение отклонения.

## Трассируемость
Feature: F003, Scenario: SC002
"""
from __future__ import annotations

from typing import Any

from core.i18n import bi
from core.vocab import REVIEW_DECLINED_EN, REVIEW_DECLINED_RU


class ReviewDeclinedAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        if event.message is not None:
            await event.message.edit_reply_markup(reply_markup=None)
        await event.message.answer(bi(REVIEW_DECLINED_RU, REVIEW_DECLINED_EN))
