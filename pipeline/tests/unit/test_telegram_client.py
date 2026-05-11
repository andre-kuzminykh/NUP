"""F003 — TelegramClient retry policy.

Traces: REQ-F03-002 / BR002 (3 retries on 5xx with backoff 1s/4s/16s).

We don't make real HTTP calls. The client is given an injected `transport`
(callable taking the request payload and returning a fake httpx.Response).
This keeps tests sub-second and deterministic.
"""
from __future__ import annotations

from typing import Callable

import httpx
import pytest

from nup_pipeline.infra.telegram import (
    TelegramClient,
    TelegramError,
    TelegramTransientError,
)


def _resp(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code=status, json=body)


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
def test_success_on_first_try_no_sleep() -> None:
    calls: list[dict] = []

    def transport(method: str, params: dict) -> httpx.Response:
        calls.append({"method": method, "params": params})
        return _resp(200, {"ok": True, "result": {"message_id": 42}})

    slept: list[float] = []
    client = TelegramClient(
        token="t",
        transport=transport,
        sleep=lambda s: slept.append(s),
    )
    msg_id = client.send_message("@d_media_ai", "hi")
    assert msg_id == 42
    assert len(calls) == 1
    assert slept == []


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
def test_retries_on_5xx_with_backoff_1_4_16() -> None:
    seq = iter([
        _resp(502, {"ok": False, "description": "bad gateway"}),
        _resp(503, {"ok": False, "description": "unavailable"}),
        _resp(200, {"ok": True, "result": {"message_id": 7}}),
    ])

    def transport(method: str, params: dict) -> httpx.Response:
        return next(seq)

    slept: list[float] = []
    client = TelegramClient(token="t", transport=transport, sleep=slept.append)
    msg_id = client.send_message("@x", "hi")
    assert msg_id == 7
    assert slept == [1.0, 4.0]   # two waits between three attempts


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
def test_gives_up_after_three_retries() -> None:
    def transport(method, params) -> httpx.Response:
        return _resp(500, {"ok": False, "description": "boom"})

    slept: list[float] = []
    client = TelegramClient(token="t", transport=transport, sleep=slept.append)
    with pytest.raises(TelegramTransientError):
        client.send_message("@x", "hi")
    # 4 total attempts (1 + 3 retries) → 3 sleeps with 1s, 4s, 16s
    assert slept == [1.0, 4.0, 16.0]


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
def test_no_retry_on_4xx() -> None:
    """4xx is a client error (bad markdown, banned, etc.) — fail fast."""
    calls = 0

    def transport(method, params) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _resp(400, {"ok": False, "description": "Bad Request: parse error"})

    slept: list[float] = []
    client = TelegramClient(token="t", transport=transport, sleep=slept.append)
    with pytest.raises(TelegramError) as exc:
        client.send_message("@x", "hi")
    assert "parse error" in str(exc.value)
    assert calls == 1
    assert slept == []


@pytest.mark.unit
@pytest.mark.req("REQ-F03-002")
def test_request_payload_has_text_and_markdown() -> None:
    captured: dict = {}

    def transport(method, params) -> httpx.Response:
        captured["method"] = method
        captured["params"] = params
        return _resp(200, {"ok": True, "result": {"message_id": 1}})

    client = TelegramClient(token="t", transport=transport, sleep=lambda _: None)
    client.send_message("@d_media_ai", "hello *world*", disable_preview=True)
    assert captured["method"] == "sendMessage"
    assert captured["params"]["chat_id"] == "@d_media_ai"
    assert captured["params"]["text"] == "hello *world*"
    assert captured["params"]["parse_mode"] == "Markdown"
    assert captured["params"]["disable_web_page_preview"] is True
