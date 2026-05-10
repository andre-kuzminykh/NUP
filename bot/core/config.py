"""
Bot configuration.

## Трассируемость
Feature: F001 — Welcome and main menu
Feature: F002 — Render job status

## Бизнес-контекст
Загружает настройки из переменных окружения. Проектное правило:
секреты не лежат в репозитории, только в .env / runtime env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str
    BACKEND_URL: str
    REQUEST_TIMEOUT: float


def _load() -> Config:
    return Config(
        BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
        BACKEND_URL=os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/"),
        REQUEST_TIMEOUT=float(os.getenv("REQUEST_TIMEOUT", "5")),
    )


config: Config = _load()
