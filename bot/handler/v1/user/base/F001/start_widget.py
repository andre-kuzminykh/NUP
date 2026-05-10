"""
Виджет: приветствие по /start.

## Трассируемость
Feature: F001 — Welcome and main menu
Scenarios: SC001

SC001 — пользователь шлёт /start → answer: welcome (FSM очищается).

## Зависимости
- StartTrigger, StartCode, WelcomeAnswer
"""
from __future__ import annotations

from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handler.v1.user.router import base_router
from node.base.answer.welcome_answer import WelcomeAnswer
from node.base.code.start_code import StartCode
from node.base.trigger.start_trigger import StartTrigger

ANSWER_REGISTRY = {
    "welcome": WelcomeAnswer(),
}


@base_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    trigger_data = await StartTrigger().run(message, state)
    code_result = await StartCode().run(trigger_data, state)
    answer = ANSWER_REGISTRY[code_result["answer_name"]]
    await answer.run(event=message, user_lang="ru", data=code_result["data"])
