"""
RenderStatusCode — валидация UUID, вызов backend и выбор Answer.

## Трассируемость
Feature: F002 — Render job status
Scenarios: SC001, SC002, SC003

## Зависимости
- service.api.renders_api.RendersAPI (через DI или ленивая инициализация)

## Бизнес-контекст
BR001: невалидный UUID → render_invalid_uuid (без обращения к backend).
BR002: backend 404 → render_not_found.
Иначе → render_found с данными для Answer.
"""
from __future__ import annotations

import uuid
from typing import Any

from service.api.renders_api import BackendError, NotFoundError, RendersAPI


class RenderStatusCode:
    def __init__(self, api: RendersAPI | None = None) -> None:
        # Lazy default: реальный API в проде, mocked в тестах через patch.
        self._api = api or RendersAPI()

    async def run(self, trigger_data: dict, state: Any) -> dict:
        raw = trigger_data.get("raw_arg", "")
        try:
            uuid.UUID(raw)
        except (ValueError, AttributeError, TypeError):
            return {"answer_name": "render_invalid_uuid", "data": {}}

        try:
            job = await self._api.get(raw)
        except NotFoundError:
            return {"answer_name": "render_not_found", "data": {"job_id": raw}}
        except BackendError as e:
            return {"answer_name": "render_backend_error", "data": {"error": str(e)}}

        return {"answer_name": "render_found", "data": job}
