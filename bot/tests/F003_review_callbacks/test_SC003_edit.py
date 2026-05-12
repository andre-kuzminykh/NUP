"""
Тест SC003 — Edit callback переключает сообщение в edit-mode preview.

## Трассируемость
Feature: F003, Scenario: SC003

## BDD
Given: preview-сообщение видео с кнопкой "✏️ Редактировать"
When:  callback_data='review:edit:<id>'
Then:  бэкенд получил start_edit(id), caption переписан на edit-mode UI
       (содержит «Кадр», «Клип», кнопки в новой клавиатуре).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from handler.v1.user.reviews.F003.review_callback_widget import handle_review_callback
from tests.F003_review_callbacks.conftest import REVIEW_ID


@pytest.mark.asyncio
async def test_edit_enters_preview_mode(make_callback, mock_state, fake_api_factory) -> None:
    cb = make_callback(f"review:edit:{REVIEW_ID}")
    # message.edit_caption нужен для edit-mode answer'а
    cb.message.edit_caption = AsyncMock()
    fake_api = fake_api_factory(edit_return={
        "review_id": REVIEW_ID,
        "status": "in_edit",
        "cursor": 0, "total": 3,
        "segment_text": "первое предложение",
        "candidate_idx": 0, "candidate_total": 3,
        "active_video_url": "a.mp4",
    })
    with patch("node.reviews.code.review_callback_code.ReviewsAPI",
               return_value=fake_api):
        await handle_review_callback(cb, mock_state)

    fake_api.start_edit.assert_awaited_once_with(REVIEW_ID)
    fake_api.approve.assert_not_awaited()
    fake_api.decline.assert_not_awaited()
    cb.message.edit_caption.assert_awaited_once()
    kwargs = cb.message.edit_caption.call_args.kwargs
    caption = kwargs["caption"]
    assert "Редактирование" in caption
    assert "Кадр" in caption and "Клип" in caption
    assert kwargs["reply_markup"] is not None
