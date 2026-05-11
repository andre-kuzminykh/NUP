"""F001 + F002 + F003 — end-to-end orchestrator.

For each active source: ingest new articles, summarise each (RU + EN),
publish the bilingual caption to the target channel via TextPublisher.

Tested by tests/unit/test_news_to_channel.py.
"""
from __future__ import annotations

import logging
from typing import Protocol

from nup_pipeline.domain.article import Article
from nup_pipeline.domain.source import Source
from nup_pipeline.services.ingest import IngestService
from nup_pipeline.services.summarize import BilingualSummarizer, SummarizerError
from nup_pipeline.services.text_format import bilingual_caption
from nup_pipeline.services.text_publication import TextPublisher

log = logging.getLogger(__name__)


class _Publisher(Protocol):
    def publish(self, chat_id: str, text: str): ...


class NewsToChannel:
    def __init__(
        self,
        ingest: IngestService,
        summarizer: BilingualSummarizer,
        publisher: TextPublisher | _Publisher,
        channel_id: str,
    ) -> None:
        self._ingest = ingest
        self._summarizer = summarizer
        self._publisher = publisher
        self._channel = channel_id

    def run_once(self, sources: list[Source]) -> dict[str, int]:
        stats = {"fetched": 0, "new": 0, "published": 0, "failed": 0}
        for src in sources:
            new_articles: list[Article] = self._ingest.ingest_source(src)
            stats["fetched"] += len(new_articles)
            stats["new"] += len(new_articles)
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
                caption = bilingual_caption(
                    title_ru=bundle.title_ru,
                    content_ru=bundle.content_ru,
                    title_en=bundle.title_en,
                    content_en=bundle.content_en,
                    link=bundle.link,
                )
                try:
                    self._publisher.publish(self._channel, caption)
                    stats["published"] += 1
                except Exception as e:
                    log.warning(
                        "publish failed",
                        extra={"article_id": article.id, "err": str(e)},
                    )
                    stats["failed"] += 1
        return stats
