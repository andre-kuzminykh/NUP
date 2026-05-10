"""RenderJob aggregate + state machine (F08).

Tested by tests/unit/test_render_job_state.py (REQ-F08-008).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from nup_pipeline.domain.segment import Segment


class IllegalStateError(RuntimeError):
    """Raised when a RenderJob receives a forbidden state transition."""


class RenderStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# (src, dst) → allowed
_LEGAL: set[tuple[RenderStatus, RenderStatus]] = {
    (RenderStatus.PENDING, RenderStatus.RUNNING),
    (RenderStatus.RUNNING, RenderStatus.SUCCEEDED),
    (RenderStatus.RUNNING, RenderStatus.FAILED),
}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class RenderJob:
    id: str
    segments: list[Segment]
    music_uri: str | None = None
    status: RenderStatus = RenderStatus.PENDING
    output_uri: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @classmethod
    def new(
        cls,
        segments: list[Segment],
        music_uri: str | None,
        *,
        status: RenderStatus = RenderStatus.PENDING,
        job_id: str | None = None,
    ) -> "RenderJob":
        return cls(
            id=job_id or str(uuid.uuid4()),
            segments=list(segments),
            music_uri=music_uri,
            status=status,
        )

    def transition(self, new_status: RenderStatus) -> None:
        if (self.status, new_status) not in _LEGAL:
            raise IllegalStateError(
                f"illegal transition {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        self.updated_at = _utcnow()
