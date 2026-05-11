"""CLI: один прогон news_to_channel и выход. Удобно для отладки без ожидания
NEWS_LOOP_INTERVAL_SEC.

Примеры:
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once --source guardian-ai
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once --no-publish
        # ingest + summarise но НЕ публикует — чтобы засеять БД старыми статьями
        # и не залить канал.
    docker compose exec news-worker python -m nup_pipeline.cli.tick_once --seed
        # самый быстрый seed: только ingest, без LLM-вызовов.
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
    p.add_argument("--source", default=None,
                   help="Один источник по id (см. default_sources). Без флага — все.")
    p.add_argument("--no-publish", action="store_true",
                   help="Прогнать суммаризацию, но НЕ публиковать в канал.")
    p.add_argument("--seed", action="store_true",
                   help="Только ingest (без LLM, без TG). Засеять БД канонами ссылок.")
    p.add_argument("--limit", type=int, default=None,
                   help="Максимум N свежих item'ов на источник за этот tick "
                        "(переопределяет MAX_PER_SOURCE=10).")
    args = p.parse_args()

    sources = default_sources()
    if args.source:
        sources = [s for s in sources if s.id == args.source]
        if not sources:
            ids = ", ".join(s.id for s in default_sources())
            raise SystemExit(f"unknown source {args.source!r}; known: {ids}")

    # --seed: используем напрямую IngestService, минуя LLM и Telegram.
    if args.seed:
        from nup_pipeline.cli.news_loop import HttpxFetcher
        from nup_pipeline.infra.article_repo import InMemoryArticleRepo
        from nup_pipeline.services.ingest import IngestService
        import os

        database_url = os.environ.get("DATABASE_URL", "")
        if database_url:
            from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
            repo = PostgresArticleRepo(database_url)
        else:
            repo = InMemoryArticleRepo()
        ingest = IngestService(
            fetcher=HttpxFetcher(),
            article_repo=repo,
            max_per_source=args.limit if args.limit is not None else 10,
        )
        total_new = 0
        for src in sources:
            new = ingest.ingest_source(src)
            total_new += len(new)
            print(f"[{src.id}] new={len(new)}")
        print(json.dumps({"seeded_new": total_new}, indent=2, ensure_ascii=False))
        return

    orchestrator = _build_orchestrator(max_per_source=args.limit)
    if args.no_publish:
        # Подменяем publisher на no-op, чтобы пройти весь pipeline,
        # но НЕ слать сообщения в TG.
        class _NoopPublisher:
            def publish(self, chat_id, text):
                return None
        orchestrator._publisher = _NoopPublisher()
    stats = orchestrator.run_once(sources)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
