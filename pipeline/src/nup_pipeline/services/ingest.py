"""F001 — IngestService: fetch → parse → dedupe → persist.

Tested by tests/unit/test_ingest_service.py and tests/unit/test_news_to_channel.py.
"""
from __future__ import annotations

import logging
from typing import Protocol

from nup_pipeline.domain.article import Article
from nup_pipeline.domain.source import Source, SourceKind
from nup_pipeline.infra.sources.rss import parse_rss

log = logging.getLogger(__name__)


class _Fetcher(Protocol):
    def get(self, url: str, *, proxy: str | None = None) -> bytes: ...


class _ArticleRepo(Protocol):
    def save(self, article: Article) -> bool: ...


class _ProxyPool(Protocol):
    def acquire(self) -> str | None: ...


class IngestService:
    def __init__(
        self,
        fetcher: _Fetcher,
        article_repo: _ArticleRepo,
        proxy_pool: _ProxyPool | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._repo = article_repo
        self._proxy = proxy_pool

    def ingest_source(self, source: Source) -> list[Article]:
        if not source.is_active:
            return []
        proxy = self._proxy.acquire() if self._proxy else None
        try:
            payload = self._fetcher.get(source.url, proxy=proxy)
        except Exception as e:
            log.warning("ingest fetch failed", extra={"source_id": source.id, "err": str(e)})
            return []

        if source.kind is SourceKind.RSS:
            items = parse_rss(payload)
        else:
            # HTML / YouTube / LinkedIn / X / Telegram adapters arrive next iter.
            log.info("source kind not yet implemented", extra={"kind": source.kind.value})
            items = []

        new: list[Article] = []
        for it in items:
            link = (it.get("link") or "").strip()
            if not link:
                continue
            article = Article(
                source_id=source.id,
                link=link,
                title=(it.get("title") or "").strip(),
                raw_content=(it.get("description") or "").strip(),
                published_at=(it.get("pub_date") or "") or None,
            )
            if self._repo.save(article):
                new.append(article)
        return new
