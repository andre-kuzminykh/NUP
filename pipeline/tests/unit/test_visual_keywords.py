"""F007 — visual keywords extraction contract."""
import pytest

from nup_pipeline.services.visual_keywords import VisualKeywords


class FakeLlm:
    def __init__(self, response: str) -> None:
        self.calls: list[str] = []
        self._response = response

    def complete_text(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._response


@pytest.mark.unit
def test_parses_one_keyword_per_line() -> None:
    llm = FakeLlm("underwater ocean\nvideo game\ndeep sea diving")
    out = VisualKeywords(llm=llm).keywords_for("Subnautica 2", "underwater game launch")
    assert out == ["underwater ocean", "video game", "deep sea diving"]


@pytest.mark.unit
def test_strips_bullets_and_dashes() -> None:
    llm = FakeLlm("- cyber security\n• server room\n* hacker code")
    out = VisualKeywords(llm=llm).keywords_for("t", "b")
    assert out == ["cyber security", "server room", "hacker code"]


@pytest.mark.unit
def test_skips_numbered_lines() -> None:
    """Если LLM ослушалась и пронумеровала — нумерованные строки пропускаем,
    чтобы не отдать в Pexels query вида '1. underwater'."""
    llm = FakeLlm("1. underwater\nocean waves\n2. another")
    out = VisualKeywords(llm=llm).keywords_for("t", "b")
    assert out == ["ocean waves"]


@pytest.mark.unit
def test_caps_at_5() -> None:
    llm = FakeLlm("\n".join(f"kw{i}" for i in range(10)))
    out = VisualKeywords(llm=llm).keywords_for("t", "b")
    assert len(out) == 5


@pytest.mark.unit
def test_llm_failure_returns_empty() -> None:
    class BrokenLlm:
        def complete_text(self, prompt):
            raise RuntimeError("boom")
    assert VisualKeywords(llm=BrokenLlm()).keywords_for("t", "b") == []


@pytest.mark.unit
def test_keywords_per_segment_one_per_sentence() -> None:
    llm = FakeLlm("call center\nheadset operator\nai voice")
    kws = VisualKeywords(llm=llm).keywords_per_segment("title", ["s1", "s2", "s3"])
    assert kws == ["call center", "headset operator", "ai voice"]


@pytest.mark.unit
def test_keywords_per_segment_strips_numbered_prefix() -> None:
    llm = FakeLlm("1. call center\n2. headset operator\n3. ai voice")
    kws = VisualKeywords(llm=llm).keywords_per_segment("title", ["s1", "s2", "s3"])
    assert kws == ["call center", "headset operator", "ai voice"]


@pytest.mark.unit
def test_keywords_per_segment_pads_with_fallback_if_lazy_llm() -> None:
    llm = FakeLlm("just one")
    kws = VisualKeywords(llm=llm).keywords_per_segment(
        "title", ["s1", "s2", "s3"], fallback=["tech", "office"]
    )
    # LLM gave 1, need 3; pad cycling through ['just one'] then fallback if needed.
    assert len(kws) == 3
    assert kws[0] == "just one"


@pytest.mark.unit
def test_keywords_per_segment_llm_failure_uses_fallback() -> None:
    class BrokenLlm:
        def complete_text(self, prompt):
            raise RuntimeError("boom")
    kws = VisualKeywords(llm=BrokenLlm()).keywords_per_segment(
        "t", ["s1", "s2"], fallback=["technology"]
    )
    assert kws == ["technology", "technology"]


@pytest.mark.unit
def test_keywords_per_segment_empty_sentences_empty_result() -> None:
    llm = FakeLlm("ignored")
    assert VisualKeywords(llm=llm).keywords_per_segment("t", []) == []
