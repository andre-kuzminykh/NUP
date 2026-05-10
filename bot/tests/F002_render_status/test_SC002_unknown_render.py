"""
Тест SC002 — backend 404 → 'не найден'.

## Трассируемость
Feature: F002 — Render job status
Scenario: SC002 — Unknown render id

## BDD
Given: backend возвращает 404 для UUID_UNKNOWN
When:  пользователь отправил `/render_status UUID_UNKNOWN`
Then:  бот ответил сообщением, содержащим 'не найден'
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.renders.F002.render_status_widget import handle_render_status
from service.api.renders_api import NotFoundError
from tests.F002_render_status.conftest import UUID_UNKNOWN


@pytest.mark.asyncio
async def test_unknown_render_returns_not_found(
    make_message, mock_state, fake_api_factory
) -> None:
    # Given
    msg = make_message(f"/render_status {UUID_UNKNOWN}")
    fake_api = fake_api_factory(get_side_effect=NotFoundError(UUID_UNKNOWN))

    # When
    with patch(
        "node.renders.code.render_status_code.RendersAPI",
        return_value=fake_api,
    ):
        await handle_render_status(msg, mock_state)

    # Then
    fake_api.get.assert_awaited_once_with(UUID_UNKNOWN)
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.call_args.args[0]
    assert "не найден" in sent_text.lower()
