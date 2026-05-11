"""
Тест SC003 — невалидный UUID → 'UUID' в ответе и backend не вызывается.

## Трассируемость
Feature: F002 — Render job status
Scenario: SC003 — Non-UUID input
Business rule: BR001

## BDD
Given: пользователь открыл чат
When:  пользователь отправил `/render_status not-a-uuid`
Then:  бот ответил сообщением, упоминающим 'UUID'
And:   backend не был вызван
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.renders.F002.render_status_widget import handle_render_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "argument",
    ["not-a-uuid", "", "12345", "abc-def"],
    ids=["string", "empty", "digits", "dashed-non-uuid"],
)
async def test_invalid_uuid_short_circuits(
    make_message, mock_state, fake_api_factory, argument
) -> None:
    # Given
    msg = make_message(f"/render_status {argument}".strip())
    fake_api = fake_api_factory()

    # When
    with patch(
        "node.renders.code.render_status_code.RendersAPI",
        return_value=fake_api,
    ):
        await handle_render_status(msg, mock_state)

    # Then
    fake_api.get.assert_not_awaited()
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.call_args.args[0]
    assert "UUID" in sent_text or "uuid" in sent_text
