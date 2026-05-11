"""
Тест SC004 — невалидный/неизвестный callback не вызывает бэкенд.

## Трассируемость
Feature: F003, Scenario: SC004

## BDD
Given: пользователь нажал кнопку из старого/чужого сообщения, либо что-то
       сгенерировало payload неправильного формата
When:  callback_data='review:foo:bar' или 'garbage'
Then:  бэкенд не вызывался ни по одной из ручек; bilingual «Unknown action».
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.reviews.F003.review_callback_widget import handle_review_callback


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        "review:foo:bar",
        "review:approve",         # missing review_id
        "garbage",                # missing prefix entirely shouldn't even reach here, but defensive
        "review::",
    ],
    ids=["unknown_action", "missing_id", "no_prefix", "empty_parts"],
)
async def test_malformed_callbacks_dont_call_backend(
    make_callback, mock_state, fake_api_factory, data
) -> None:
    cb = make_callback(data)
    fake_api = fake_api_factory()
    with patch(
        "node.reviews.code.review_callback_code.ReviewsAPI",
        return_value=fake_api,
    ):
        await handle_review_callback(cb, mock_state)
    fake_api.approve.assert_not_awaited()
    fake_api.decline.assert_not_awaited()
    fake_api.start_edit.assert_not_awaited()
    text = cb.message.answer.call_args.args[0]
    assert "Unknown" in text or "Неизвестное" in text
