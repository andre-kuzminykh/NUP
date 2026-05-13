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

    async def _post(self, path: str, *, body: dict | None = None) -> dict:
        url = f"{self._base_url}/v1/reviews{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body) if body else await client.post(url)
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

    async def cancel_edit(self, review_id: str) -> dict:
        return await self._post(f"/{review_id}/cancel-edit")

    async def cancel_edit_revert(self, review_id: str) -> dict:
        return await self._post(f"/{review_id}/cancel-edit-revert")

    async def save_edit(self, review_id: str) -> dict:
        # Долго: бэкенд пересобирает reel (ffmpeg ~10-30 с) + uploads в Telegram.
        async with httpx.AsyncClient(timeout=180.0) as client:
            url = f"{self._base_url}/v1/reviews/{review_id}/save-edit"
            try:
                resp = await client.post(url)
            except httpx.HTTPError as e:
                raise BackendError(str(e)) from e
        if resp.status_code == 404:
            raise NotFoundError("save-edit")
        if resp.status_code >= 400:
            raise BackendError(f"backend {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    async def regenerate(self, review_id: str) -> dict:
        # Полная пересборка: ~3-5 мин (LLM + TTS + 140 preupload-ов + ffmpeg).
        async with httpx.AsyncClient(timeout=600.0) as client:
            url = f"{self._base_url}/v1/reviews/{review_id}/regenerate"
            try:
                resp = await client.post(url)
            except httpx.HTTPError as e:
                raise BackendError(str(e)) from e
        if resp.status_code == 404:
            raise NotFoundError("regenerate")
        if resp.status_code >= 400:
            raise BackendError(f"backend {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    async def move(self, review_id: str, direction: str) -> dict:
        return await self._post(f"/{review_id}/move", body={"direction": direction})

    async def pick(self, review_id: str, direction: str) -> dict:
        return await self._post(f"/{review_id}/pick", body={"direction": direction})

    async def refresh_candidates(self, review_id: str) -> dict:
        # Долго: бекенд качает + uploadит ~10 mp4 в Telegram. 30-60 с легко.
        async with httpx.AsyncClient(timeout=120.0) as client:
            url = f"{self._base_url}/v1/reviews/{review_id}/refresh-candidates"
            try:
                resp = await client.post(url)
            except httpx.HTTPError as e:
                raise BackendError(str(e)) from e
        if resp.status_code == 404:
            raise NotFoundError("refresh-candidates")
        if resp.status_code >= 400:
            raise BackendError(f"backend {resp.status_code}: {resp.text[:200]}")
        return resp.json()
