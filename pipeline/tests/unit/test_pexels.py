"""F007 — Pexels search contract."""
from __future__ import annotations

import httpx
import pytest

from nup_pipeline.infra.pexels import PexelsError, PexelsSearch


_FAKE_RESPONSE = {
    "videos": [
        {
            "id": 1,
            "image": "https://pexels.com/preview1.jpg",
            "duration": 12,
            "video_files": [
                {"link": "https://x/landscape.mp4", "width": 1920, "height": 1080},
                {"link": "https://x/portrait_low.mp4", "width": 540, "height": 960},
                {"link": "https://x/portrait_high.mp4", "width": 1080, "height": 1920},
            ],
        },
        {
            "id": 2,
            "image": "https://pexels.com/preview2.jpg",
            "duration": 8,
            "video_files": [
                {"link": "https://x/portrait_2.mp4", "width": 720, "height": 1280},
            ],
        },
    ]
}


@pytest.mark.unit
def test_search_returns_normalized_items_with_highest_portrait() -> None:
    def transport(url, params):
        assert params["query"] == "AI robots"
        assert params["orientation"] == "portrait"
        return httpx.Response(200, json=_FAKE_RESPONSE)

    out = PexelsSearch(api_key="k", transport=transport).search_videos("AI robots")
    assert len(out) == 2
    # Highest portrait of first video wins.
    assert out[0]["video_url"] == "https://x/portrait_high.mp4"
    assert out[0]["height"] == 1920
    assert out[1]["video_url"] == "https://x/portrait_2.mp4"


@pytest.mark.unit
def test_video_without_portrait_files_skipped() -> None:
    payload = {
        "videos": [
            {
                "video_files": [
                    {"link": "https://x/only-landscape.mp4", "width": 1920, "height": 1080},
                ],
            }
        ]
    }

    def transport(url, params):
        return httpx.Response(200, json=payload)

    out = PexelsSearch(api_key="k", transport=transport).search_videos("q")
    assert out == []


@pytest.mark.unit
def test_4xx_raises_pexels_error() -> None:
    def transport(url, params):
        return httpx.Response(429, text="rate limited")

    with pytest.raises(PexelsError):
        PexelsSearch(api_key="k", transport=transport).search_videos("q")
