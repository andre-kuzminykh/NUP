"""F011/F012/F013 — Persistent ReviewSession storage (Postgres / SQLite).

Хранит:
- статус (pending_review/approved/declined/in_edit)
- output_uri (URL финального MP4)
- caption (тот же текст, что отправлен оператору)
- message_id (id сообщения в чате оператора — для edit_reply_markup)
- segments_snapshot (JSONB): список сегментов с тремя кандидатами на каждый
  кадр, для frame-edit UX. Структура:
    [
      {"text": "...", "audio_path": "/app/reels_out/.../voice_00.mp3",
       "candidates": [
         {"video_url": "...", "local_path": "...", "preview_url": "..."},
         ...
       ],
       "active_idx": 0},
      ...
    ]
- edit_state (JSONB): {"cursor": 0} — индекс текущего сегмента в edit-mode.

Tested by tests/unit/test_review_repo_pg.py.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    select,
)
from sqlalchemy.orm import sessionmaker

from nup_pipeline.domain.review import ReviewSession, ReviewStatus
from nup_pipeline.infra.db import Base, make_engine


class _ReviewRow(Base):
    __tablename__ = "reviews"
    id = Column(String, primary_key=True)
    render_job_id = Column(String, nullable=False)
    reviewer_chat_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    message_id = Column(Integer, nullable=True)
    output_uri = Column(String, nullable=True)
    caption = Column(String, nullable=True)
    publication_message_id = Column(Integer, nullable=True)
    # Используем JSON, не JSONB: совместимость с SQLite для unit-тестов.
    segments_snapshot = Column(JSON, nullable=True)
    edit_state = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


def _row_to_domain(r: _ReviewRow) -> ReviewSession:
    sess = ReviewSession(
        id=r.id,
        render_job_id=r.render_job_id,
        reviewer_chat_id=r.reviewer_chat_id,
        channel_id=r.channel_id,
        status=ReviewStatus(r.status),
        message_id=r.message_id,
        output_uri=r.output_uri,
        caption=r.caption,
        publication_message_id=r.publication_message_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
    sess.segments_snapshot = r.segments_snapshot
    sess.edit_state = r.edit_state
    return sess


class PostgresReviewRepo:
    def __init__(self, database_url: str) -> None:
        self._engine = make_engine(database_url)
        Base.metadata.create_all(self._engine, tables=[_ReviewRow.__table__])
        self._Session = sessionmaker(self._engine, expire_on_commit=False)

    def save(self, r: ReviewSession) -> None:
        with self._Session() as s:
            row = s.get(_ReviewRow, r.id)
            payload = {
                "id": r.id,
                "render_job_id": r.render_job_id,
                "reviewer_chat_id": r.reviewer_chat_id,
                "channel_id": r.channel_id,
                "status": r.status.value,
                "message_id": r.message_id,
                "output_uri": r.output_uri,
                "caption": r.caption,
                "publication_message_id": r.publication_message_id,
                "segments_snapshot": r.segments_snapshot,
                "edit_state": r.edit_state,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            if row is None:
                s.add(_ReviewRow(**payload))
            else:
                for k, v in payload.items():
                    setattr(row, k, v)
            s.commit()

    def get(self, review_id: str) -> ReviewSession | None:
        with self._Session() as s:
            row = s.get(_ReviewRow, review_id)
            return _row_to_domain(row) if row else None

    def get_by_render_job(self, render_job_id: str) -> ReviewSession | None:
        with self._Session() as s:
            row = s.execute(
                select(_ReviewRow).where(_ReviewRow.render_job_id == render_job_id)
            ).scalar_one_or_none()
            return _row_to_domain(row) if row else None
