"""In-memory ArticleRepo (REQ-F01-006).

Производственная Postgres-реализация будет на этой же сигнатуре.
"""
from __future__ import annotations

from nup_pipeline.domain.article import Article
from nup_pipeline.infra.canonical import canonical_url


class InMemoryArticleRepo:
    def __init__(self) -> None:
        self._by_canonical: dict[str, Article] = {}
        self._by_source: dict[str, list[Article]] = {}

    def save(self, article: Article) -> bool:
        """Return True if the article was inserted, False if it was a duplicate."""
        key = canonical_url(article.link)
        if key in self._by_canonical:
            return False
        self._by_canonical[key] = article
        self._by_source.setdefault(article.source_id, []).append(article)
        return True

    def get_by_canonical(self, link: str) -> Article | None:
        return self._by_canonical.get(canonical_url(link))

    def all(self) -> list[Article]:
        return list(self._by_canonical.values())

    def list_by_source(self, source_id: str) -> list[Article]:
        return list(self._by_source.get(source_id, []))
