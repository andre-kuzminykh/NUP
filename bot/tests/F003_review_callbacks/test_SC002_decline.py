"""
Тест SC002 — Decline callback.

## Трассируемость
Feature: F003, Scenario: SC002

## BDD
Given: preview-сообщение с кнопкой "❌ Decline / Отклонить"
When:  callback_data='review:decline:<id>'
Then:  бэкенд получил decline(id); approve НЕ вызывался; клавиатура убрана;
       bilingual ответ с RU+EN.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.reviews.F003.review_callback_widget import handle_review_callback
from tests.F003_review_callbacks.conftest import REVIEW_ID


@pytest.mark.asyncio
async def test_decline_calls_backend_and_replies_bilingual(
    make_callback, mock_state, fake_api_factory
) -> None:
    cb = make_callback(f"review:decline:{REVIEW_ID}")
    fake_api = fake_api_factory()
    with patch(
        "node.reviews.code.review_callback_code.ReviewsAPI",
        return_value=fake_api,
    ):
        await handle_review_callback(cb, mock_state)
    fake_api.decline.assert_awaited_once_with(REVIEW_ID)
    fake_api.approve.assert_not_awaited()
    cb.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    text = cb.message.answer.call_args.args[0]
    assert "Отклонено" in text
    assert "Declined" in text
