"""
Aiogram routers, по одному на тег. Виджеты регистрируют свои хендлеры
на эти роутеры; include_router.py подключает роутеры к Dispatcher.

## Трассируемость
Feature: F001 (base_router), F002 (renders_router)
"""
from __future__ import annotations

from aiogram import Router

base_router = Router(name="base")
renders_router = Router(name="renders")
reviews_router = Router(name="reviews")
