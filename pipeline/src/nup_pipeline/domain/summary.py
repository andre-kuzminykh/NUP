"""SummaryBundle — RU + EN summary per article (F002)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SummaryBundle:
    article_id: str
    link: str
    title_ru: str
    content_ru: str
    title_en: str
    content_en: str
