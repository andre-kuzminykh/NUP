"""Pixabay stock-video search — fallback к Pexels.

GET https://pixabay.com/api/videos/?key=<key>&q=<query>&per_page=N&video_type=film

Возвращает тот же контракт, что PexelsSearch: list[{video_url, preview_url, duration}].

Tested by tests/unit/test_pixabay.py.
"""
from __future__ import annotations

import os
from typing import Callable

import httpx

API_BASE = "https://pixabay.com/api/videos/"


class PixabayError(RuntimeError):
    pass


def _best_portrait_clip(videos_dict: dict) -> dict | None:
    """Pixabay-видео содержит несколько форматов: large/medium/small/tiny.
    Берём первый, у которого height > width (vertical), приоритет large→tiny.
    """
    for key in ("large", "medium", "small", "tiny"):
        f = videos_dict.get(key)
        if not isinstance(f, dict) or not f.get("url"):
            continue
        if int(f.get("height", 0)) > int(f.get("width", 0)):
            return {"url": f["url"], "width": f["width"], "height": f["height"]}
    return None


class PixabaySearch:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 15.0,
        transport: Callable[[dict], httpx.Response] | None = None,
    ) -> None:
        self._key = api_key or os.environ["PIXABAY_API_KEY"]
        self._timeout = timeout
        self._transport = transport

    def search_videos(
        self,
        query: str,
        *,
        per_page: int = 3,
        page: int = 1,
    ) -> list[dict]:
        params = {
            "key": self._key,
            "q": query,
            "per_page": max(3, per_page),
            "video_type": "film",
            "page": page,
        }
        if self._transport is not None:
            resp = self._transport(params)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(API_BASE, params=params)
        if resp.status_code >= 400:
            raise PixabayError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        out: list[dict] = []
        for hit in data.get("hits") or []:
            if not isinstance(hit, dict):
                continue
            best = _best_portrait_clip(hit.get("videos") or {})
            if not best:
                continue
            out.append(
                {
                    "video_url": best["url"],
                    "preview_url": hit.get("picture_id") or "",
                    "duration": hit.get("duration") or 0,
                    "width": best["width"],
                    "height": best["height"],
                }
            )
        return out
