"""ReviewSession — domain aggregate для оператор-ревью Reels.

Fixed lifecycle:
    PENDING_REVIEW ─approve──► APPROVED
                  ─decline──► DECLINED
                  ─start_edit──► IN_EDIT
    IN_EDIT       ─cancel───► PENDING_REVIEW

Idempotent self-transitions (APPROVED→APPROVED, DECLINED→DECLINED) разрешены,
чтобы повторные сетевые вызовы оставались no-op.

Tested by tests/unit/test_review_state.py, test_review_submission.py,
test_review_decision.py, test_review_editor_contract.py.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class IllegalReviewStateError(RuntimeError):
    """Raised on a forbidden ReviewSession transition or unsupported operation."""


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DECLINED = "declined"
    IN_EDIT = "in_edit"


_LEGAL: set[tuple[ReviewStatus, ReviewStatus]] = {
    (ReviewStatus.PENDING_REVIEW, ReviewStatus.APPROVED),
    (ReviewStatus.PENDING_REVIEW, ReviewStatus.DECLINED),
    (ReviewStatus.PENDING_REVIEW, ReviewStatus.IN_EDIT),
    (ReviewStatus.IN_EDIT, ReviewStatus.PENDING_REVIEW),
    # Idempotent self-transitions:
    (ReviewStatus.APPROVED, ReviewStatus.APPROVED),
    (ReviewStatus.DECLINED, ReviewStatus.DECLINED),
}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class ReviewSession:
    id: str
    render_job_id: str
    reviewer_chat_id: int
    channel_id: int
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    message_id: int | None = None              # message in operator chat
    output_uri: str | None = None              # snapshot of render_job.output_uri
    caption: str | None = None                 # bilingual caption sent to operator
    publication_message_id: int | None = None  # message in channel after approve
    edit_state: dict[str, Any] | None = None
    # Snapshot of segments at submission time (used by F013 edit mode).
    segments_snapshot: list[dict] | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @classmethod
    def new(
        cls,
        render_job_id: str,
        reviewer_chat_id: int,
        channel_id: int,
        *,
        status: ReviewStatus = ReviewStatus.PENDING_REVIEW,
        review_id: str | None = None,
    ) -> "ReviewSession":
        return cls(
            id=review_id or str(uuid.uuid4()),
            render_job_id=render_job_id,
            reviewer_chat_id=reviewer_chat_id,
            channel_id=channel_id,
            status=status,
        )

    def transition(self, new_status: ReviewStatus) -> None:
        if (self.status, new_status) not in _LEGAL:
            raise IllegalReviewStateError(
                f"illegal review transition {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        self.updated_at = _utcnow()
