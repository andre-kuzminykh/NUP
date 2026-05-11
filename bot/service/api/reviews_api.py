"""
HTTP-клиент к бэкенду /v1/reviews.

## Трассируемость
Feature: F003 — Review callbacks (bilingual)
Scenarios: SC001 (approve), SC002 (decline), SC003 (edit start)

## Бизнес-контекст
Аналог renders_api: тонкая обёртка над httpx. На 404 кидает NotFoundError,
на 5xx / сетевые ошибки — BackendError.
"""
from __future__ import annotations

import httpx

from core.config import config


class BackendError(RuntimeError):
    pass


class NotFoundError(LookupError):
    pass


class ReviewsAPI:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url or config.BACKEND_URL
        self._timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT

    async def _post(self, path: str) -> dict:
        url = f"{self._base_url}/v1/reviews{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url)
        except httpx.HTTPError as e:
            raise BackendError(str(e)) from e
        if resp.status_code == 404:
            raise NotFoundError(path)
        if resp.status_code >= 400:
            raise BackendError(f"backend {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    async def approve(self, review_id: str) -> dict:
        return await self._post(f"/{review_id}/approve")

    async def decline(self, review_id: str) -> dict:
        return await self._post(f"/{review_id}/decline")

    async def start_edit(self, review_id: str) -> dict:
        return await self._post(f"/{review_id}/start-edit")
