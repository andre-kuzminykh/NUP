"""
RenderFoundAnswer — карточка успешно найденного рендера.

## Трассируемость
Feature: F002, Scenario: SC001
"""
from __future__ import annotations

from typing import Any

from core.vocab import RENDER_STATUS_FOUND


class RenderFoundAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        await event.answer(
            RENDER_STATUS_FOUND.format(
                job_id=data.get("job_id", "?"),
                status=data.get("status", "?"),
                output_uri=data.get("output_uri") or "—",
            )
        )
