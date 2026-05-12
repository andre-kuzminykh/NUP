"""F007 (lite) — извлечение визуальных ключевых слов для stock-search.

Stock-сервисы (Pexels, Pixabay) не понимают имён собственных типа
"Subnautica 2 Devs Don't" — поиск выдаёт случайные клипы. Этот сервис
просит LLM сгенерировать 3-5 английских визуальных ключевых слов на
основе текста новости — короткие, конкретные, generic.

Tested by tests/unit/test_visual_keywords.py.
"""
from __future__ import annotations

from typing import Protocol


class TextLlm(Protocol):
    def complete_text(self, prompt: str) -> str: ...


_PROMPT = """\
You are choosing search terms for stock-video sites like Pexels and Pixabay.

Given the article below, output 3-5 short ENGLISH visual keywords.
Rules:
- Keywords must describe VISUAL content (objects, places, actions, moods).
- AVOID proper nouns (brand/product/person names) — stock sites don't have them.
- 1-3 words per keyword, lowercase.
- One keyword per line, no numbering, no other text.

EXAMPLES (input → output):
Article about Subnautica 2 game launch:
underwater ocean
video game
deep sea diving
sci-fi exploration
gaming setup

Article about Google AI hacking:
server room
cybersecurity
hacker code
data center
glowing circuits

NOW THE ACTUAL ARTICLE:
Title: {{title}}
Body: {{body}}

OUTPUT (one keyword per line):
"""


class VisualKeywords:
    def __init__(self, llm: TextLlm) -> None:
        self._llm = llm

    def keywords_for(self, title_en: str, content_en: str) -> list[str]:
        prompt = (
            _PROMPT
            .replace("{{title}}", (title_en or "").strip()[:300])
            .replace("{{body}}", (content_en or "").strip()[:1500])
        )
        try:
            raw = self._llm.complete_text(prompt) or ""
        except Exception:
            return []
        out: list[str] = []
        for line in raw.splitlines():
            kw = line.strip().strip("-•*").strip()
            # Skip numbered lines like "1. ..."
            if kw and not kw[0].isdigit():
                out.append(kw)
            if len(out) >= 5:
                break
        return out
