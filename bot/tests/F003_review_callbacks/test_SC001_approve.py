"""
Тест SC001 — Approve callback.

## Трассируемость
Feature: F003 — Review callbacks
Scenario: SC001 — Approve

## BDD
Given: оператор видит preview-сообщение с кнопкой "✅ Approve / Одобрить"
When:  оператор нажал кнопку, callback_data='review:approve:<id>'
Then:  бэкенд получил approve(id); inline-клавиатура убрана; оператору
       отправлено bilingual подтверждение, содержащее RU и EN текст.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.reviews.F003.review_callback_widget import handle_review_callback
from tests.F003_review_callbacks.conftest import REVIEW_ID


@pytest.mark.asyncio
async def test_approve_removes_keyboard_and_replies_bilingual(
    make_callback, mock_state, fake_api_factory
) -> None:
    # Given
    cb = make_callback(f"review:approve:{REVIEW_ID}")
    fake_api = fake_api_factory()

    # When
    with patch(
        "node.reviews.code.review_callback_code.ReviewsAPI",
        return_value=fake_api,
    ):
        await handle_review_callback(cb, mock_state)

    # Then
    cb.answer.assert_awaited_once()  # callback ack
    fake_api.approve.assert_awaited_once_with(REVIEW_ID)
    cb.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    cb.message.answer.assert_awaited_once()
    sent_text = cb.message.answer.call_args.args[0]
    # Bilingual: must contain both RU and EN phrases.
    assert "Опубликовано" in sent_text
    assert "Published" in sent_text
