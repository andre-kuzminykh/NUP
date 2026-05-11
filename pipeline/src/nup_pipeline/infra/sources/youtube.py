"""F001 — YouTube channel URL → Atom-feed URL resolver.

YouTube не отдаёт RSS по @handle напрямую. Чтобы узнать channel_id вида
UC..., приходится сходить на HTML страницы канала и вытащить его регэкспом
из JSON, который YouTube вставляет в `<script>`.

Поддерживаемые входные URL:
  - https://www.youtube.com/feeds/videos.xml?channel_id=UC...    (уже фид → no-op)
  - https://www.youtube.com/channel/UC...                       (channel_id в пути)
  - https://www.youtube.com/@handle                             (нужен HTML fetch)
  - https://www.youtube.com/c/CustomName                        (нужен HTML fetch)

Tested by tests/unit/test_youtube_resolver.py.
"""
from __future__ import annotations

import re
from typing import Protocol

_CHANNEL_ID_RX = re.compile(r"(UC[A-Za-z0-9_-]{22})")


class _Fetcher(Protocol):
    def get(self, url: str, *, proxy: str | None = None) -> bytes: ...


def already_feed_url(url: str) -> bool:
    return "feeds/videos.xml?channel_id=" in url


def _try_extract_from_url(url: str) -> str | None:
    """If URL itself contains a UC-id (channel/<UC...> or feed query), return it."""
    if "feeds/videos.xml?channel_id=" in url:
        m = re.search(r"channel_id=(UC[A-Za-z0-9_-]{22})", url)
        return m.group(1) if m else None
    if "/channel/" in url:
        m = re.search(r"/channel/(UC[A-Za-z0-9_-]{22})", url)
        return m.group(1) if m else None
    return None


def _extract_from_html(html: str) -> str | None:
    """First UC-id that appears in the page — works for @handle and /c/ URLs."""
    # `"channelId":"UC..."` is the most reliable marker.
    m = re.search(r'"channelId":"(UC[A-Za-z0-9_-]{22})"', html)
    if m:
        return m.group(1)
    # Canonical link: <link rel="canonical" href=".../channel/UC..."
    m = re.search(r'canonical[^>]+href="[^"]*?/channel/(UC[A-Za-z0-9_-]{22})', html)
    if m:
        return m.group(1)
    # Last resort: any UC-id in the page (less safe, may pick a related channel).
    m = _CHANNEL_ID_RX.search(html)
    return m.group(1) if m else None


def resolve_feed_url(channel_url: str, fetcher: _Fetcher | None = None) -> str:
    """Возвращает Atom feed URL для канала.

    Если входной URL уже сам — feed, возвращает его как есть (без сетевых вызовов).
    Иначе нужен fetcher: ходит на страницу канала, выдёргивает channel_id.
    """
    direct = _try_extract_from_url(channel_url)
    if direct:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={direct}"

    if fetcher is None:
        raise ValueError(
            f"cannot resolve {channel_url!r} without a fetcher (need HTTP to extract channel_id)"
        )

    html = fetcher.get(channel_url).decode("utf-8", errors="ignore")
    cid = _extract_from_html(html)
    if not cid:
        raise LookupError(f"channel_id not found in {channel_url!r}")
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
