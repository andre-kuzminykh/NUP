"""F004 — voice-over script generator (Hook → Essence → Why → Context → Outro).

Использует уже существующий промт `docs/05-prompts/voiceover-script.md`
со структурой 5 блоков под YouTube Shorts.

Возвращает простой строковый сценарий (без JSON-обёртки), готовый для TTS.

Tested by tests/unit/test_voiceover_scripter.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs" / "05-prompts" / "voiceover-script.md"
)


class TextLlm(Protocol):
    def complete_text(self, prompt: str) -> str: ...


class VoiceoverScripter:
    def __init__(self, llm: TextLlm, *, template: str | None = None) -> None:
        self._llm = llm
        self._template = template or _PROMPT_PATH.read_text(encoding="utf-8")

    def script(self, content_ru: str) -> str:
        prompt = self._template.replace("{{content_ru}}", (content_ru or "").strip())
        out = (self._llm.complete_text(prompt) or "").strip()
        if not out:
            raise RuntimeError("voiceover llm returned empty text")
        return out
