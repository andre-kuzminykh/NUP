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
def test_full_flow_publishes_two_messages_per_article_ru_first() -> None:
    """Each article → 2 messages: RU first, then EN. Same channel."""
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
    stats = n2c.run_once(sources)

    assert len(article_repo.all()) == 2
    # 2 articles × 2 languages = 4 messages.
    assert len(tg.sent) == 4
    assert all(m["chat_id"] == "@d_media_ai" for m in tg.sent)

    ru_msgs = [m for m in tg.sent if "Полная новость" in m["text"]]
    en_msgs = [m for m in tg.sent if "Full story" in m["text"]]
    assert len(ru_msgs) == 2
    assert len(en_msgs) == 2

    # First message is RU.
    assert "Полная новость" in tg.sent[0]["text"]
    # Second is EN of the same article.
    assert "Full story" in tg.sent[1]["text"]

    assert all(p.status is PublicationStatus.SENT for p in pub_repo.rows)
    assert stats == {"fetched": 2, "new": 2, "published": 4, "failed": 0, "silent_seeded": 0}


@pytest.mark.unit
def test_silent_first_seed_does_not_publish_backlog() -> None:
    """When silent_first_seed=True and DB has no rows for the source,
    the first ingest seeds the DB silently without any Telegram publish."""
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
        article_repo=article_repo,
        silent_first_seed=True,
    )
    sources = [Source(id="guardian", kind=SourceKind.RSS, url="https://x/feed")]
    stats = n2c.run_once(sources)
    assert len(article_repo.all()) == 2     # articles are saved
    assert tg.sent == []                      # but NOT published to Telegram
    assert stats["silent_seeded"] == 2
    assert stats["published"] == 0


@pytest.mark.unit
def test_silent_seed_yields_to_normal_publish_on_second_tick() -> None:
    """First tick: silent seed (no publish). Second tick: same articles
    are already in DB so ingest returns []. To exercise the publish path
    we manually pre-load one article into the repo (simulating prior seed),
    then run with silent_first_seed=True — since repo is non-empty for this
    source, we should publish."""
    article_repo = InMemoryArticleRepo()
    # Pre-load: a placeholder article (not from the RSS feed) — simulates
    # the state after a previous silent seed.
    from nup_pipeline.domain.article import Article
    article_repo.save(Article(
        source_id="guardian",
        link="https://example.com/old-already-seen",
        title="old",
        raw_content="",
    ))

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
        article_repo=article_repo,
        silent_first_seed=True,
    )
    sources = [Source(id="guardian", kind=SourceKind.RSS, url="https://x/feed")]
    stats = n2c.run_once(sources)
    # Source already had rows → 2 new articles publish RU+EN normally.
    assert stats["silent_seeded"] == 0
    assert stats["published"] == 4


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
    n2c.run_once(sources)
    assert len(article_repo.all()) == 2
    # First tick: 4 messages (2 articles × 2 langs). Second tick: 0 (all dups).
    assert len(tg.sent) == 4
