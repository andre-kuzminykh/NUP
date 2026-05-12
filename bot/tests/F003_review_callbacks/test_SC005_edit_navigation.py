"""
Тест SC005 — навигация в edit-mode (frame/clip prev/next + cancel).

## Трассируемость
Feature: F003 — Review callbacks (edit mode)
Scenario: SC005 — Frame and candidate navigation

## BDD
Given: review в IN_EDIT, видео уже в чате с caption
When:  оператор тапает [Кадр ▶]/[Клип ▶]/etc — callback edit:<id>:frame_next/clip_next/...
Then:  бот зовёт соответствующий backend endpoint и обновляет caption
       новым preview.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from handler.v1.user.reviews.F003.edit_callback_widget import handle_edit_callback
from tests.F003_review_callbacks.conftest import REVIEW_ID


def _payload(cursor=0, total=3, cand=0, cand_total=3, text="seg"):
    return {
        "review_id": REVIEW_ID, "status": "in_edit",
        "cursor": cursor, "total": total,
        "segment_text": text,
        "candidate_idx": cand, "candidate_total": cand_total,
        "active_video_url": f"v{cursor}_{cand}.mp4",
    }


@pytest.fixture
def edit_callback(make_callback):
    def _make(data: str):
        cb = make_callback(data)
        cb.message.edit_caption = AsyncMock()
        cb.message.edit_reply_markup = AsyncMock()
        return cb
    return _make


@pytest.mark.asyncio
async def test_frame_next_calls_move_next(edit_callback, mock_state) -> None:
    cb = edit_callback(f"edit:{REVIEW_ID}:frame_next")
    api = AsyncMock()
    api.move = AsyncMock(return_value=_payload(cursor=1))
    with patch("node.reviews.code.edit_callback_code.ReviewsAPI", return_value=api):
        await handle_edit_callback(cb, mock_state)
    api.move.assert_awaited_once_with(REVIEW_ID, "next")
    cb.message.edit_caption.assert_awaited_once()
    caption = cb.message.edit_caption.call_args.kwargs["caption"]
    assert "Кадр *2/3*" in caption


@pytest.mark.asyncio
async def test_clip_prev_calls_pick_prev(edit_callback, mock_state) -> None:
    cb = edit_callback(f"edit:{REVIEW_ID}:clip_prev")
    api = AsyncMock()
    api.pick = AsyncMock(return_value=_payload(cand=2))
    with patch("node.reviews.code.edit_callback_code.ReviewsAPI", return_value=api):
        await handle_edit_callback(cb, mock_state)
    api.pick.assert_awaited_once_with(REVIEW_ID, "prev")
    caption = cb.message.edit_caption.call_args.kwargs["caption"]
    assert "Клип *3/3*" in caption


@pytest.mark.asyncio
async def test_approve_from_edit_calls_approve(edit_callback, mock_state) -> None:
    cb = edit_callback(f"edit:{REVIEW_ID}:approve")
    api = AsyncMock()
    api.approve = AsyncMock(return_value={"status": "approved"})
    with patch("node.reviews.code.edit_callback_code.ReviewsAPI", return_value=api):
        await handle_edit_callback(cb, mock_state)
    api.approve.assert_awaited_once_with(REVIEW_ID)


@pytest.mark.asyncio
async def test_decline_from_edit_calls_decline(edit_callback, mock_state) -> None:
    cb = edit_callback(f"edit:{REVIEW_ID}:decline")
    api = AsyncMock()
    api.decline = AsyncMock(return_value={"status": "declined"})
    with patch("node.reviews.code.edit_callback_code.ReviewsAPI", return_value=api):
        await handle_edit_callback(cb, mock_state)
    api.decline.assert_awaited_once_with(REVIEW_ID)


@pytest.mark.asyncio
async def test_malformed_edit_callback_no_backend_call(edit_callback, mock_state) -> None:
    cb = edit_callback("edit:garbage")
    api = AsyncMock()
    with patch("node.reviews.code.edit_callback_code.ReviewsAPI", return_value=api):
        await handle_edit_callback(cb, mock_state)
    api.move.assert_not_awaited()
    api.pick.assert_not_awaited()
