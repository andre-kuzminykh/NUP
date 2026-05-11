"""F013 — ReviewEditor (skeleton).

Минимальная реализация, чтобы пройти contract-тесты. Pexels-refresh,
candidate pick и commit (re-render через F008) делаются следующей
итерацией. Тесты пинят форму payload и поведение start / move / cancel.

Tested by tests/unit/test_review_editor_contract.py.
"""
from __future__ import annotations

from typing import Any, Protocol

from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)


class _ReviewRepo(Protocol):
    def get(self, review_id: str) -> ReviewSession | None: ...
    def save(self, r: ReviewSession) -> None: ...


class ReviewEditor:
    def __init__(self, review_repo: _ReviewRepo) -> None:
        self._repo = review_repo

    # --- internals ---------------------------------------------------------

    def _load(self, review_id: str) -> ReviewSession:
        r = self._repo.get(review_id)
        if r is None:
            raise KeyError(f"review {review_id} not found")
        return r

    def _build_payload(self, r: ReviewSession) -> dict[str, Any]:
        state = r.edit_state or {}
        cursor = int(state.get("cursor", 0))
        segments = r.segments_snapshot or []
        total = len(segments)
        if total == 0:
            return {
                "cursor": 0,
                "total": 0,
                "segment_text": "",
                "active_candidate": None,
                "candidates": [],
            }
        seg = segments[cursor]
        active_idx = int(state.get("active", {}).get(str(cursor), 0))
        candidates = seg.get("candidates") or []
        active = candidates[active_idx] if candidates else None
        return {
            "cursor": cursor,
            "total": total,
            "segment_text": seg.get("text", ""),
            "active_candidate": active,
            "candidates": candidates,
        }

    # --- API ---------------------------------------------------------------

    def start(self, review_id: str) -> dict[str, Any]:
        r = self._load(review_id)
        # `transition` rejects illegal states (only PENDING_REVIEW → IN_EDIT).
        r.transition(ReviewStatus.IN_EDIT)
        r.edit_state = {"cursor": 0, "active": {}}
        self._repo.save(r)
        return self._build_payload(r)

    def move(self, review_id: str, direction: str) -> dict[str, Any]:
        r = self._load(review_id)
        if r.status is not ReviewStatus.IN_EDIT:
            raise IllegalReviewStateError("editor.move requires IN_EDIT state")
        state = r.edit_state or {"cursor": 0, "active": {}}
        cursor = int(state.get("cursor", 0))
        total = len(r.segments_snapshot or [])
        if direction == "next":
            cursor = min(total - 1, cursor + 1)
        elif direction == "prev":
            cursor = max(0, cursor - 1)
        else:
            raise ValueError(f"unknown direction: {direction!r}")
        state["cursor"] = cursor
        r.edit_state = state
        self._repo.save(r)
        return self._build_payload(r)

    def payload(self, review_id: str) -> dict[str, Any]:
        r = self._load(review_id)
        return self._build_payload(r)

    def cancel(self, review_id: str) -> None:
        r = self._load(review_id)
        if r.status is ReviewStatus.IN_EDIT:
            r.transition(ReviewStatus.PENDING_REVIEW)
        r.edit_state = None
        self._repo.save(r)
