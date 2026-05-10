"""FastAPI dependency providers.

In production these wire to real Postgres/MinIO; in tests they are overridden
via app.dependency_overrides[...] to inject in-memory fakes.
"""
from __future__ import annotations

from nup_pipeline.services.video_assembly import AssembleService


def get_assemble_service() -> AssembleService:  # pragma: no cover - production wiring
    raise RuntimeError(
        "get_assemble_service must be overridden via app.dependency_overrides "
        "or wired in api.app.build_app(production=True)."
    )
