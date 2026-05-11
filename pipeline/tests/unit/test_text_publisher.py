"""F003 — TextPublisher service.

Traces: REQ-F03-001..003. Wires RateLimiter + TelegramClient + PublicationRepo.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from nup_pipeline.domain.publication import Publication, PublicationStatus
from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter
from nup_pipeline.infra.telegram import TelegramError, TelegramTransientError
from nup_pipeline.services.text_publication import TextPublisher


class FakeClock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class InMemoryPublicationRepo:
    def __init__(self) -> None:
        self.rows: list[Publication] = []

    def save(self, p: Publication) -> None:
        self.rows.append(p)


class FakeTelegram:
    def __init__(self, message_id: int = 100, raise_with: Exception | None = None) -> None:
        self.calls: list[tuple] = []
        self._next_id = message_id
        self._raise = raise_with

    def send_message(self, chat_id: str, text: str, **kw) -> int:
        self.calls.append((chat_id, text, kw))
        if self._raise:
            raise self._raise
        self._next_id += 1
        return self._next_id


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_two_consecutive_publishes_are_spaced_60s() -> None:
    clk = FakeClock()
    slept: list[float] = []
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    tg = FakeTelegram()
    repo = InMemoryPublicationRepo()

    def sleep_advancing(s: float) -> None:
        slept.append(s)
        clk.advance(s)

    pub = TextPublisher(client=tg, rate_limiter=rl, repo=repo, sleep=sleep_advancing, clock=clk)
    pub.publish("@d_media_ai", "first")
    pub.publish("@d_media_ai", "second")

    assert len(tg.calls) == 2
    assert slept == [pytest.approx(60.0)]   # exactly one wait of ~60s


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_different_chats_do_not_block_each_other() -> None:
    clk = FakeClock()
    slept: list[float] = []
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    tg = FakeTelegram()
    repo = InMemoryPublicationRepo()
    pub = TextPublisher(client=tg, rate_limiter=rl, repo=repo, sleep=slept.append, clock=clk)
    pub.publish("@a", "x")
    pub.publish("@b", "y")
    assert slept == []   # no wait


@pytest.mark.unit
@pytest.mark.req("REQ-F03-003")
def test_successful_publication_is_persisted_with_message_id() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    tg = FakeTelegram(message_id=999)
    repo = InMemoryPublicationRepo()
    pub = TextPublisher(client=tg, rate_limiter=rl, repo=repo, sleep=lambda _: None, clock=clk)
    pub.publish("@d_media_ai", "hello")
    assert len(repo.rows) == 1
    row = repo.rows[0]
    assert row.status is PublicationStatus.SENT
    assert row.message_id == 1000
    assert row.chat_id == "@d_media_ai"
    assert row.error is None
    assert isinstance(row.created_at, datetime)


@pytest.mark.unit
@pytest.mark.req("REQ-F03-003")
def test_failure_persists_failed_status_with_error() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    tg = FakeTelegram(raise_with=TelegramError("Bad Request: parse error"))
    repo = InMemoryPublicationRepo()
    pub = TextPublisher(client=tg, rate_limiter=rl, repo=repo, sleep=lambda _: None, clock=clk)
    with pytest.raises(TelegramError):
        pub.publish("@d_media_ai", "hello")
    assert len(repo.rows) == 1
    row = repo.rows[0]
    assert row.status is PublicationStatus.FAILED
    assert row.message_id is None
    assert "parse error" in (row.error or "")


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
@pytest.mark.req("REQ-F03-003")
def test_transient_error_after_retries_is_marked_failed() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    tg = FakeTelegram(raise_with=TelegramTransientError("503"))
    repo = InMemoryPublicationRepo()
    pub = TextPublisher(client=tg, rate_limiter=rl, repo=repo, sleep=lambda _: None, clock=clk)
    with pytest.raises(TelegramTransientError):
        pub.publish("@d_media_ai", "hi")
    assert repo.rows[0].status is PublicationStatus.FAILED
