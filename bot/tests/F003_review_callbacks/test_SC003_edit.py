"""
Тест SC003 — Edit callback.

## Трассируемость
Feature: F003, Scenario: SC003

## BDD
Given: preview-сообщение с кнопкой "✏️ Edit / Править"
When:  callback_data='review:edit:<id>'
Then:  бэкенд получил start_edit(id); оператор увидел bilingual сообщение,
       что режим включён (полный UI кадров — в следующей итерации, F013).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.reviews.F003.review_callback_widget import handle_review_callback
from tests.F003_review_callbacks.conftest import REVIEW_ID


@pytest.mark.asyncio
async def test_edit_starts_session_and_acks_bilingual(
    make_callback, mock_state, fake_api_factory
) -> None:
    cb = make_callback(f"review:edit:{REVIEW_ID}")
    fake_api = fake_api_factory(edit_return={"status": "in_edit", "cursor": 0, "total": 3})
    with patch(
        "node.reviews.code.review_callback_code.ReviewsAPI",
        return_value=fake_api,
    ):
        await handle_review_callback(cb, mock_state)
    fake_api.start_edit.assert_awaited_once_with(REVIEW_ID)
    fake_api.approve.assert_not_awaited()
    fake_api.decline.assert_not_awaited()
    text = cb.message.answer.call_args.args[0]
    assert "редактирования" in text.lower() or "редактор" in text.lower()
    assert "edit" in text.lower()
