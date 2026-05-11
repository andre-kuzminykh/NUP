"""Publication aggregate — фиксирует попытку публикации в Telegram.

Tested by tests/unit/test_text_publisher.py (REQ-F03-003).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PublicationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class PublicationKind(str, Enum):
    TEXT = "text"
    VIDEO = "video"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Publication:
    chat_id: str
    kind: PublicationKind = PublicationKind.TEXT
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PublicationStatus = PublicationStatus.PENDING
    message_id: int | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
