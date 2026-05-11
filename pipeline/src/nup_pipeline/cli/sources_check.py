"""CLI: пробег по всем источникам, печатает таблицу статуса.

Запуск:
    docker compose exec news-worker python -m nup_pipeline.cli.sources_check

Колонки:
    ID, KIND, STATUS, ITEMS, URL. Для каждого OK-источника — заголовок
    самого свежего item'а, чтобы убедиться, что данные релевантные.

Использует ту же резолв-цепочку, что IngestService: для YouTube-источников
делает шаг @handle → channel_id → Atom feed.
"""
from __future__ import annotations

import sys

from nup_pipeline.cli.news_loop import HttpxFetcher
from nup_pipeline.cli.sources import default_sources
from nup_pipeline.domain.source import SourceKind
from nup_pipeline.infra.sources.rss import parse_rss
from nup_pipeline.infra.sources.youtube import already_feed_url, resolve_feed_url

COLS = (("ID", 26), ("KIND", 18), ("STATUS", 8), ("ITEMS", 6))


def _hdr() -> str:
    return "  ".join(f"{name:<{w}}" for name, w in COLS) + "  URL"


def main() -> int:
    fetcher = HttpxFetcher(timeout=15.0)
    sources = default_sources()
    print(_hdr())
    print("-" * 120)

    overall_fail = 0
    for src in sources:
        # Эффективный URL, с которого мы хотим качать XML: для YouTube — после
        # резолва @handle / /c/ → feeds/videos.xml?channel_id=…
        effective_url = src.url
        status = "OK"
        count = 0
        items: list[dict] = []
        err: str | None = None

        try:
            if src.kind is SourceKind.YOUTUBE_CHANNEL and not already_feed_url(effective_url):
                effective_url = resolve_feed_url(src.url, fetcher=fetcher)
            payload = fetcher.get(effective_url)
            items = parse_rss(payload)
            status = "OK" if items else "EMPTY"
            count = len(items)
        except Exception as e:
            status = "FAIL"
            err = str(e)[:80]

        # Print row: показываем оригинальный URL источника, чтобы было удобно
        # править его в sources.py. resolved URL пишем второй строкой, если он
        # отличается.
        print(
            f"{src.id:<26}  {src.kind.value:<18}  {status:<8}  {count:>6}  {src.url}"
        )
        if effective_url != src.url:
            print(f"    └─ resolved: {effective_url}")
        if status == "OK" and items:
            print(f"    └─ latest:   {items[0]['title'][:90]}")
        elif status == "FAIL":
            print(f"    └─ error:    {err}")
            overall_fail += 1
        elif status == "EMPTY":
            print(f"    └─ feed parsed but returned 0 items")

    print("-" * 120)
    print(f"{len(sources)} sources, {overall_fail} failures")
    return 1 if overall_fail else 0


if __name__ == "__main__":
    sys.exit(main())
