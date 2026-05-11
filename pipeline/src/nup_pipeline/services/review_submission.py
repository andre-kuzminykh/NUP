"""F011 — ReviewSubmitter.

Отправляет финальный Reels оператору в личку с inline-клавиатурой
[Approve / Decline / Edit] и фиксирует ReviewSession в БД.

Tested by tests/unit/test_review_submission.py.
"""
from __future__ import annotations

from typing import Any, Protocol

from nup_pipeline.domain.render_job import RenderJob, RenderStatus
from nup_pipeline.domain.review import (
    IllegalReviewStateError,
    ReviewSession,
    ReviewStatus,
)
from nup_pipeline.services.text_format import bilingual_caption


class _RenderJobReader(Protocol):
    def get(self, job_id: str) -> RenderJob | None: ...


class _ReviewRepo(Protocol):
    def get_by_render_job(self, render_job_id: str) -> ReviewSession | None: ...
    def save(self, r: ReviewSession) -> None: ...


class _TelegramVideoPort(Protocol):
    def send_video(
        self, chat_id, video_url, *, caption=None, reply_markup=None
    ) -> int: ...


def _build_keyboard(review_id: str) -> dict:
    """Inline keyboard with bilingual labels and review-scoped callback_data."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve / Одобрить", "callback_data": f"review:approve:{review_id}"},
            ],
            [
                {"text": "❌ Decline / Отклонить", "callback_data": f"review:decline:{review_id}"},
                {"text": "✏️ Edit / Править", "callback_data": f"review:edit:{review_id}"},
            ],
        ]
    }


class ReviewSubmitter:
    def __init__(
        self,
        render_job_repo: _RenderJobReader,
        review_repo: _ReviewRepo,
        telegram: _TelegramVideoPort,
    ) -> None:
        self._jobs = render_job_repo
        self._reviews = review_repo
        self._tg = telegram

    def submit(
        self,
        render_job_id: str,
        reviewer_chat_id: int,
        channel_id: int,
        caption_bundle: dict[str, Any],
    ) -> ReviewSession:
        existing = self._reviews.get_by_render_job(render_job_id)
        if existing is not None:
            return existing  # REQ-F011-006

        job = self._jobs.get(render_job_id)
        if job is None:
            raise IllegalReviewStateError(f"render job {render_job_id} not found")
        if job.status is not RenderStatus.SUCCEEDED or not job.output_uri:
            raise IllegalReviewStateError(
                f"render job {render_job_id} is {job.status.value}, expected succeeded"
            )

        session = ReviewSession.new(
            render_job_id=render_job_id,
            reviewer_chat_id=reviewer_chat_id,
            channel_id=channel_id,
        )
        session.output_uri = job.output_uri
        session.caption = bilingual_caption(
            title_ru=caption_bundle.get("title_ru", ""),
            content_ru=caption_bundle.get("content_ru", ""),
            title_en=caption_bundle.get("title_en", ""),
            content_en=caption_bundle.get("content_en", ""),
            link=caption_bundle.get("link"),
        )
        # Сохраняем в БД до отправки в TG, чтобы callback_data ссылался на
        # существующую строку — даже если send_video упадёт, оператор не
        # увидит «висящих» сообщений с битым review_id.
        self._reviews.save(session)

        message_id = self._tg.send_video(
            reviewer_chat_id,
            session.output_uri,
            caption=session.caption,
            reply_markup=_build_keyboard(session.id),
        )
        session.message_id = message_id
        self._reviews.save(session)
        return session
