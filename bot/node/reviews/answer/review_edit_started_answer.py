"""
ReviewEditStartedAnswer — заглушка перед полноценным edit-mode (F013).

## Трассируемость
Feature: F003, Scenario: SC003
"""
from __future__ import annotations

from typing import Any

from core.i18n import bi
from core.vocab import REVIEW_EDIT_STARTED_EN, REVIEW_EDIT_STARTED_RU


class ReviewEditStartedAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        if event.message is not None:
            await event.message.edit_reply_markup(reply_markup=None)
        await event.message.answer(bi(REVIEW_EDIT_STARTED_RU, REVIEW_EDIT_STARTED_EN))
