"""F012 — ReviewDecider (approve / decline / start_edit).

Traces: REQ-F012-001..005, REQ-F012-007.
"""
import pytest

from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)
from nup_pipeline.services.review_decision import ReviewDecider


class InMemReviewRepo:
    def __init__(self) -> None:
        self.rows: dict[str, ReviewSession] = {}

    def get(self, review_id: str) -> ReviewSession | None:
        return self.rows.get(review_id)

    def save(self, r: ReviewSession) -> None:
        self.rows[r.id] = r


class FakeVideoPublisher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def publish(self, chat_id, video_uri, caption) -> int:
        self.calls.append({"chat_id": chat_id, "video_uri": video_uri, "caption": caption})
        return 9000 + len(self.calls)


def _session(status: ReviewStatus = ReviewStatus.PENDING_REVIEW, caption: str = "RU\n\nEN") -> ReviewSession:
    s = ReviewSession.new(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1003924811323,
        status=status,
    )
    s.output_uri = "s3://nup-media/renders/abc.mp4"
    s.caption = caption
    return s


@pytest.mark.unit
@pytest.mark.req("REQ-F012-001")
@pytest.mark.req("REQ-F012-006")
def test_approve_transitions_and_publishes_to_channel() -> None:
    repo = InMemReviewRepo()
    s = _session(caption="*Заголовок*\n\nТело\n\n*Headline*\n\nBody")
    repo.save(s)
    pub = FakeVideoPublisher()
    decider = ReviewDecider(review_repo=repo, video_publisher=pub)
    updated = decider.approve(s.id)
    assert updated.status is ReviewStatus.APPROVED
    assert updated.publication_message_id is not None
    assert len(pub.calls) == 1
    call = pub.calls[0]
    assert call["chat_id"] == s.channel_id
    assert call["video_uri"] == s.output_uri
    assert call["caption"] == s.caption


@pytest.mark.unit
@pytest.mark.req("REQ-F012-002")
def test_decline_transitions_without_publishing() -> None:
    repo = InMemReviewRepo()
    s = _session()
    repo.save(s)
    pub = FakeVideoPublisher()
    decider = ReviewDecider(review_repo=repo, video_publisher=pub)
    updated = decider.decline(s.id)
    assert updated.status is ReviewStatus.DECLINED
    assert pub.calls == []


@pytest.mark.unit
@pytest.mark.req("REQ-F012-003")
def test_approve_is_idempotent_no_second_publish() -> None:
    repo = InMemReviewRepo()
    s = _session()
    repo.save(s)
    pub = FakeVideoPublisher()
    decider = ReviewDecider(review_repo=repo, video_publisher=pub)
    first = decider.approve(s.id)
    second = decider.approve(s.id)
    assert second.publication_message_id == first.publication_message_id
    assert len(pub.calls) == 1


@pytest.mark.unit
@pytest.mark.req("REQ-F012-007")
@pytest.mark.parametrize(
    "from_status, action",
    [
        (ReviewStatus.DECLINED, "approve"),
        (ReviewStatus.APPROVED, "decline"),
        (ReviewStatus.DECLINED, "start_edit"),
        (ReviewStatus.APPROVED, "start_edit"),
    ],
)
def test_illegal_actions_raise(from_status, action) -> None:
    repo = InMemReviewRepo()
    s = _session(status=from_status)
    repo.save(s)
    pub = FakeVideoPublisher()
    decider = ReviewDecider(review_repo=repo, video_publisher=pub)
    with pytest.raises(IllegalReviewStateError):
        getattr(decider, action)(s.id)


@pytest.mark.unit
def test_unknown_review_raises_lookup_error() -> None:
    repo = InMemReviewRepo()
    decider = ReviewDecider(review_repo=repo, video_publisher=FakeVideoPublisher())
    with pytest.raises(KeyError):
        decider.approve("does-not-exist")
