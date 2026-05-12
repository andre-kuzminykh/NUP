"""F006 — ElevenLabs TTS transport contract."""
from __future__ import annotations

import httpx
import pytest

from nup_pipeline.infra.elevenlabs_tts import (
    DEFAULT_MODEL_ID,
    DEFAULT_VOICE_ID,
    ElevenLabsError,
    ElevenLabsTTS,
)


@pytest.mark.unit
def test_post_payload_shape_uses_voice_and_model_defaults() -> None:
    captured = {}

    def transport(url, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return httpx.Response(200, content=b"MP3DATA")

    tts = ElevenLabsTTS(api_key="k", transport=transport)
    out = tts.synthesize("Привет мир")
    assert out == b"MP3DATA"
    assert captured["url"].endswith(f"/v1/text-to-speech/{DEFAULT_VOICE_ID}")
    assert captured["headers"]["xi-api-key"] == "k"
    assert captured["body"]["text"] == "Привет мир"
    assert captured["body"]["model_id"] == DEFAULT_MODEL_ID
    assert captured["body"]["voice_settings"]["stability"] == 0.5


@pytest.mark.unit
def test_voice_override_changes_url() -> None:
    captured = {}

    def transport(url, headers, body):
        captured["url"] = url
        return httpx.Response(200, content=b"x")

    ElevenLabsTTS(api_key="k", transport=transport).synthesize("hi", voice_id="OVERRIDE123")
    assert captured["url"].endswith("/text-to-speech/OVERRIDE123")


@pytest.mark.unit
def test_4xx_raises_elevenlabs_error() -> None:
    def transport(url, headers, body):
        return httpx.Response(401, text='{"detail":"invalid api key"}')

    tts = ElevenLabsTTS(api_key="bad", transport=transport)
    with pytest.raises(ElevenLabsError) as e:
        tts.synthesize("hi")
    assert "401" in str(e.value)
