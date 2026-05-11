"""F009 / F012 — VideoPublisher.

Аналог TextPublisher для видео в канал. Использует тот же TelegramClient
(с retry/backoff). Идемпотентность по конкретной задаче решается на уровне
F012 ReviewDecider (через ReviewSession.publication_message_id), здесь сервис
just-do-it.

Tested transitively via tests/unit/test_review_decision.py with a fake
implementation; full unit coverage добавляется по мере роста функционала.
"""
from __future__ import annotations

from typing import Protocol

from nup_pipeline.domain.publication import (
    Publication,
    PublicationKind,
    PublicationStatus,
)
from nup_pipeline.infra.telegram import TelegramError


class _TelegramVideoPort(Protocol):
    def send_video(self, chat_id, video_url, *, caption=None, reply_markup=None) -> int: ...


class _PublicationRepo(Protocol):
    def save(self, p: Publication) -> None: ...


class VideoPublisher:
    def __init__(
        self,
        client: _TelegramVideoPort,
        repo: _PublicationRepo,
    ) -> None:
        self._client = client
        self._repo = repo

    def publish(self, chat_id, video_uri: str, caption: str | None = None) -> int:
        pub = Publication(chat_id=str(chat_id), kind=PublicationKind.VIDEO)
        try:
            message_id = self._client.send_video(chat_id, video_uri, caption=caption)
        except TelegramError as e:
            pub.status = PublicationStatus.FAILED
            pub.error = str(e)
            self._repo.save(pub)
            raise
        pub.status = PublicationStatus.SENT
        pub.message_id = message_id
        self._repo.save(pub)
        return message_id
