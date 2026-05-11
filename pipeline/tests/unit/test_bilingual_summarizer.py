"""F002 — Bilingual summarizer (RU + EN in one LLM call).

Traces: REQ-F02-001, REQ-F02-002, REQ-F02-003.
"""
import pytest

from nup_pipeline.domain.article import Article
from nup_pipeline.services.summarize import BilingualSummarizer, SummarizerError


class FakeLlm:
    def __init__(self, responses: list[dict | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def complete_json(self, prompt: str) -> dict:
        self.calls.append(prompt)
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _article() -> Article:
    return Article(
        source_id="src-1",
        link="https://example.com/a",
        title="OpenAI launches GPT-5",
        raw_content="Today OpenAI announced GPT-5, a new multimodal model.",
    )


@pytest.mark.unit
@pytest.mark.req("REQ-F02-001")
def test_returns_bundle_with_all_four_fields() -> None:
    llm = FakeLlm([{
        "title_ru": "OpenAI представила GPT-5",
        "content_ru": "Анонсирована новая мультимодальная модель.",
        "title_en": "OpenAI launches GPT-5",
        "content_en": "A new multimodal model has been announced.",
    }])
    summarizer = BilingualSummarizer(llm=llm)
    bundle = summarizer.summarize(_article())
    assert bundle.title_ru.startswith("OpenAI")
    assert bundle.content_ru
    assert bundle.title_en.startswith("OpenAI")
    assert bundle.content_en
    assert bundle.link == "https://example.com/a"
    assert len(llm.calls) == 1


@pytest.mark.unit
@pytest.mark.req("REQ-F02-003")
def test_retries_once_on_invalid_payload() -> None:
    bad_then_good = [
        {"title_ru": "x"},  # missing 3 fields → invalid
        {
            "title_ru": "x", "content_ru": "y",
            "title_en": "X", "content_en": "Y",
        },
    ]
    llm = FakeLlm(bad_then_good)
    summarizer = BilingualSummarizer(llm=llm)
    bundle = summarizer.summarize(_article())
    assert len(llm.calls) == 2
    assert bundle.title_en == "X"


@pytest.mark.unit
@pytest.mark.req("REQ-F02-003")
def test_gives_up_after_one_retry() -> None:
    llm = FakeLlm([{"title_ru": "x"}, {"title_ru": "still bad"}])
    summarizer = BilingualSummarizer(llm=llm)
    with pytest.raises(SummarizerError):
        summarizer.summarize(_article())
    assert len(llm.calls) == 2


@pytest.mark.unit
@pytest.mark.req("REQ-F02-001")
def test_prompt_contains_article_title_and_body() -> None:
    llm = FakeLlm([{
        "title_ru": "t", "content_ru": "c", "title_en": "T", "content_en": "C",
    }])
    BilingualSummarizer(llm=llm).summarize(_article())
    prompt = llm.calls[0]
    assert "OpenAI launches GPT-5" in prompt
    assert "multimodal model" in prompt
