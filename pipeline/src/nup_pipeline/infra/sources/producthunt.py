"""F001 — Product Hunt leaderboard adapter.

`producthunt.com/feed` отдаёт перемешанный список свежих запусков + служебные
блоки ('Launching Today / Day Rank'), не годится для «продукта дня».

Этот адаптер ходит на /leaderboard/daily/yesterday и вытаскивает встроенный
JSON-стейт, находит пост с `dailyRank == "1"` и возвращает один item:
title (имя продукта), link (https://www.producthunt.com/posts/slug),
description (tagline), pub_date пуст.

Tested by tests/unit/test_producthunt_adapter.py.
"""
from __future__ import annotations

import json
import re

_BASE = "https://www.producthunt.com"
_ITEMS_RX = re.compile(
    r'"homefeed"\s*:\s*\{[^{]*?"items"\s*:\s*(\[.+?\])\s*[,}]',
    re.DOTALL,
)
# Generic fallback: search for any items-array containing Post entries.
_GENERIC_ITEMS_RX = re.compile(r'"items"\s*:\s*(\[\s*\{[^\[\]]*?"__typename"\s*:\s*"Post".+?\])',
                               re.DOTALL)


def parse_producthunt_leaderboard(html_bytes: bytes) -> list[dict]:
    """Return [{title, link, description, pub_date}] for daily product #1.

    Strategy: regex-extract the JSON array of `homefeed.items` embedded in
    the SSR page, parse it, pick the entry with `dailyRank == "1"` (or
    fallback to the first Post if no ranks are present).
    """
    text = html_bytes.decode("utf-8", errors="ignore")

    items: list[dict] = []
    for rx in (_ITEMS_RX, _GENERIC_ITEMS_RX):
        m = rx.search(text)
        if not m:
            continue
        try:
            decoded = json.loads(m.group(1))
            if isinstance(decoded, list):
                items = decoded
                break
        except json.JSONDecodeError:
            continue

    if not items:
        return []

    posts = [x for x in items if isinstance(x, dict) and x.get("__typename") == "Post"]
    if not posts:
        return []

    # Prefer dailyRank == "1"; otherwise the first Post in the feed.
    rank_one = next((p for p in posts if str(p.get("dailyRank") or "") == "1"), None)
    pick = rank_one or posts[0]

    name = (pick.get("name") or "").strip()
    tagline = (pick.get("tagline") or "").strip()
    shortened = (pick.get("shortenedUrl") or "").strip()
    slug = ""
    product = pick.get("product")
    if isinstance(product, dict):
        slug = (product.get("slug") or "").strip()

    if shortened:
        link = shortened if shortened.startswith("http") else f"{_BASE}{shortened}"
    elif slug:
        link = f"{_BASE}/products/{slug}"
    else:
        return []

    if not name:
        return []

    return [
        {
            "title": name,
            "link": link,
            "description": tagline,
            "pub_date": "",
        }
    ]
