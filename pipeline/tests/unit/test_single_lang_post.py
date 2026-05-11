"""F003 — per-language post formatter (RU+EN posted as two separate messages).

Traces: REQ-F03-001 / requirement to publish RU and EN as independent posts
with a hyperlinked source.
"""
from __future__ import annotations

import pytest

from nup_pipeline.services.text_format import single_lang_post


@pytest.mark.unit
def test_ru_post_has_bold_title_body_and_hyperlinked_source() -> None:
    out = single_lang_post(
        title="ИИ переписал Мольера",
        content="Учёные Сорбонны использовали Le Chat для пьесы. Премьера в Версале.",
        link="https://example.com/play",
        lang="ru",
    )
    assert out.startswith("*ИИ переписал Мольера*")
    assert "Учёные Сорбонны" in out
    assert "[📰 Полная новость](https://example.com/play)" in out
    # body separated from title by blank line, source — by another blank line.
    assert out.count("\n\n") >= 2


@pytest.mark.unit
def test_en_post_has_full_story_label() -> None:
    out = single_lang_post(
        title="AI rewrites Molière",
        content="Sorbonne researchers used Le Chat to draft the play.",
        link="https://example.com/play",
        lang="en",
    )
    assert out.startswith("*AI rewrites Molière*")
    assert "[📰 Full story](https://example.com/play)" in out


@pytest.mark.unit
def test_post_without_link_omits_source_block() -> None:
    out = single_lang_post(
        title="t", content="c", link=None, lang="ru",
    )
    assert "Полная новость" not in out
    assert "📰" not in out


@pytest.mark.unit
def test_post_is_capped_at_telegram_message_limit() -> None:
    big = "x" * 5000
    out = single_lang_post(title="t", content=big, link=None, lang="ru")
    assert len(out) <= 4096


@pytest.mark.unit
def test_unknown_lang_raises() -> None:
    with pytest.raises(ValueError):
        single_lang_post(title="t", content="c", link=None, lang="de")
