"""CLI: пробег по всем источникам, печатает таблицу статуса.

Запуск:
    docker compose exec news-worker python -m nup_pipeline.cli.sources_check

Колонки:
    ID        — id источника (как в default_sources)
    KIND      — rss / youtube_channel / ... — что объявлено в Source
    STATUS    — OK / EMPTY / FAIL
    ITEMS     — сколько свежих item'ов вернул feed
    URL       — фид
И отдельной строкой ниже — заголовок самого свежего item'а, чтобы убедиться,
что данные релевантные.
"""
from __future__ import annotations

import sys

from nup_pipeline.cli.news_loop import HttpxFetcher
from nup_pipeline.cli.sources import default_sources
from nup_pipeline.infra.sources.rss import parse_rss


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
        try:
            payload = fetcher.get(src.url)
            items = parse_rss(payload)
            status = "OK" if items else "EMPTY"
            count = len(items)
        except Exception as e:
            status = "FAIL"
            count = 0
            items = []
            err = str(e)[:80]
        else:
            err = None

        print(
            f"{src.id:<26}  {src.kind.value:<18}  {status:<8}  {count:>6}  {src.url}"
        )
        if status == "OK" and items:
            print(f"    └─ latest: {items[0]['title'][:90]}")
        elif status == "FAIL":
            print(f"    └─ error:  {err}")
            overall_fail += 1
        elif status == "EMPTY":
            print(f"    └─ feed parsed but returned 0 items (selector / namespace mismatch?)")

    print("-" * 120)
    print(f"{len(sources)} sources, {overall_fail} failures")
    return 1 if overall_fail else 0


if __name__ == "__main__":
    sys.exit(main())
