"""F013 — ReviewEditor: navigation by frames and by candidates within a frame."""
import pytest

from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)
from nup_pipeline.services.review_editor import ReviewEditor


class InMemRepo:
    def __init__(self) -> None:
        self.rows: dict[str, ReviewSession] = {}

    def get(self, rid):
        return self.rows.get(rid)

    def save(self, r):
        self.rows[r.id] = r


def _session_with(segments: list[dict]) -> ReviewSession:
    s = ReviewSession.new(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-100,
    )
    s.segments_snapshot = segments
    return s


def _segs(n: int = 3, per_seg: int = 3) -> list[dict]:
    return [
        {
            "text": f"сегмент {i}",
            "candidates": [{"video_url": f"v{i}_{j}.mp4"} for j in range(per_seg)],
            "active_idx": 0,
        }
        for i in range(n)
    ]


# --- start / cancel ---------------------------------------------------------

@pytest.mark.unit
def test_start_transitions_to_in_edit_and_returns_payload() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(3))
    repo.save(s)
    payload = ReviewEditor(repo).start(s.id)
    assert repo.get(s.id).status is ReviewStatus.IN_EDIT
    assert payload["cursor"] == 0
    assert payload["total"] == 3
    assert payload["segment_text"] == "сегмент 0"
    assert payload["candidate_idx"] == 0
    assert payload["candidate_total"] == 3
    assert payload["active_video_url"] == "v0_0.mp4"


@pytest.mark.unit
def test_cancel_returns_to_pending_review() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(2))
    repo.save(s)
    ed = ReviewEditor(repo)
    ed.start(s.id)
    ed.cancel(s.id)
    assert repo.get(s.id).status is ReviewStatus.PENDING_REVIEW
    assert repo.get(s.id).edit_state is None


# --- move (between frames) --------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize(
    "start_cursor, direction, expected",
    [
        (0, "prev", 0),
        (0, "next", 1),
        (2, "next", 2),  # clamp at right
        (1, "prev", 0),
    ],
)
def test_move_clamps(start_cursor, direction, expected) -> None:
    repo = InMemRepo()
    s = _session_with(_segs(3))
    repo.save(s)
    ed = ReviewEditor(repo)
    ed.start(s.id)
    while ed.payload(s.id)["cursor"] < start_cursor:
        ed.move(s.id, "next")
    p = ed.move(s.id, direction)
    assert p["cursor"] == expected


@pytest.mark.unit
def test_move_when_not_in_edit_raises() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(2))
    repo.save(s)
    with pytest.raises(IllegalReviewStateError):
        ReviewEditor(repo).move(s.id, "next")  # status=PENDING_REVIEW


# --- pick (between candidates within current frame) -------------------------

@pytest.mark.unit
def test_pick_next_cycles_through_candidates() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(n=1, per_seg=3))
    repo.save(s)
    ed = ReviewEditor(repo)
    ed.start(s.id)
    p = ed.pick(s.id, "next")
    assert p["candidate_idx"] == 1
    assert p["active_video_url"] == "v0_1.mp4"
    p = ed.pick(s.id, "next")
    assert p["candidate_idx"] == 2
    p = ed.pick(s.id, "next")
    assert p["candidate_idx"] == 0  # wrap-around


@pytest.mark.unit
def test_pick_prev_cycles_backwards() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(n=1, per_seg=3))
    repo.save(s)
    ed = ReviewEditor(repo)
    ed.start(s.id)
    p = ed.pick(s.id, "prev")
    assert p["candidate_idx"] == 2  # wrap to last


@pytest.mark.unit
def test_pick_persists_active_idx_in_snapshot() -> None:
    """Pick on frame 0 should not affect frame 1's active_idx, and value
    must survive a save+load round-trip via the repo."""
    repo = InMemRepo()
    s = _session_with(_segs(n=2, per_seg=3))
    repo.save(s)
    ed = ReviewEditor(repo)
    ed.start(s.id)
    ed.pick(s.id, "next")
    ed.pick(s.id, "next")  # frame 0 active = 2
    ed.move(s.id, "next")  # cursor to frame 1
    p = ed.payload(s.id)
    assert p["cursor"] == 1
    assert p["candidate_idx"] == 0  # frame 1 untouched
    # Back to frame 0 — still at 2.
    ed.move(s.id, "prev")
    assert ed.payload(s.id)["candidate_idx"] == 2


# --- payload shape ----------------------------------------------------------

@pytest.mark.unit
def test_payload_shape() -> None:
    repo = InMemRepo()
    s = _session_with(_segs(2))
    repo.save(s)
    p = ReviewEditor(repo).start(s.id)
    for k in ("review_id", "status", "cursor", "total", "segment_text",
              "candidate_idx", "candidate_total", "active_video_url"):
        assert k in p
