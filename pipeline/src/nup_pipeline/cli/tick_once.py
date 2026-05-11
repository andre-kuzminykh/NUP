"""CLI: один прогон news_to_channel и выход. Удобно для отладки без ожидания
NEWS_LOOP_INTERVAL_SEC.

Запуск в контейнере:
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once --source guardian-ai
"""
from __future__ import annotations

import argparse
import json
import logging

from nup_pipeline.cli.news_loop import _build_orchestrator
from nup_pipeline.cli.sources import default_sources


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Run news_to_channel one tick and exit.")
    p.add_argument(
        "--source",
        help="Один источник по id (см. default_sources). Без флага — все.",
        default=None,
    )
    args = p.parse_args()

    sources = default_sources()
    if args.source:
        sources = [s for s in sources if s.id == args.source]
        if not sources:
            ids = ", ".join(s.id for s in default_sources())
            raise SystemExit(f"unknown source {args.source!r}; known: {ids}")

    orchestrator = _build_orchestrator()
    stats = orchestrator.run_once(sources)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
