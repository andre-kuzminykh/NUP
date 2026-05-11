"""F001 + F002 + F003 — end-to-end orchestrator.

Для каждого активного источника: ingest → summarize → publish RU + EN.

Anti-flood (per-source silent first ingest):
Когда источник появляется в системе впервые (в `articles` нет ни одной строки
с его `source_id`), мы НЕ публикуем backlog в канал — просто сохраняем
текущие свежие item'ы в БД. На следующем тике публиковать будем только то,
что появилось в фиде ПОСЛЕ этого первого «тихого» ingest'а.

Это включается через `silent_first_seed=True` + переданный `article_repo`.
В тестах оба не передаются → flag отключён, поведение классическое.

Tested by tests/unit/test_news_to_channel.py.
"""
from __future__ import annotations

import logging
from typing import Protocol

from nup_pipeline.domain.article import Article
from nup_pipeline.domain.source import Source
from nup_pipeline.services.ingest import IngestService
from nup_pipeline.services.summarize import BilingualSummarizer, SummarizerError
from nup_pipeline.services.text_format import single_lang_post
from nup_pipeline.services.text_publication import TextPublisher

log = logging.getLogger(__name__)


class _Publisher(Protocol):
    def publish(self, chat_id: str, text: str): ...


class _ArticleReader(Protocol):
    def list_by_source(self, source_id: str) -> list[Article]: ...


class NewsToChannel:
    def __init__(
        self,
        ingest: IngestService,
        summarizer: BilingualSummarizer,
        publisher: TextPublisher | _Publisher,
        channel_id: str,
        *,
        article_repo: _ArticleReader | None = None,
        silent_first_seed: bool = False,
    ) -> None:
        self._ingest = ingest
        self._summarizer = summarizer
        self._publisher = publisher
        self._channel = channel_id
        self._repo = article_repo
        self._silent_first_seed = silent_first_seed and article_repo is not None

    def run_once(self, sources: list[Source]) -> dict[str, int]:
        stats = {"fetched": 0, "new": 0, "published": 0, "failed": 0, "silent_seeded": 0}
        for src in sources:
            # Pre-count BEFORE ingest — нам важно знать, был ли источник
            # «знаком» до этого tick'а. После ingest_source repo уже содержит
            # вновь сохранённые item'ы.
            had_any_before = False
            if self._silent_first_seed and self._repo is not None:
                had_any_before = bool(self._repo.list_by_source(src.id))

            new_articles: list[Article] = self._ingest.ingest_source(src)
            stats["fetched"] += len(new_articles)
            stats["new"] += len(new_articles)

            if self._silent_first_seed and not had_any_before and new_articles:
                # Первый ingest этого источника — публиковать не будем.
                stats["silent_seeded"] += len(new_articles)
                log.info(
                    "first-time ingest, items seeded silently",
                    extra={"source_id": src.id, "count": len(new_articles)},
                )
                continue

            for article in new_articles:
                try:
                    bundle = self._summarizer.summarize(article)
                except SummarizerError as e:
                    log.warning(
                        "summary failed",
                        extra={"article_id": article.id, "err": str(e)},
                    )
                    stats["failed"] += 1
                    continue
                ru_text = single_lang_post(
                    title=bundle.title_ru,
                    content=bundle.content_ru,
                    link=bundle.link,
                    lang="ru",
                )
                en_text = single_lang_post(
                    title=bundle.title_en,
                    content=bundle.content_en,
                    link=bundle.link,
                    lang="en",
                )
                for text in (ru_text, en_text):  # RU first, EN second
                    try:
                        self._publisher.publish(self._channel, text)
                        stats["published"] += 1
                    except Exception as e:
                        log.warning(
                            "publish failed",
                            extra={"article_id": article.id, "err": str(e)},
                        )
                        stats["failed"] += 1
        return stats
