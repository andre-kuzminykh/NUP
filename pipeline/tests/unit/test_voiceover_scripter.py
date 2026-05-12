"""F004 — voiceover script generator contract."""
import pytest

from nup_pipeline.services.voiceover_scripter import VoiceoverScripter


class FakeLlm:
    def __init__(self, response: str) -> None:
        self.calls: list[str] = []
        self._response = response

    def complete_text(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self._response


@pytest.mark.unit
def test_substitutes_content_into_template() -> None:
    llm = FakeLlm("scripted line 1.\nscripted line 2.")
    scripter = VoiceoverScripter(llm=llm, template="content was: {{content_ru}}")
    out = scripter.script("hello world")
    assert "scripted line 1." in out
    assert llm.calls[0] == "content was: hello world"


@pytest.mark.unit
def test_default_template_loads_from_md_file() -> None:
    # No template provided → реальный файл должен подгрузиться без ошибок.
    llm = FakeLlm("ok")
    scripter = VoiceoverScripter(llm=llm)
    out = scripter.script("любой текст")
    assert out == "ok"
    assert len(llm.calls) == 1
    # В реальном промте должны быть 5 блочные ключевые слова
    assert "ХУК" in llm.calls[0] or "хук" in llm.calls[0].lower()


@pytest.mark.unit
def test_empty_response_raises() -> None:
    llm = FakeLlm("   \n\t  ")
    with pytest.raises(RuntimeError, match="empty"):
        VoiceoverScripter(llm=llm, template="x").script("y")
