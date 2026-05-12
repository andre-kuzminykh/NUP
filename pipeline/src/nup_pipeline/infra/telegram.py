"""Telegram Bot API client (F003 / F009 infra port).

Retry policy: 3 retries on 5xx with backoff 1s / 4s / 16s. 4xx fails fast.

Transport indirection: the constructor accepts a callable `transport(method, params)`
returning `httpx.Response`. Tests inject a fake; production wires httpx directly.

Tested by tests/unit/test_telegram_client.py.
"""
from __future__ import annotations

import time
from typing import Callable

import httpx

API_BASE = "https://api.telegram.org"
RETRY_BACKOFF = (1.0, 4.0, 16.0)


class TelegramError(RuntimeError):
    """Permanent Telegram failure (4xx or non-ok response)."""


class TelegramTransientError(TelegramError):
    """Transient Telegram failure (5xx, retries exhausted)."""


Transport = Callable[[str, dict], httpx.Response]


def _default_transport(token: str, timeout: float) -> Transport:
    def _send(method: str, params: dict) -> httpx.Response:
        url = f"{API_BASE}/bot{token}/{method}"
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, json=params)

    return _send


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
    ) -> None:
        self._token = token
        self._transport = transport or _default_transport(token, timeout)
        self._sleep = sleep

    # --- public API ---------------------------------------------------------

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        disable_preview: bool = False,
    ) -> int:
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": disable_preview,
        }
        result = self._call_with_retry("sendMessage", params)
        return int(result["message_id"])

    def send_video(
        self,
        chat_id: str | int,
        video_url: str,
        *,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> int:
        params: dict = {
            "chat_id": chat_id,
            "video": video_url,
            "parse_mode": "Markdown",
        }
        if caption is not None:
            params["caption"] = caption
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        result = self._call_with_retry("sendVideo", params)
        return int(result["message_id"])

    def send_video_file(
        self,
        chat_id: str | int,
        local_path: str,
        *,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> int:
        """Upload a local MP4 to Telegram (multipart/form-data).

        Bot API лимит на upload через бота — 50 MB. Подходит для коротких Reels.
        Не идёт через _call_with_retry (он принимает JSON params), у multipart
        своя обёртка. Retry/backoff здесь не делаем — для смок-теста хватит.
        """
        url = f"{API_BASE}/bot{self._token}/sendVideo"
        data: dict = {"chat_id": str(chat_id), "parse_mode": "Markdown"}
        if caption is not None:
            data["caption"] = caption
        if reply_markup is not None:
            import json as _json
            data["reply_markup"] = _json.dumps(reply_markup, ensure_ascii=False)
        with open(local_path, "rb") as f:
            files = {"video": ("reel.mp4", f, "video/mp4")}
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(url, data=data, files=files)
        if resp.status_code >= 400:
            body = self._safe_json(resp)
            raise TelegramError(body.get("description") or f"HTTP {resp.status_code}")
        payload = resp.json()
        if not payload.get("ok"):
            raise TelegramError(payload.get("description") or "ok=false")
        return int(payload["result"]["message_id"])

    # --- internals ----------------------------------------------------------

    def _call_with_retry(self, method: str, params: dict) -> dict:
        last_err: Exception | None = None
        for attempt in range(len(RETRY_BACKOFF) + 1):
            resp = self._transport(method, params)
            status = resp.status_code
            if status < 400:
                payload = resp.json()
                if not payload.get("ok"):
                    raise TelegramError(payload.get("description") or "ok=false")
                return payload["result"]
            if 400 <= status < 500:
                body = self._safe_json(resp)
                raise TelegramError(body.get("description") or f"HTTP {status}")
            # 5xx → transient: sleep + retry, unless this was the last attempt.
            body = self._safe_json(resp)
            last_err = TelegramTransientError(body.get("description") or f"HTTP {status}")
            if attempt < len(RETRY_BACKOFF):
                self._sleep(RETRY_BACKOFF[attempt])
        assert last_err is not None
        raise last_err

    @staticmethod
    def _safe_json(resp: httpx.Response) -> dict:
        try:
            return resp.json()
        except Exception:
            return {"description": resp.text[:200]}
