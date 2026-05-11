"""
RenderBackendErrorAnswer — backend упал не по 404.

## Трассируемость
Feature: F002 — Render job status
"""
from __future__ import annotations

from typing import Any

from core.vocab import RENDER_BACKEND_ERROR


class RenderBackendErrorAnswer:
    async def run(self, event: Any, user_lang: str, data: dict) -> None:
        await event.answer(RENDER_BACKEND_ERROR)
