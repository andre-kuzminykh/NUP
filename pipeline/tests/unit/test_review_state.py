"""F011/F012/F013 — ReviewSession state machine.

Traces: REQ-F012-007.
"""
import pytest

from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)


def _new(status: ReviewStatus = ReviewStatus.PENDING_REVIEW) -> ReviewSession:
    return ReviewSession.new(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1003924811323,
        status=status,
    )


@pytest.mark.unit
@pytest.mark.req("REQ-F012-007")
@pytest.mark.parametrize(
    "src, dst",
    [
        (ReviewStatus.PENDING_REVIEW, ReviewStatus.APPROVED),
        (ReviewStatus.PENDING_REVIEW, ReviewStatus.DECLINED),
        (ReviewStatus.PENDING_REVIEW, ReviewStatus.IN_EDIT),
        (ReviewStatus.IN_EDIT, ReviewStatus.PENDING_REVIEW),  # cancel edit
        # Idempotent self-transitions:
        (ReviewStatus.APPROVED, ReviewStatus.APPROVED),
        (ReviewStatus.DECLINED, ReviewStatus.DECLINED),
    ],
)
def test_legal_transitions(src, dst) -> None:
    r = _new(src)
    r.transition(dst)
    assert r.status is dst


@pytest.mark.unit
@pytest.mark.req("REQ-F012-007")
@pytest.mark.parametrize(
    "src, dst",
    [
        (ReviewStatus.DECLINED, ReviewStatus.APPROVED),
        (ReviewStatus.APPROVED, ReviewStatus.DECLINED),
        (ReviewStatus.DECLINED, ReviewStatus.IN_EDIT),
        (ReviewStatus.APPROVED, ReviewStatus.IN_EDIT),
        (ReviewStatus.IN_EDIT, ReviewStatus.APPROVED),
        (ReviewStatus.IN_EDIT, ReviewStatus.DECLINED),
    ],
)
def test_illegal_transitions_raise(src, dst) -> None:
    r = _new(src)
    with pytest.raises(IllegalReviewStateError):
        r.transition(dst)
