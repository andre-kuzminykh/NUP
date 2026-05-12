"""ElevenLabs TTS — production-grade голос для Reels.

POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
   Header: xi-api-key: <key>
   Body:   {"text", "model_id", "voice_settings"}
   Resp:   audio/mpeg bytes

Тонкая обёртка над httpx; ключи и voice_id берутся из env по умолчанию.

Tested by tests/unit/test_elevenlabs_tts.py.
"""
from __future__ import annotations

import os
from typing import Callable

import httpx

# RU-голос оператора (переопределяется через ELEVENLABS_VOICE_ID).
# В исходном n8n-конвейере для EN использовался "WRqFZoFeI1OgfQp8RY7i".
DEFAULT_VOICE_ID = "7xxG1HweS4PIsATG1xua"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsTTS:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        voice_id: str | None = None,
        model_id: str | None = None,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        timeout: float = 60.0,
        transport: Callable[[str, dict, dict], httpx.Response] | None = None,
    ) -> None:
        self._key = api_key or os.environ["ELEVENLABS_API_KEY"]
        self._voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        self._model_id = model_id or os.environ.get("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._timeout = timeout
        # transport(url, headers, body) → response. Прокидывается в тестах.
        self._transport = transport

    def synthesize(self, text: str, *, voice_id: str | None = None) -> bytes:
        vid = voice_id or self._voice_id
        url = f"{API_BASE}/text-to-speech/{vid}"
        headers = {
            "xi-api-key": self._key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        body = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
            },
        }
        if self._transport is not None:
            resp = self._transport(url, headers, body)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise ElevenLabsError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.content
