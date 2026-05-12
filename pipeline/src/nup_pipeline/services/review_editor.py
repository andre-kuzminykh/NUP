"""F013 — ReviewEditor: навигация по сегментам и выбор кандидатов.

Состояние хранится в `ReviewSession.segments_snapshot` (список сегментов с
кандидатами и active_idx) + `edit_state` ({cursor: int}).

Сервис делает только мутации над состоянием. Реальная пересборка видео
после commit — отдельный шаг (cli/submit_for_review.py делает повторную
отрисовку). Это разделение упрощает unit-тестирование.

Tested by tests/unit/test_review_editor.py.
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


def _payload(r: ReviewSession) -> dict[str, Any]:
    """Pure projection текущего состояния review для bot UI."""
    segments = r.segments_snapshot or []
    total = len(segments)
    cursor = int((r.edit_state or {}).get("cursor", 0)) if total else 0
    cursor = max(0, min(cursor, total - 1)) if total else 0

    if total == 0:
        return {
            "review_id": r.id,
            "status": r.status.value,
            "cursor": 0, "total": 0,
            "segment_text": "",
            "candidate_idx": 0, "candidate_total": 0,
            "active_video_url": None,
        }

    seg = segments[cursor]
    candidates = seg.get("candidates") or []
    active_idx = int(seg.get("active_idx", 0))
    active_idx = max(0, min(active_idx, len(candidates) - 1)) if candidates else 0
    active = candidates[active_idx] if candidates else {}
    return {
        "review_id": r.id,
        "status": r.status.value,
        "cursor": cursor,
        "total": total,
        "segment_text": seg.get("text", ""),
        "candidate_idx": active_idx,
        "candidate_total": len(candidates),
        "active_video_url": active.get("video_url") if active else None,
        "active_preview_url": active.get("preview_url") if active else None,
        "active_file_id": active.get("file_id") if active else None,
    }


class ReviewEditor:
    def __init__(self, repo: _ReviewRepo) -> None:
        self._repo = repo

    # --- helpers -----------------------------------------------------------

    def _load(self, review_id: str) -> ReviewSession:
        r = self._repo.get(review_id)
        if r is None:
            raise KeyError(f"review {review_id} not found")
        return r

    # --- public API --------------------------------------------------------

    def start(self, review_id: str) -> dict[str, Any]:
        """Перевести в IN_EDIT. Инициализирует edit_state, не трогая snapshot."""
        r = self._load(review_id)
        r.transition(ReviewStatus.IN_EDIT)
        if not r.edit_state:
            r.edit_state = {"cursor": 0}
        self._repo.save(r)
        return _payload(r)

    def cancel(self, review_id: str) -> dict[str, Any]:
        """Выйти из IN_EDIT обратно в PENDING_REVIEW. active_idx сегментов
        НЕ откатываются — пользователь мог что-то поменять до cancel'а."""
        r = self._load(review_id)
        if r.status is ReviewStatus.IN_EDIT:
            r.transition(ReviewStatus.PENDING_REVIEW)
        r.edit_state = None
        self._repo.save(r)
        return _payload(r)

    def move(self, review_id: str, direction: str) -> dict[str, Any]:
        """Перемещение между сегментами (◀ Кадр / Кадр ▶). Clamp на границах."""
        r = self._load(review_id)
        if r.status is not ReviewStatus.IN_EDIT:
            raise IllegalReviewStateError("editor.move requires IN_EDIT state")
        total = len(r.segments_snapshot or [])
        if total == 0:
            return _payload(r)
        state = dict(r.edit_state or {"cursor": 0})
        cursor = int(state.get("cursor", 0))
        if direction == "next":
            cursor = min(total - 1, cursor + 1)
        elif direction == "prev":
            cursor = max(0, cursor - 1)
        else:
            raise ValueError(f"unknown direction: {direction!r}")
        state["cursor"] = cursor
        r.edit_state = state
        self._repo.save(r)
        return _payload(r)

    def pick(self, review_id: str, direction: str) -> dict[str, Any]:
        """Перемещение между кандидатами текущего сегмента (◀ Клип / Клип ▶).

        direction: 'next' / 'prev'. Циклически (на последнем next → 0)."""
        r = self._load(review_id)
        if r.status is not ReviewStatus.IN_EDIT:
            raise IllegalReviewStateError("editor.pick requires IN_EDIT state")
        segments = list(r.segments_snapshot or [])
        if not segments:
            return _payload(r)
        cursor = int((r.edit_state or {}).get("cursor", 0))
        cursor = max(0, min(cursor, len(segments) - 1))
        seg = dict(segments[cursor])
        candidates = seg.get("candidates") or []
        if not candidates:
            return _payload(r)
        active = int(seg.get("active_idx", 0))
        if direction == "next":
            active = (active + 1) % len(candidates)
        elif direction == "prev":
            active = (active - 1) % len(candidates)
        else:
            raise ValueError(f"unknown direction: {direction!r}")
        seg["active_idx"] = active
        segments[cursor] = seg
        r.segments_snapshot = segments
        self._repo.save(r)
        return _payload(r)

    def payload(self, review_id: str) -> dict[str, Any]:
        return _payload(self._load(review_id))
