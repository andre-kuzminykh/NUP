"""FastAPI application factory + production wiring of review services."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from nup_pipeline.api import deps
from nup_pipeline.api.routers import renders, reviews
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.review_decision import ReviewDecider
from nup_pipeline.services.review_editor import ReviewEditor
from nup_pipeline.services.video_publication import VideoPublisher

log = logging.getLogger(__name__)


def _wire_review_services(app: FastAPI) -> None:
    """Подключить production-инстансы review-сервисов к FastAPI DI.

    Если переменные окружения не заданы (DATABASE_URL / TELEGRAM_BOT_TOKEN) —
    пропускаем wiring, чтобы импорт модуля не падал в тестах.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not (db_url and bot_token):
        log.warning(
            "review services NOT wired: DATABASE_URL or TELEGRAM_BOT_TOKEN missing"
        )
        return

    repo = PostgresReviewRepo(db_url)

    class _InMemPubRepo:
        def __init__(self) -> None:
            self.rows: list = []
        def save(self, p) -> None:
            self.rows.append(p)

    tg = TelegramClient(token=bot_token)
    video_publisher = VideoPublisher(client=tg, repo=_InMemPubRepo())
    decider = ReviewDecider(review_repo=repo, video_publisher=video_publisher)
    editor = ReviewEditor(repo=repo)

    app.dependency_overrides[deps.get_review_repo] = lambda: repo
    app.dependency_overrides[deps.get_review_decider] = lambda: decider
    app.dependency_overrides[deps.get_review_editor] = lambda: editor
    app.dependency_overrides[deps.get_video_publisher] = lambda: video_publisher
    log.info("review services wired (Postgres + Telegram)")


def build_app() -> FastAPI:
    app = FastAPI(
        title="NUP Pipeline API",
        version="0.1.0",
        description=(
            "Self-hosted pipeline replacing the n8n flow. "
            "Postgres replaces Google Sheets; FFmpeg replaces Shotstack."
        ),
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(renders.router)
    app.include_router(reviews.router)

    _wire_review_services(app)
    return app


# uvicorn entrypoint:  uvicorn nup_pipeline.api.app:app
app = build_app()
