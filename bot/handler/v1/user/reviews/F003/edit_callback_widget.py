"""
Виджет: callback'и edit-mode (frame/clip навигация, approve/decline/cancel изнутри edit).

## Трассируемость
Feature: F003 — Review callbacks (edit mode)
Scenarios: SC003 (frame/clip navigation), SC004 (publish/decline from edit)
"""
from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handler.v1.user.router import reviews_router
from node.reviews.answer.review_approved_answer import ReviewApprovedAnswer
from node.reviews.answer.review_backend_error_answer import ReviewBackendErrorAnswer
from node.reviews.answer.review_declined_answer import ReviewDeclinedAnswer
from node.reviews.answer.review_edit_cancelled_answer import ReviewEditCancelledAnswer
from node.reviews.answer.review_edit_preview_answer import ReviewEditPreviewAnswer
from node.reviews.answer.review_invalid_answer import ReviewInvalidAnswer
from node.reviews.code.edit_callback_code import EditCallbackCode
from node.reviews.trigger.edit_callback_trigger import EditCallbackTrigger

ANSWER_REGISTRY = {
    "review_edit_preview": ReviewEditPreviewAnswer(),
    "review_edit_cancelled": ReviewEditCancelledAnswer(),
    "review_approved": ReviewApprovedAnswer(),
    "review_declined": ReviewDeclinedAnswer(),
    "review_invalid": ReviewInvalidAnswer(),
    "review_backend_error": ReviewBackendErrorAnswer(),
}


@reviews_router.callback_query(F.data.startswith("edit:"))
async def handle_edit_callback(callback: CallbackQuery, state: FSMContext) -> None:
    trigger_data = await EditCallbackTrigger().run(callback, state)
    code_result = await EditCallbackCode().run(trigger_data, state)
    answer = ANSWER_REGISTRY[code_result["answer_name"]]
    await answer.run(event=callback, user_lang="ru", data=code_result["data"])
