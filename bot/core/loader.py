"""
Aiogram bootstrap helpers.

## Трассируемость
Feature: F001, F002 (общая инфра)

## Бизнес-контекст
make_bot выделено отдельно, чтобы тесты не пытались поднять реальный
Bot без токена. app.py вызывает make_bot(config.BOT_TOKEN) на старте,
тесты импортируют только хэндлеры с моками.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage


def make_bot(token: str) -> Bot:
    if not token:
        raise RuntimeError("BOT_TOKEN is empty — set it in env before starting the bot")
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )


def make_dispatcher() -> Dispatcher:
    return Dispatcher(storage=MemoryStorage())
