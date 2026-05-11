"""Article — нормализованная статья из источника.

Tested by tests/unit/test_article_repo.py, test_ingest_service.py.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Article:
    source_id: str
    link: str
    title: str
    raw_content: str = ""
    published_at: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)
