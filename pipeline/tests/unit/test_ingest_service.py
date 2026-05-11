"""F001 — IngestService orchestrates fetch → parse → dedupe → save.

Traces: REQ-F01-001, REQ-F01-006, REQ-F01-007.
"""
import pytest

from nup_pipeline.domain.source import Source, SourceKind
from nup_pipeline.infra.article_repo import InMemoryArticleRepo
from nup_pipeline.services.ingest import IngestService


RSS_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Guardian AI</title>
    <item>
      <title>One</title>
      <link>https://example.com/a?utm_source=rss</link>
      <description>aaa</description>
    </item>
    <item>
      <title>Two</title>
      <link>https://example.com/b</link>
      <description>bbb</description>
    </item>
  </channel>
</rss>
"""


class FakeFetcher:
    def __init__(self, payload: bytes, fail_with: Exception | None = None) -> None:
        self.payload = payload
        self.calls: list[str] = []
        self.fail_with = fail_with

    def get(self, url: str, *, proxy: str | None = None) -> bytes:
        self.calls.append(url)
        if self.fail_with:
            raise self.fail_with
        return self.payload


@pytest.mark.unit
@pytest.mark.req("REQ-F01-001")
@pytest.mark.req("REQ-F01-007")
def test_ingest_rss_inserts_articles_into_repo() -> None:
    fetcher = FakeFetcher(RSS_FIXTURE)
    repo = InMemoryArticleRepo()
    svc = IngestService(fetcher=fetcher, article_repo=repo)
    src = Source(id="guardian", kind=SourceKind.RSS, url="https://x.example/feed")
    new = svc.ingest_source(src)
    assert len(new) == 2
    assert {a.title for a in new} == {"One", "Two"}
    assert len(repo.all()) == 2
    assert fetcher.calls == ["https://x.example/feed"]


@pytest.mark.unit
@pytest.mark.req("REQ-F01-006")
def test_ingest_is_idempotent_dedups_by_canonical_link() -> None:
    fetcher = FakeFetcher(RSS_FIXTURE)
    repo = InMemoryArticleRepo()
    svc = IngestService(fetcher=fetcher, article_repo=repo)
    src = Source(id="guardian", kind=SourceKind.RSS, url="https://x.example/feed")
    first = svc.ingest_source(src)
    second = svc.ingest_source(src)
    assert len(first) == 2
    assert len(second) == 0   # all duplicates
    assert len(repo.all()) == 2


@pytest.mark.unit
def test_ingest_swallows_fetch_failure_and_returns_empty() -> None:
    fetcher = FakeFetcher(b"", fail_with=RuntimeError("network down"))
    repo = InMemoryArticleRepo()
    svc = IngestService(fetcher=fetcher, article_repo=repo)
    src = Source(id="guardian", kind=SourceKind.RSS, url="https://x.example/feed")
    result = svc.ingest_source(src)
    assert result == []
    assert repo.all() == []
