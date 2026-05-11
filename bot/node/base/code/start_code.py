"""
StartCode — выбор Answer для /start.

## Трассируемость
Feature: F001 — Welcome and main menu
Scenario: SC001

## Бизнес-контекст
У /start ровно один путь — приветствие. Ноду оставляем для
единообразия архитектуры (Trigger→Code→Answer).
"""
from __future__ import annotations

from typing import Any


class StartCode:
    async def run(self, trigger_data: dict, state: Any) -> dict:
        return {"answer_name": "welcome", "data": {}}
