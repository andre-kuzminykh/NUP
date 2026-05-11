"""End-to-end (units only) — F001 + F002 + F003 wired together.

For each active source: fetch → parse → dedupe → save → summarize → publish.
The publication is a bilingual (RU+EN) caption sent to the target channel.

Traces: REQ-F01-001, REQ-F02-001, REQ-F03-003, REQ-F011-003 (bilingual caption).
"""
import pytest

from nup_pipeline.domain.publication import PublicationStatus
from nup_pipeline.domain.source import Source, SourceKind
from nup_pipeline.infra.article_repo import InMemoryArticleRepo
from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter
from nup_pipeline.services.ingest import IngestService
from nup_pipeline.services.news_to_channel import NewsToChannel
from nup_pipeline.services.summarize import BilingualSummarizer
from nup_pipeline.services.text_publication import TextPublisher


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>OpenAI launches GPT-5</title>
    <link>https://example.com/gpt5</link>
    <description>OpenAI announced GPT-5, a multimodal model.</description>
  </item>
  <item>
    <title>Anthropic raises money</title>
    <link>https://example.com/anth</link>
    <description>Funding round.</description>
  </item>
</channel></rss>
"""


class FakeFetcher:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get(self, url, *, proxy=None) -> bytes:
        self.calls.append(url)
        return self.payload


class FakeLlm:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_json(self, prompt: str) -> dict:
        self.calls.append(prompt)
        # Deterministic faux-translation derived from input prompt.
        if "GPT-5" in prompt:
            return {
                "title_ru": "OpenAI выпустила GPT-5",
                "content_ru": "Анонсирована мультимодальная модель.",
                "title_en": "OpenAI launches GPT-5",
                "content_en": "A multimodal model has been announced.",
            }
        return {
            "title_ru": "Anthropic привлёк инвестиции",
            "content_ru": "Раунд финансирования закрыт.",
            "title_en": "Anthropic raises funding",
            "content_en": "A funding round was closed.",
        }


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_message(self, chat_id, text, **kw) -> int:
        self.sent.append({"chat_id": chat_id, "text": text})
        return 1000 + len(self.sent)


class InMemPubRepo:
    def __init__(self) -> None:
        self.rows = []

    def save(self, p) -> None:
        self.rows.append(p)


@pytest.mark.unit
def test_full_flow_saves_articles_and_publishes_bilingual() -> None:
    # Wiring: fetcher → ingest → summarizer → publisher
    article_repo = InMemoryArticleRepo()
    pub_repo = InMemPubRepo()
    tg = FakeTelegram()
    rate_limiter = InMemoryRateLimiter(min_interval_sec=0)  # no spacing in tests
    publisher = TextPublisher(
        client=tg, rate_limiter=rate_limiter, repo=pub_repo,
        sleep=lambda _: None, clock=lambda: 0.0,
    )
    n2c = NewsToChannel(
        ingest=IngestService(fetcher=FakeFetcher(RSS), article_repo=article_repo),
        summarizer=BilingualSummarizer(llm=FakeLlm()),
        publisher=publisher,
        channel_id="@d_media_ai",
    )

    sources = [Source(id="guardian", kind=SourceKind.RSS, url="https://x/feed")]
    stats = n2c.run_once(sources)

    # Both articles in DB.
    assert len(article_repo.all()) == 2
    # Both summaries sent to TG, bilingual.
    assert len(tg.sent) == 2
    for msg in tg.sent:
        assert msg["chat_id"] == "@d_media_ai"
        # RU and EN headlines both present in the bilingual caption.
        assert any(s in msg["text"] for s in ("OpenAI выпустила", "Anthropic привлёк"))
        assert any(s in msg["text"] for s in ("OpenAI launches", "Anthropic raises"))
    # Publications persisted.
    assert all(p.status is PublicationStatus.SENT for p in pub_repo.rows)
    assert stats == {"fetched": 2, "new": 2, "published": 2, "failed": 0}


@pytest.mark.unit
def test_rerun_does_not_republish_known_articles() -> None:
    article_repo = InMemoryArticleRepo()
    pub_repo = InMemPubRepo()
    tg = FakeTelegram()
    rate_limiter = InMemoryRateLimiter(min_interval_sec=0)
    publisher = TextPublisher(
        client=tg, rate_limiter=rate_limiter, repo=pub_repo,
        sleep=lambda _: None, clock=lambda: 0.0,
    )
    n2c = NewsToChannel(
        ingest=IngestService(fetcher=FakeFetcher(RSS), article_repo=article_repo),
        summarizer=BilingualSummarizer(llm=FakeLlm()),
        publisher=publisher,
        channel_id="@d_media_ai",
    )
    sources = [Source(id="guardian", kind=SourceKind.RSS, url="https://x/feed")]
    n2c.run_once(sources)
    n2c.run_once(sources)   # second tick
    assert len(article_repo.all()) == 2
    assert len(tg.sent) == 2                  # no second publish
