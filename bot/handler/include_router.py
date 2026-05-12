"""
Подключение роутеров и регистрация виджетов.

## Трассируемость
Feature: F001, F002 (общая инфра)

## Бизнес-контекст
Импорт виджетов триггерит регистрацию декораторов на роутерах. Затем
роутеры включаются в Dispatcher.
"""
from __future__ import annotations

from aiogram import Dispatcher

# noqa: F401 — импорты ниже нужны для побочного эффекта (регистрация декораторов).
import handler.v1.user.base.F001.start_widget  # noqa: F401
import handler.v1.user.renders.F002.render_status_widget  # noqa: F401
import handler.v1.user.reviews.F003.review_callback_widget  # noqa: F401
import handler.v1.user.reviews.F003.edit_callback_widget  # noqa: F401
from handler.v1.user.router import base_router, renders_router, reviews_router


def setup_routers(dp: Dispatcher) -> None:
    dp.include_router(base_router)
    dp.include_router(renders_router)
    dp.include_router(reviews_router)
