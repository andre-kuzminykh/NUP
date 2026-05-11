"""F001 — Persistent ArticleRepo on SQLAlchemy.

Same contract as InMemoryArticleRepo:
- save(article) -> bool  (True if inserted, False if dup canonical link)
- get_by_canonical(link)
- list_by_source(source_id)
- all()

Works on Postgres in production and on SQLite for unit tests — dedup is
enforced by the UNIQUE constraint on `canonical_link`, and the repo catches
IntegrityError to map it onto False (no engine-specific SQL).

Tested by tests/unit/test_article_repo_pg.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from nup_pipeline.domain.article import Article
from nup_pipeline.infra.canonical import canonical_url
from nup_pipeline.infra.db import Base, make_engine


class _ArticleRow(Base):
    __tablename__ = "articles"
    id = Column(String, primary_key=True)
    source_id = Column(String, nullable=False, index=True)
    canonical_link = Column(String, nullable=False, unique=True)
    raw_link = Column(String, nullable=False)
    title = Column(String, nullable=False, default="")
    raw_content = Column(String, nullable=False, default="")
    published_at = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_articles_source_created", "source_id", "created_at"),)


def _to_domain(row: _ArticleRow) -> Article:
    return Article(
        id=row.id,
        source_id=row.source_id,
        link=row.raw_link,
        title=row.title or "",
        raw_content=row.raw_content or "",
        published_at=row.published_at,
        created_at=row.created_at,
    )


class PostgresArticleRepo:
    def __init__(self, database_url: str) -> None:
        self._engine = make_engine(database_url)
        Base.metadata.create_all(self._engine, tables=[_ArticleRow.__table__])
        self._Session = sessionmaker(self._engine, expire_on_commit=False)

    def save(self, article: Article) -> bool:
        key = canonical_url(article.link)
        with self._Session() as s:
            row = _ArticleRow(
                id=article.id,
                source_id=article.source_id,
                canonical_link=key,
                raw_link=article.link,
                title=article.title or "",
                raw_content=article.raw_content or "",
                published_at=article.published_at,
                created_at=article.created_at,
            )
            s.add(row)
            try:
                s.commit()
                return True
            except IntegrityError:
                s.rollback()
                return False

    def get_by_canonical(self, link: str) -> Article | None:
        key = canonical_url(link)
        with self._Session() as s:
            row = s.execute(
                select(_ArticleRow).where(_ArticleRow.canonical_link == key)
            ).scalar_one_or_none()
            return _to_domain(row) if row else None

    def list_by_source(self, source_id: str) -> list[Article]:
        with self._Session() as s:
            rows = s.execute(
                select(_ArticleRow).where(_ArticleRow.source_id == source_id)
            ).scalars().all()
            return [_to_domain(r) for r in rows]

    def all(self) -> list[Article]:
        with self._Session() as s:
            rows = s.execute(select(_ArticleRow)).scalars().all()
            return [_to_domain(r) for r in rows]
