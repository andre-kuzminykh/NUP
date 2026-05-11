"""
Виджет: статус задачи рендера по /render_status <uuid>.

## Трассируемость
Feature: F002 — Render job status
Scenarios: SC001, SC002, SC003

SC001 — backend вернул job → answer: render_found.
SC002 — backend 404                  → answer: render_not_found.
SC003 — argument не UUID             → answer: render_invalid_uuid (без вызова backend).

## Зависимости
- RenderStatusTrigger, RenderStatusCode (с RendersAPI), 4 Answer-ноды
"""
from __future__ import annotations

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handler.v1.user.router import renders_router
from node.renders.answer.render_backend_error_answer import RenderBackendErrorAnswer
from node.renders.answer.render_found_answer import RenderFoundAnswer
from node.renders.answer.render_invalid_uuid_answer import RenderInvalidUuidAnswer
from node.renders.answer.render_not_found_answer import RenderNotFoundAnswer
from node.renders.code.render_status_code import RenderStatusCode
from node.renders.trigger.render_status_trigger import RenderStatusTrigger

ANSWER_REGISTRY = {
    "render_found": RenderFoundAnswer(),
    "render_not_found": RenderNotFoundAnswer(),
    "render_invalid_uuid": RenderInvalidUuidAnswer(),
    "render_backend_error": RenderBackendErrorAnswer(),
}


@renders_router.message(Command("render_status"))
async def handle_render_status(message: Message, state: FSMContext) -> None:
    trigger_data = await RenderStatusTrigger().run(message, state)
    code_result = await RenderStatusCode().run(trigger_data, state)
    answer = ANSWER_REGISTRY[code_result["answer_name"]]
    await answer.run(event=message, user_lang="ru", data=code_result["data"])
