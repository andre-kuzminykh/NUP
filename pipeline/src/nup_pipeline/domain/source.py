"""Source — registered news source.

Поддерживаемые виды соответствуют REQ-F01-001.
В этой итерации фактически парсятся RSS; остальные адаптеры — спека/roadmap.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceKind(str, Enum):
    RSS = "rss"
    HTML = "html"
    YOUTUBE_CHANNEL = "youtube_channel"
    LINKEDIN_PROFILE = "linkedin_profile"
    X_PROFILE = "x_profile"
    TELEGRAM_CHANNEL = "telegram_channel"


@dataclass
class Source:
    id: str
    kind: SourceKind
    url: str
    is_active: bool = True
