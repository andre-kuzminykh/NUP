"""F007 — Pixabay search fallback contract."""
from __future__ import annotations

import httpx
import pytest

from nup_pipeline.infra.pixabay import PixabayError, PixabaySearch


_FAKE = {
    "hits": [
        {
            "id": 100,
            "picture_id": "abc",
            "duration": 14,
            "videos": {
                "large": {"url": "https://x/large.mp4", "width": 1920, "height": 1080},
                "medium": {"url": "https://x/medium.mp4", "width": 720, "height": 1280},
                "small": {"url": "https://x/small.mp4", "width": 360, "height": 640},
            },
        },
        {
            "id": 200,
            "duration": 9,
            "videos": {"medium": {"url": "https://x/m2.mp4", "width": 540, "height": 960}},
        },
    ]
}


@pytest.mark.unit
def test_picks_first_portrait_clip_per_hit() -> None:
    def transport(params):
        assert params["q"] == "robotics"
        assert params["video_type"] == "film"
        return httpx.Response(200, json=_FAKE)

    out = PixabaySearch(api_key="k", transport=transport).search_videos("robotics")
    assert len(out) == 2
    # large is landscape → skipped, medium (720x1280) is the first portrait.
    assert out[0]["video_url"] == "https://x/medium.mp4"
    assert out[1]["video_url"] == "https://x/m2.mp4"


@pytest.mark.unit
def test_no_portrait_skipped() -> None:
    payload = {"hits": [{"videos": {"large": {"url": "https://x/l.mp4", "width": 1920, "height": 1080}}}]}

    def transport(params):
        return httpx.Response(200, json=payload)

    assert PixabaySearch(api_key="k", transport=transport).search_videos("q") == []


@pytest.mark.unit
def test_4xx_raises_pixabay_error() -> None:
    def transport(params):
        return httpx.Response(403, text="forbidden")

    with pytest.raises(PixabayError):
        PixabaySearch(api_key="k", transport=transport).search_videos("q")
