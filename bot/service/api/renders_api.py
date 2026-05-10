"""
HTTP-клиент к бэкенду /v1/renders.

## Трассируемость
Feature: F002 — Render job status
Scenarios: SC001, SC002

## Бизнес-контекст
Бот не подключается к БД. Любые данные о рендер-задачах он берёт
через REST у backend-сервиса (см. pipeline/openapi.yaml).
"""
from __future__ import annotations

import httpx

from core.config import config


class BackendError(RuntimeError):
    """Generic backend failure (5xx, network)."""


class NotFoundError(LookupError):
    """Backend returned 404 for the requested resource."""


class RendersAPI:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url or config.BACKEND_URL
        self._timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT

    async def get(self, job_id: str) -> dict:
        """GET /v1/renders/{job_id}.

        Raises NotFoundError on 404, BackendError on any other non-2xx.
        """
        url = f"{self._base_url}/v1/renders/{job_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
        except httpx.HTTPError as e:
            raise BackendError(str(e)) from e
        if resp.status_code == 404:
            raise NotFoundError(job_id)
        if resp.status_code >= 400:
            raise BackendError(f"backend {resp.status_code}: {resp.text[:200]}")
        return resp.json()
