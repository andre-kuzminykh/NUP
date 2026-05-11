"""F001 — PostgresArticleRepo via SQLite (so unit tests don't need a real Postgres).

Traces: REQ-F01-006, REQ-F01-007.
"""
import os
import tempfile

import pytest

from nup_pipeline.domain.article import Article
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo


@pytest.fixture
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield PostgresArticleRepo(f"sqlite:///{path}")
    os.unlink(path)


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_save_returns_true_for_new(repo) -> None:
    is_new = repo.save(Article(source_id="s", link="https://example.com/a", title="t"))
    assert is_new is True
    assert len(repo.all()) == 1


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_duplicate_canonical_returns_false(repo) -> None:
    repo.save(Article(source_id="s", link="https://example.com/a", title="t"))
    again = repo.save(
        Article(source_id="s", link="https://Example.com/a?utm_source=x#frag", title="t")
    )
    assert again is False
    assert len(repo.all()) == 1


@pytest.mark.unit
@pytest.mark.req("REQ-F01-007")
def test_list_by_source(repo) -> None:
    repo.save(Article(source_id="s1", link="https://a.example/1", title="t"))
    repo.save(Article(source_id="s1", link="https://a.example/2", title="t"))
    repo.save(Article(source_id="s2", link="https://b.example/1", title="t"))
    assert len(repo.list_by_source("s1")) == 2
    assert len(repo.list_by_source("s2")) == 1
    assert repo.list_by_source("s3") == []


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_get_by_canonical_round_trip(repo) -> None:
    a = Article(source_id="s", link="https://example.com/a?id=42", title="hello")
    repo.save(a)
    fetched = repo.get_by_canonical("https://EXAMPLE.com/a?id=42&utm_source=x#frag")
    assert fetched is not None
    assert fetched.title == "hello"
