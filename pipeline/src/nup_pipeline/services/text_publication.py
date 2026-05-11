"""F003 — TextPublisher.

Bridges rate limiting (BR001), retry policy (BR002, inside TelegramClient),
and Publication persistence (REQ-F03-003).

Tested by tests/unit/test_text_publisher.py.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

from nup_pipeline.domain.publication import (
    Publication,
    PublicationKind,
    PublicationStatus,
)
from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter
from nup_pipeline.infra.telegram import TelegramError


class _TelegramPort(Protocol):
    def send_message(self, chat_id: str, text: str, **kw) -> int: ...


class _PublicationRepo(Protocol):
    def save(self, pub: Publication) -> None: ...


class TextPublisher:
    def __init__(
        self,
        client: _TelegramPort,
        rate_limiter: InMemoryRateLimiter,
        repo: _PublicationRepo,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._rl = rate_limiter
        self._repo = repo
        self._sleep = sleep
        self._clock = clock

    def publish(self, chat_id: str, text: str) -> Publication:
        wait_sec = self._rl.seconds_to_wait(chat_id)
        if wait_sec > 0:
            self._sleep(wait_sec)

        pub = Publication(chat_id=chat_id, kind=PublicationKind.TEXT)
        try:
            message_id = self._client.send_message(chat_id, text)
        except TelegramError as e:
            pub.status = PublicationStatus.FAILED
            pub.error = str(e)
            self._repo.save(pub)
            raise

        # Success — record send time so the next post is properly spaced.
        self._rl.mark_sent(chat_id)
        pub.status = PublicationStatus.SENT
        pub.message_id = message_id
        self._repo.save(pub)
        return pub
