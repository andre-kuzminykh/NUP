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

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("reviews_api")

from nup_pipeline.api.deps import (
    get_article_repo,
    get_candidate_refresher,
    get_reel_rebuilder,
    get_review_builder,
    get_review_decider,
    get_review_editor,
    get_review_repo,
    get_review_tg_client,
)
from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)
from nup_pipeline.services.candidate_refresher import CandidateRefresher
from nup_pipeline.services.reel_rebuilder import ReelRebuilder
from nup_pipeline.services.review_builder import ReviewBuilder
from nup_pipeline.services.review_decision import ReviewDecider
from nup_pipeline.services.review_editor import ReviewEditor


_ARTICLE_LINK_RE = re.compile(r"\]\((https?://[^)]+)\)")


def _extract_article_link(caption: str | None) -> str | None:
    if not caption:
        return None
    m = _ARTICLE_LINK_RE.search(caption)
    return m.group(1) if m else None

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


def _main_keyboard(review_id: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "🔁 Перегенерировать",
              "callback_data": f"review:regenerate:{review_id}"}],
            [
                {"text": "❌ Отклонить",
                 "callback_data": f"review:decline:{review_id}"},
                {"text": "✏️ Редактировать",
                 "callback_data": f"review:edit:{review_id}"},
                {"text": "✅ Принять",
                 "callback_data": f"review:approve:{review_id}"},
            ],
        ]
    }


@router.post("/{review_id}/regenerate")
def regenerate(
    request: Request,
    review_id: str,
    repo: Annotated[object, Depends(get_review_repo)],
    art_repo: Annotated[object, Depends(get_article_repo)],
    builder: Annotated[ReviewBuilder | None, Depends(get_review_builder)],
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    tg: Annotated[object, Depends(get_review_tg_client)],
):
    """🔁 Перегенерировать reel целиком для той же статьи: новый
    voiceover, новые keywords, новые клипы. ~3-5 мин."""
    if builder is None:
        raise HTTPException(503, "review builder not wired (missing OPENAI/ELEVENLABS keys)")
    s = repo.get(review_id)
    if s is None:
        raise HTTPException(404, "review not found")
    link = _extract_article_link(s.caption)
    if not link:
        raise HTTPException(409, "cannot find article link in review caption")
    article = art_repo.get_by_canonical(link)
    if article is None:
        raise HTTPException(409, f"article not found for link {link}")

    # Если review был в IN_EDIT — выйти, чтобы builder.save не конфликтовал.
    if s.status is ReviewStatus.IN_EDIT:
        editor.cancel(review_id)
        s = repo.get(review_id)

    # Скрываем текущий reel под placeholder'ом на время полной пересборки.
    _swap_to_saving_placeholder(request, tg, s)

    builder.build(article, s)
    s = repo.get(review_id)

    # Заменяем видео + caption + клавиатуру в существующем сообщении.
    if s.message_id is not None:
        try:
            tg.edit_message_video_file(
                s.reviewer_chat_id,
                s.message_id,
                s.output_uri,
                caption=s.caption or "",
                reply_markup=_main_keyboard(review_id),
            )
        except Exception as e:
            raise HTTPException(502, f"telegram edit failed: {e}")
    return _state(s, editor)


def _swap_to_saving_placeholder(request, tg, s) -> None:
    """Подменить видео в чате оператора на чёрный 1-сек mp4 c caption
    «⏳ Сохраняю и пересобираю видео…», чтобы во время рендера он не
    залипал на последнем тапнутом клипе."""
    placeholder = getattr(request.app.state, "saving_placeholder", None)
    if not placeholder or s.message_id is None:
        return
    try:
        tg.edit_message_video_file(
            s.reviewer_chat_id,
            s.message_id,
            placeholder,
            caption="⏳ Сохраняю и пересобираю видео… (~20-40 с)",
            reply_markup={"inline_keyboard": []},
        )
    except Exception as e:
        logger.warning("placeholder swap failed for %s: %s", s.id, e)


@router.post("/{review_id}/save-edit")
def save_edit(
    request: Request,
    review_id: str,
    editor: Annotated[ReviewEditor, Depends(get_review_editor)],
    repo: Annotated[object, Depends(get_review_repo)],
    rebuilder: Annotated[ReelRebuilder, Depends(get_reel_rebuilder)],
    tg: Annotated[object, Depends(get_review_tg_client)],
):
    """💾 Сохранить в edit-mode: пересобрать reel из выбранных кандидатов
    (active_idx по сегментам), заменить видео в чате оператора, выйти
    из IN_EDIT в PENDING_REVIEW."""
    s = repo.get(review_id)
    if s is None:
        raise HTTPException(404, "review not found")
    # Если ничего не меняли — просто cancel-edit без пересборки.
    has_picks = any(
        int((seg or {}).get("active_idx", 0)) != 0
        for seg in (s.segments_snapshot or [])
    )
    if not has_picks:
        try:
            editor.cancel(review_id)
        except KeyError:
            raise HTTPException(404, "review not found")
        return _state(repo.get(review_id), editor)

    # Скрываем последний тапнутый клип под чёрным placeholder'ом + caption
    # с прогрессом — иначе оператор смотрит на стейл-клип ~30 секунд.
    _swap_to_saving_placeholder(request, tg, s)

    try:
        new_path = rebuilder.rebuild(s)
    except FileNotFoundError as e:
        logger.warning("save-edit failed for %s: work_dir/file gone: %s", review_id, e)
        raise HTTPException(409, f"work_dir gone: {e}")
    except ValueError as e:
        logger.warning("save-edit failed for %s: %s", review_id, e)
        raise HTTPException(409, str(e))
    except Exception as e:
        logger.exception("save-edit unexpected error for %s", review_id)
        raise HTTPException(500, f"rebuild failed: {e}")
    s.output_uri = new_path
    repo.save(s)

    # Заменяем видео в сообщении оператора + восстанавливаем главные кнопки.
    if s.message_id is not None:
        try:
            tg.edit_message_video_file(
                s.reviewer_chat_id,
                s.message_id,
                new_path,
                caption=s.caption or "",
                reply_markup=_main_keyboard(review_id),
            )
        except Exception as e:
            # Видео уже пересобрано на диске; bot покажет fallback-сообщение.
            raise HTTPException(502, f"telegram edit failed: {e}")

    try:
        editor.cancel(review_id)
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
