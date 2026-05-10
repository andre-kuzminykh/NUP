"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI

from nup_pipeline.api.routers import renders


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
    return app


# uvicorn entrypoint:  uvicorn nup_pipeline.api.app:app
app = build_app()
