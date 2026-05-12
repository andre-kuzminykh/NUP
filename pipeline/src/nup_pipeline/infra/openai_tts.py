"""Минимальный OpenAI TTS-клиент.

Используется в смок-тесте Reels (cli/make_reel.py). Production-ready
ElevenLabs-клиент остаётся в плане F006 (см. spec).
"""
from __future__ import annotations

import os


class OpenAITTS:
    """Возвращает MP3-байты для произвольного текста.

    Модель по умолчанию — tts-1 (быстрая, дешёвая, поддерживает русский).
    Voice: alloy / echo / fable / onyx / nova / shimmer.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        voice: str = "alloy",
    ) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError("pip install openai required for OpenAITTS") from e
        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self._model = model or os.environ.get("OPENAI_TTS_MODEL", "tts-1")
        self._voice = voice

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        response = self._client.audio.speech.create(
            model=self._model,
            voice=voice or self._voice,
            input=text,
            response_format="mp3",
        )
        # SDK v1.x: BinaryAPIResponse. .content / .read() оба отдают bytes.
        if hasattr(response, "content"):
            data = response.content
            return data if isinstance(data, (bytes, bytearray)) else bytes(data)
        return response.read()
