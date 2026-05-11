"""F001 — Product Hunt leaderboard adapter.

`producthunt.com/feed` отдаёт перемешанный список свежих запусков + служебные
блоки ('Launching Today / Day Rank'), не годится для «продукта дня».

Этот адаптер строит URL ранкинга за вчера (Product Hunt:
/leaderboard/daily/YYYY/M/D), вытаскивает встроенный JSON-стейт страницы,
находит пост с `dailyRank == "1"` и возвращает один item:
title (имя продукта), link (https://www.producthunt.com/posts/slug),
description (tagline), pub_date пуст.

Tested by tests/unit/test_producthunt_adapter.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

_BASE = "https://www.producthunt.com"

# Несколько возможных шаблонов, в которых PH встраивает SSR-стейт.
# Пробуем по очереди.
_PATTERNS = [
    re.compile(r'"homefeed"\s*:\s*\{[^{]*?"items"\s*:\s*(\[.+?\])\s*[,}]', re.DOTALL),
    re.compile(r'"leaderboardFeed"\s*:\s*\{[^{]*?"items"\s*:\s*(\[.+?\])\s*[,}]', re.DOTALL),
    re.compile(r'"posts"\s*:\s*\{[^{]*?"edges"\s*:\s*(\[.+?\])\s*[,}]', re.DOTALL),
    re.compile(r'"items"\s*:\s*(\[\s*\{[^\[\]]*?"__typename"\s*:\s*"Post".+?\])', re.DOTALL),
]


def yesterday_url(now: datetime | None = None) -> str:
    """Сегодняшнее UTC-вчера в формате, который понимает PH leaderboard."""
    today = now or datetime.now(tz=timezone.utc)
    y = today - timedelta(days=1)
    return f"{_BASE}/leaderboard/daily/{y.year}/{y.month}/{y.day}"


def parse_producthunt_leaderboard(html_bytes: bytes) -> list[dict]:
    """Return [{title, link, description, pub_date}] for daily product #1.

    Strategy: regex-extract the JSON array of `homefeed.items` embedded in
    the SSR page, parse it, pick the entry with `dailyRank == "1"` (or
    fallback to the first Post if no ranks are present).
    """
    text = html_bytes.decode("utf-8", errors="ignore")

    items: list[dict] = []
    for rx in _PATTERNS:
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

    # PH иногда хранит как [{"node":{...}}, ...] для edges-API, а иногда как
    # прямые объекты. Нормализуем.
    flat = []
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("node"), dict):
            flat.append(it["node"])
        else:
            flat.append(it)
    posts = [x for x in flat if isinstance(x, dict) and x.get("__typename") in ("Post", None)
             and (x.get("name") or x.get("slug"))]
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
