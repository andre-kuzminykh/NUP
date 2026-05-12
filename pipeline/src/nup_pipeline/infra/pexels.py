"""Pexels stock-video search.

GET https://api.pexels.com/videos/search?query=<q>&per_page=N&orientation=portrait
   Header: Authorization: <key>

Возвращает список вертикальных видео-кандидатов:
[{video_url, preview_url, duration}, ...]

Tested by tests/unit/test_pexels.py.
"""
from __future__ import annotations

import os
from typing import Callable

import httpx

API_BASE = "https://api.pexels.com"


class PexelsError(RuntimeError):
    pass


def _best_portrait_file(video_files: list[dict]) -> dict | None:
    portrait = [
        f for f in video_files
        if isinstance(f, dict) and f.get("width") and f.get("height")
        and int(f["height"]) > int(f["width"])
    ]
    if not portrait:
        return None
    # Берём самый низкокачественный вариант ≥720 по высоте — это даёт
    # 2-5 MB файлы (vs 10-20 MB у HD/UHD) и легко проходит лимит Telegram
    # bot upload (50 MB) + быстрее грузится на телефоне в edit-mode preview.
    # Если в наборе нет 720+ — fallback на минимально доступный.
    candidates_720 = [f for f in portrait if int(f["height"]) >= 720]
    pool = candidates_720 if candidates_720 else portrait
    return min(pool, key=lambda f: int(f["height"]))


class PexelsSearch:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 15.0,
        transport: Callable[[str, dict], httpx.Response] | None = None,
    ) -> None:
        self._key = api_key or os.environ["PEXELS_API_KEY"]
        self._timeout = timeout
        self._transport = transport

    def search_videos(
        self,
        query: str,
        *,
        per_page: int = 3,
        orientation: str = "portrait",
        page: int = 1,
    ) -> list[dict]:
        url = f"{API_BASE}/videos/search?query={httpx.QueryParams({'q':query})['q']}"
        # use proper param encoding:
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
            "page": page,
        }
        headers = {"Authorization": self._key}
        if self._transport is not None:
            resp = self._transport(url, params)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{API_BASE}/videos/search", params=params, headers=headers,
                )
        if resp.status_code >= 400:
            raise PexelsError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        out: list[dict] = []
        for v in data.get("videos") or []:
            if not isinstance(v, dict):
                continue
            best = _best_portrait_file(v.get("video_files") or [])
            if not best:
                continue
            out.append(
                {
                    "video_url": best.get("link") or "",
                    "preview_url": v.get("image") or "",
                    "duration": v.get("duration") or 0,
                    "width": best.get("width"),
                    "height": best.get("height"),
                }
            )
        return out
