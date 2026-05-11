"""
Bilingual helper.

## Трассируемость
Feature: F003 (Review callbacks) — все ответы оператору RU + EN.

## Бизнес-контекст
Один источник правды для двуязычных строк. Любой Answer-узел склеивает
ru/en через `bi()`, чтобы стиль был одинаковым во всём боте.
"""
from __future__ import annotations


def bi(ru: str, en: str, *, sep: str = "\n\n") -> str:
    """Склеить RU и EN в один блок с разделителем `sep`."""
    return f"{ru.strip()}{sep}{en.strip()}"
