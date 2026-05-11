"""
RenderStatusTrigger — извлекает аргумент команды /render_status.

## Трассируемость
Feature: F002 — Render job status
Scenarios: SC001, SC002, SC003

## Бизнес-контекст
Trigger делает только визуальные/входные операции: выделить аргумент,
почистить пробелы. Решение «валидный ли UUID» принимает Code-нода.
"""
from __future__ import annotations

from typing import Any


class RenderStatusTrigger:
    async def run(self, message: Any, state: Any) -> dict:
        text = (message.text or "").strip()
        # message.text is e.g. "/render_status abc-uuid" or just "/render_status"
        parts = text.split(maxsplit=1)
        raw_arg = parts[1].strip() if len(parts) > 1 else ""
        return {"raw_arg": raw_arg}
