"""F012 — ReviewDecider (approve / decline / start_edit).

State machine guarded by ReviewSession.transition(). approve() публикует
в канал через VideoPublisher; decline() и start_edit() — без побочных
эффектов в инфре, только смена статуса.

Tested by tests/unit/test_review_decision.py.
"""
from __future__ import annotations

from typing import Protocol

from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)


class _ReviewRepo(Protocol):
    def get(self, review_id: str) -> ReviewSession | None: ...
    def save(self, r: ReviewSession) -> None: ...


class _VideoPublisher(Protocol):
    def publish(self, chat_id, video_uri: str, caption: str | None) -> int: ...


class ReviewDecider:
    def __init__(
        self,
        review_repo: _ReviewRepo,
        video_publisher: _VideoPublisher,
    ) -> None:
        self._repo = review_repo
        self._video = video_publisher

    # --- helpers -----------------------------------------------------------

    def _load(self, review_id: str) -> ReviewSession:
        r = self._repo.get(review_id)
        if r is None:
            raise KeyError(f"review session {review_id} not found")
        return r

    # --- actions -----------------------------------------------------------

    def approve(self, review_id: str) -> ReviewSession:
        r = self._load(review_id)
        if r.status is ReviewStatus.APPROVED:
            return r  # idempotent — REQ-F012-003
        # Will raise IllegalReviewStateError for declined/in_edit/etc.
        r.transition(ReviewStatus.APPROVED)
        if not r.output_uri:
            raise IllegalReviewStateError("review has no output_uri to publish")
        message_id = self._video.publish(r.channel_id, r.output_uri, r.caption)
        r.publication_message_id = message_id
        self._repo.save(r)
        return r

    def decline(self, review_id: str) -> ReviewSession:
        r = self._load(review_id)
        if r.status is ReviewStatus.DECLINED:
            return r  # idempotent — REQ-F012-004
        r.transition(ReviewStatus.DECLINED)
        self._repo.save(r)
        return r

    def start_edit(self, review_id: str) -> ReviewSession:
        r = self._load(review_id)
        if r.status is ReviewStatus.IN_EDIT:
            return r
        r.transition(ReviewStatus.IN_EDIT)
        self._repo.save(r)
        return r
