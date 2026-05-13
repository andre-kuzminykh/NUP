"""FastAPI application factory + production wiring of review services."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI

from nup_pipeline.api import deps
from nup_pipeline.api.routers import renders, reviews
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.elevenlabs_tts import ElevenLabsTTS
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.pexels import PexelsSearch
from nup_pipeline.infra.pixabay import PixabaySearch
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.candidate_refresher import CandidateRefresher
from nup_pipeline.services.reel_rebuilder import ReelRebuilder
from nup_pipeline.services.review_builder import ReviewBuilder
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

    # Refresher грузит свежие кандидаты + uploadит в Telegram через
    # тот же REVIEW_BOT_TOKEN, что и submit_for_review.
    review_token = os.environ.get("REVIEW_BOT_TOKEN") or bot_token
    refresh_tg = TelegramClient(token=review_token)
    pexels = PexelsSearch() if os.environ.get("PEXELS_API_KEY") else None
    pixabay = PixabaySearch() if os.environ.get("PIXABAY_API_KEY") else None
    llm = None
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from nup_pipeline.cli.news_loop import OpenAIJsonLlm
            llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
        except Exception as e:
            log.warning("LLM wiring failed for refresher: %s", e)
    refresher = CandidateRefresher(
        repo=repo, pexels=pexels, pixabay=pixabay,
        telegram=refresh_tg, llm=llm,
    )

    rebuilder = ReelRebuilder(runner=FfmpegRunner())

    art_repo = PostgresArticleRepo(db_url)
    tts = None
    review_builder = None
    if os.environ.get("ELEVENLABS_API_KEY") and llm is not None:
        try:
            tts = ElevenLabsTTS()
            review_builder = ReviewBuilder(
                llm=llm,
                tts=tts,
                pexels=pexels,
                pixabay=pixabay,
                telegram=refresh_tg,
                ffmpeg_runner=FfmpegRunner(),
                review_repo=repo,
                out_root=Path(os.environ.get("REELS_OUT_DIR", "/tmp")),
                candidates_per_segment=10,
            )
        except Exception as e:
            log.warning("ReviewBuilder wiring failed: %s", e)

    app.dependency_overrides[deps.get_review_repo] = lambda: repo
    app.dependency_overrides[deps.get_review_decider] = lambda: decider
    app.dependency_overrides[deps.get_review_editor] = lambda: editor
    app.dependency_overrides[deps.get_video_publisher] = lambda: video_publisher
    app.dependency_overrides[deps.get_candidate_refresher] = lambda: refresher
    app.dependency_overrides[deps.get_reel_rebuilder] = lambda: rebuilder
    app.dependency_overrides[deps.get_review_tg_client] = lambda: refresh_tg
    app.dependency_overrides[deps.get_article_repo] = lambda: art_repo
    app.dependency_overrides[deps.get_review_builder] = lambda: review_builder
    log.info("review services wired (Postgres + Telegram + Refresher + Rebuilder + Builder)")


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
