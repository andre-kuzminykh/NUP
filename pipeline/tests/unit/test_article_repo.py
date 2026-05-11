"""F001 — InMemoryArticleRepo: dedup by canonical link.

Traces: REQ-F01-006, REQ-F01-007.
"""
import pytest

from nup_pipeline.domain.article import Article
from nup_pipeline.infra.article_repo import InMemoryArticleRepo


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_save_returns_true_for_new_article() -> None:
    repo = InMemoryArticleRepo()
    a = Article(source_id="src-1", link="https://example.com/a", title="A", raw_content="…")
    is_new = repo.save(a)
    assert is_new is True
    assert repo.get_by_canonical("https://example.com/a") is not None


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_duplicate_link_with_utm_is_ignored() -> None:
    repo = InMemoryArticleRepo()
    repo.save(Article(source_id="src-1", link="https://example.com/a", title="A", raw_content="…"))
    second = Article(
        source_id="src-1",
        link="https://Example.com/a?utm_source=newsletter#frag",
        title="A",
        raw_content="…",
    )
    is_new = repo.save(second)
    assert is_new is False
    assert len(repo.all()) == 1


@pytest.mark.unit
@pytest.mark.req("REQ-F01-007")
def test_can_query_by_source() -> None:
    repo = InMemoryArticleRepo()
    repo.save(Article(source_id="src-1", link="https://a.example/1", title="t", raw_content="b"))
    repo.save(Article(source_id="src-2", link="https://b.example/1", title="t", raw_content="b"))
    repo.save(Article(source_id="src-1", link="https://a.example/2", title="t", raw_content="b"))
    assert len(repo.list_by_source("src-1")) == 2
    assert len(repo.list_by_source("src-2")) == 1
