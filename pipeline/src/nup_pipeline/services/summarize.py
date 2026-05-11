"""F002 — Bilingual summarizer (RU + EN in a single LLM call).

LLM port returns parsed JSON (already deserialised). Production wires it to
OpenAI with `response_format={"type": "json_object"}`. Tests inject FakeLlm.

Prompt is loaded from docs/05-prompts/article-bilingual-summary.md — single
source of truth. Two attempts: original + one retry on schema failure.

Tested by tests/unit/test_bilingual_summarizer.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from nup_pipeline.domain.article import Article
from nup_pipeline.domain.summary import SummaryBundle

# pipeline/src/nup_pipeline/services/summarize.py
#       └── parents[0] = services/
#       └── parents[1] = nup_pipeline/
#       └── parents[2] = src/
#       └── parents[3] = pipeline/
_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "05-prompts" / "article-bilingual-summary.md"
)

_REQUIRED = ("title_ru", "content_ru", "title_en", "content_en")
_RETRY_NOTE = "\n\nReturn ONLY valid JSON with all four required keys."

# Cap body sent to LLM to keep token usage bounded.
_MAX_BODY_CHARS = 8000


class SummarizerError(RuntimeError):
    """Raised when LLM fails to produce a valid bilingual summary after retry."""


class LlmJson(Protocol):
    def complete_json(self, prompt: str) -> dict: ...


def _load_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _is_valid(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(k in payload and str(payload[k]).strip() for k in _REQUIRED)


class BilingualSummarizer:
    def __init__(self, llm: LlmJson, *, template: str | None = None) -> None:
        self._llm = llm
        self._template = template or _load_template()

    def _render(self, article: Article) -> str:
        body = (article.raw_content or "")[:_MAX_BODY_CHARS]
        return (
            self._template.replace("{{title}}", article.title or "")
            .replace("{{content}}", body)
        )

    def summarize(self, article: Article) -> SummaryBundle:
        base = self._render(article)
        last_err: Exception | None = None
        for attempt in range(2):  # initial + 1 retry per REQ-F02-003
            prompt = base if attempt == 0 else base + _RETRY_NOTE
            try:
                payload = self._llm.complete_json(prompt)
            except Exception as e:
                last_err = e
                continue
            if _is_valid(payload):
                return SummaryBundle(
                    article_id=article.id,
                    link=article.link,
                    title_ru=str(payload["title_ru"]).strip(),
                    content_ru=str(payload["content_ru"]).strip(),
                    title_en=str(payload["title_en"]).strip(),
                    content_en=str(payload["content_en"]).strip(),
                )
            last_err = ValueError(f"invalid summary payload: keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)}")
        raise SummarizerError(f"summarizer gave up after retry: {last_err}")
