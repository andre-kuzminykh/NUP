"""
Виджет: callback-кнопки approve / decline / edit на превью Reels.

## Трассируемость
Feature: F003 — Review callbacks (RU + EN)
Scenarios: SC001 (approve), SC002 (decline), SC003 (edit), SC004 (malformed)

SC001 — callback_data 'review:approve:<id>' → answer: review_approved
                                            → backend.approve(id), keyboard removed
SC002 — 'review:decline:<id>'                → review_declined
SC003 — 'review:edit:<id>'                   → review_edit_started (skeleton)
SC004 — любая иная форма                      → review_invalid

## Зависимости
- ReviewCallbackTrigger, ReviewCallbackCode (через ReviewsAPI), 5 Answer-нод
"""
from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handler.v1.user.router import reviews_router
from node.reviews.answer.review_approved_answer import ReviewApprovedAnswer
from node.reviews.answer.review_backend_error_answer import ReviewBackendErrorAnswer
from node.reviews.answer.review_declined_answer import ReviewDeclinedAnswer
from node.reviews.answer.review_edit_started_answer import ReviewEditStartedAnswer
from node.reviews.answer.review_invalid_answer import ReviewInvalidAnswer
from node.reviews.code.review_callback_code import ReviewCallbackCode
from node.reviews.trigger.review_callback_trigger import ReviewCallbackTrigger

ANSWER_REGISTRY = {
    "review_approved": ReviewApprovedAnswer(),
    "review_declined": ReviewDeclinedAnswer(),
    "review_edit_started": ReviewEditStartedAnswer(),
    "review_invalid": ReviewInvalidAnswer(),
    "review_backend_error": ReviewBackendErrorAnswer(),
}


@reviews_router.callback_query(F.data.startswith("review:"))
async def handle_review_callback(callback: CallbackQuery, state: FSMContext) -> None:
    trigger_data = await ReviewCallbackTrigger().run(callback, state)
    code_result = await ReviewCallbackCode().run(trigger_data, state)
    answer = ANSWER_REGISTRY[code_result["answer_name"]]
    await answer.run(event=callback, user_lang="ru", data=code_result["data"])
