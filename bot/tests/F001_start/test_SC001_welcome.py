"""
Тест SC001 — /start показывает welcome.

## Трассируемость
Feature: F001 — Welcome and main menu
Scenario: SC001 — Welcome on /start

## BDD
Given: пользователь только что открыл чат
When:  отправлен /start
Then:  бот ответил один раз сообщением, содержащим 'NUP Pipeline Bot'
And:   FSM-состояние очищено (BR001)
"""
from __future__ import annotations

import pytest

from handler.v1.user.base.F001.start_widget import handle_start


@pytest.mark.asyncio
async def test_start_replies_with_welcome_and_clears_state(make_message, mock_state) -> None:
    # Given
    msg = make_message("/start")

    # When
    await handle_start(msg, mock_state)

    # Then
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.call_args.args[0]
    assert "NUP Pipeline Bot" in sent_text
    assert "/render" in sent_text  # menu hints at /render_status
    mock_state.clear.assert_awaited_once()
