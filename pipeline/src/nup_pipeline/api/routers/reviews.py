"""F011/F012/F013 — REST /v1/reviews/*.

Endpoints:
  GET    /v1/reviews/{id}                — current state payload
  POST   /v1/reviews/{id}/approve        — publish to channel
  POST   /v1/reviews/{id}/decline        — discard
  POST   /v1/reviews/{id}/start-edit     — enter IN_EDIT mode
  POST   /v1/reviews/{id}/cancel-edit    — back to PENDING_REVIEW
  POST   /v1/reviews/{id}/move           — body {"direction": "prev"|"next"}
  POST   /v1/reviews/{id}/pick           — body {"direction": "prev"|"next"}

Возвращают payload c полным состоянием для бота.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from nup_pipeline.api.deps import (
    get_candidate_refresher,
    get_review_decider,
    get_review_editor,
    get_review_repo,
)
from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)
from nup_pipeline.services.candidate_refresher import CandidateRefresher
from nup_pipeline.services.review_decision import ReviewDecider
from nup_pipeline.services.review_editor import ReviewEditor

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


class DirectionBody(BaseModel):
    direction: str  # "prev" | "next"


def _state(session: ReviewSession, editor: ReviewEditor) -> dict:
    """Возвращаем payload c полным состоянием включая статус."""
    p = editor.payload(session.id)
    # editor.payload может игнорировать output_uri/caption — добавим тут.
    p["output_uri"] = session.output_uri
    p["caption"] = session.caption
    p["status"] = session.status.value
    return p


@router.get("/{review_id}")
def get_review(
    review_id: str,
    repo: Annotated[object, Depends(get_review_repo)],
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
):
    s = repo.get(review_id)
    if s is None:
        raise HTTPException(404, "review not found")
    return _state(s, editor)


def _ensure_not_in_edit(review_id: str, repo, editor: ReviewEditor) -> None:
    """Если оператор жмёт ✅/❌ из edit-mode, сначала возвращаем review
    в PENDING_REVIEW — иначе domain отвергнет переход IN_EDIT → APPROVED."""
    s = repo.get(review_id)
    if s is not None and s.status is ReviewStatus.IN_EDIT:
        editor.cancel(review_id)


@router.post("/{review_id}/approve")
def approve(
    review_id: str,
    decider: Annotated[ReviewDecider, Depends(get_review_decider)],
    repo: Annotated[object, Depends(get_review_repo)],
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
):
    try:
        _ensure_not_in_edit(review_id, repo, editor)
        decider.approve(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    except IllegalReviewStateError as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/decline")
def decline(
    review_id: str,
    decider: Annotated[ReviewDecider, Depends(get_review_decider)],
    repo: Annotated[object, Depends(get_review_repo)],
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
):
    try:
        _ensure_not_in_edit(review_id, repo, editor)
        decider.decline(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    except IllegalReviewStateError as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/start-edit")
def start_edit(
    review_id: str,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
):
    try:
        editor.start(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    except IllegalReviewStateError as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/cancel-edit")
def cancel_edit(
    review_id: str,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
):
    try:
        editor.cancel(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/cancel-edit-revert")
def cancel_edit_revert(
    review_id: str,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
):
    """↩️ Отмена в edit-mode: выйти и сбросить active_idx=0 во всех сегментах."""
    try:
        editor.cancel_revert(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    return _state(repo.get(review_id), editor)


def _ensure_in_edit(review_id: str, repo, editor: ReviewEditor) -> None:
    """Авто-вход в IN_EDIT, если оператор давит стрелки в PENDING_REVIEW
    (бывает после автоматического cancel в approve→fail или если первый
    тап на стрелку прилетел раньше чем edit-mode успел проинициализироваться)."""
    s = repo.get(review_id)
    if s is not None and s.status is ReviewStatus.PENDING_REVIEW:
        editor.start(review_id)


@router.post("/{review_id}/move")
def move(
    review_id: str,
    body: DirectionBody,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
):
    try:
        _ensure_in_edit(review_id, repo, editor)
        editor.move(review_id, body.direction)
    except KeyError:
        raise HTTPException(404, "review not found")
    except (IllegalReviewStateError, ValueError) as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/pick")
def pick(
    review_id: str,
    body: DirectionBody,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
):
    try:
        _ensure_in_edit(review_id, repo, editor)
        editor.pick(review_id, body.direction)
    except KeyError:
        raise HTTPException(404, "review not found")
    except (IllegalReviewStateError, ValueError) as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)


@router.post("/{review_id}/refresh-candidates")
def refresh_candidates(
    review_id: str,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
    refresher: Annotated[CandidateRefresher, Depends(get_candidate_refresher)],
):
    """🔄 Найти ещё — заменить кандидаты текущего сегмента свежей партией
    из Pexels/Pixabay (следующая страница). Auto-входит в IN_EDIT, если
    был в PENDING_REVIEW."""
    try:
        _ensure_in_edit(review_id, repo, editor)
        refresher.refresh(review_id)
    except KeyError:
        raise HTTPException(404, "review not found")
    except (IllegalReviewStateError, ValueError) as e:
        raise HTTPException(409, str(e))
    return _state(repo.get(review_id), editor)
