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
            if kw and not kw[0].isdigit():
                out.append(kw)
            if len(out) >= 5:
                break
        return out

    def keywords_per_segment(
        self, title_en: str, sentences: list[str], fallback: list[str] | None = None,
    ) -> list[str]:
        """По одному визуальному keyword'у на каждое предложение из сценария.

        Каждый сегмент Reels получает собственный, отличный от соседей
        запрос для stock-search — это убирает «одни и те же кадры подряд».
        """
        if not sentences:
            return []
        numbered = "\n".join(f"{i+1}. {s.strip()}" for i, s in enumerate(sentences))
        prompt = (
            "You're choosing search terms for stock-video sites.\n\n"
            f"Article title (for context): {title_en[:200]}\n\n"
            "For EACH numbered sentence below, output ONE short ENGLISH visual\n"
            "keyword (1-3 words, lowercase, NO proper nouns, NO numbers).\n"
            "Output the keywords in the SAME ORDER as sentences, one per line.\n"
            "Make each keyword DIFFERENT from the previous one — variety matters.\n\n"
            f"SENTENCES:\n{numbered}\n\n"
            "OUTPUT (one keyword per line, same order):"
        )
        try:
            raw = self._llm.complete_text(prompt) or ""
        except Exception:
            raw = ""
        out: list[str] = []
        for line in raw.splitlines():
            kw = line.strip().strip("-•*").strip()
            # Skip leading "1. " numbering if LLM still numbered
            if kw and kw[0].isdigit() and "." in kw[:4]:
                kw = kw.split(".", 1)[1].strip()
            if kw:
                out.append(kw)
            if len(out) >= len(sentences):
                break
        # Pad with fallback / generic if LLM was lazy.
        pool = fallback or out or ["technology"]
        while len(out) < len(sentences):
            out.append(pool[len(out) % len(pool)])
        return out[: len(sentences)]
