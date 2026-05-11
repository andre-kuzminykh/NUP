"""F013 — ReviewEditor contract (skeleton).

Implementation in this iteration is intentionally minimal — full FSM and
Pexels refresh are deferred. These tests pin the API contract that future
implementation MUST honour.

Traces: REQ-F013-001, REQ-F013-002, REQ-F013-006, REQ-F013-007.
"""
import pytest

from nup_pipeline.domain.review import ReviewSession, ReviewStatus
from nup_pipeline.services.review_editor import ReviewEditor


class InMemReviewRepo:
    def __init__(self) -> None:
        self.rows: dict[str, ReviewSession] = {}

    def get(self, rid: str):
        return self.rows.get(rid)

    def save(self, r: ReviewSession) -> None:
        self.rows[r.id] = r


def _session_with_segments(n: int = 3) -> ReviewSession:
    s = ReviewSession.new(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1003924811323,
    )
    # Minimal segment snapshot — real implementation reads from F07 cache.
    s.segments_snapshot = [
        {"text": f"segment {i}", "candidates": [{"video_url": f"v{i}_0"}]}
        for i in range(n)
    ]
    return s


@pytest.mark.unit
@pytest.mark.req("REQ-F013-001")
def test_start_transitions_to_in_edit_and_returns_cursor_zero() -> None:
    repo = InMemReviewRepo()
    s = _session_with_segments(3)
    repo.save(s)
    editor = ReviewEditor(review_repo=repo)
    payload = editor.start(s.id)
    assert repo.get(s.id).status is ReviewStatus.IN_EDIT
    assert payload["cursor"] == 0
    assert payload["total"] == 3
    assert payload["segment_text"] == "segment 0"


@pytest.mark.unit
@pytest.mark.req("REQ-F013-002")
@pytest.mark.parametrize(
    "start_cursor, direction, expected",
    [
        (0, "prev", 0),  # clamp at left edge
        (0, "next", 1),
        (2, "next", 2),  # clamp at right edge
        (1, "prev", 0),
    ],
)
def test_move_clamps_at_edges(start_cursor, direction, expected) -> None:
    repo = InMemReviewRepo()
    s = _session_with_segments(3)
    repo.save(s)
    editor = ReviewEditor(review_repo=repo)
    editor.start(s.id)
    # Bring cursor to start position.
    while editor.payload(s.id)["cursor"] < start_cursor:
        editor.move(s.id, "next")
    payload = editor.move(s.id, direction)
    assert payload["cursor"] == expected


@pytest.mark.unit
@pytest.mark.req("REQ-F013-006")
def test_cancel_restores_pending_review() -> None:
    repo = InMemReviewRepo()
    s = _session_with_segments(2)
    repo.save(s)
    editor = ReviewEditor(review_repo=repo)
    editor.start(s.id)
    editor.cancel(s.id)
    assert repo.get(s.id).status is ReviewStatus.PENDING_REVIEW
    assert repo.get(s.id).edit_state is None


@pytest.mark.unit
@pytest.mark.req("REQ-F013-007")
def test_payload_shape_has_required_keys() -> None:
    repo = InMemReviewRepo()
    s = _session_with_segments(1)
    repo.save(s)
    editor = ReviewEditor(review_repo=repo)
    payload = editor.start(s.id)
    for key in ("cursor", "total", "segment_text", "active_candidate", "candidates"):
        assert key in payload, f"payload must contain {key!r}"
