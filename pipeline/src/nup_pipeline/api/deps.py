"""FastAPI dependency providers.

Production wiring строится один раз в api/app.py на основе env.
В тестах прокидываются in-memory заглушки через app.dependency_overrides.
"""
from __future__ import annotations

from nup_pipeline.services.candidate_refresher import CandidateRefresher
from nup_pipeline.services.review_decision import ReviewDecider
from nup_pipeline.services.review_editor import ReviewEditor
from nup_pipeline.services.video_assembly import AssembleService
from nup_pipeline.services.video_publication import VideoPublisher


def get_assemble_service() -> AssembleService:  # pragma: no cover
    raise RuntimeError(
        "get_assemble_service must be overridden via app.dependency_overrides "
        "or wired in api.app.build_app()."
    )


def get_review_repo():  # pragma: no cover
    raise RuntimeError("get_review_repo must be wired in api.app")


def get_review_decider() -> ReviewDecider:  # pragma: no cover
    raise RuntimeError("get_review_decider must be wired in api.app")


def get_review_editor() -> ReviewEditor:  # pragma: no cover
    raise RuntimeError("get_review_editor must be wired in api.app")


def get_video_publisher() -> VideoPublisher:  # pragma: no cover
    raise RuntimeError("get_video_publisher must be wired in api.app")


def get_candidate_refresher() -> CandidateRefresher:  # pragma: no cover
    raise RuntimeError("get_candidate_refresher must be wired in api.app")


def get_reel_rebuilder():  # pragma: no cover
    raise RuntimeError("get_reel_rebuilder must be wired in api.app")


def get_review_tg_client():  # pragma: no cover
    raise RuntimeError("get_review_tg_client must be wired in api.app")


def get_review_builder():  # pragma: no cover
    raise RuntimeError("get_review_builder must be wired in api.app")


def get_article_repo():  # pragma: no cover
    raise RuntimeError("get_article_repo must be wired in api.app")
