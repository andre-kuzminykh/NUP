"""F011 — bilingual caption formatter.

Traces: REQ-F011-003.
"""
import pytest

from nup_pipeline.services.text_format import bilingual_caption


@pytest.mark.unit
@pytest.mark.req("REQ-F011-003")
def test_full_caption_has_ru_then_en_then_link() -> None:
    out = bilingual_caption(
        title_ru="Заголовок", content_ru="Тело по-русски.",
        title_en="Headline",  content_en="English body.",
        link="https://example.com/a",
    )
    # Order: title_ru (bold) → content_ru → blank → title_en (bold) → content_en → blank → link
    ru_pos = out.index("Заголовок")
    en_pos = out.index("Headline")
    link_pos = out.index("https://example.com/a")
    assert ru_pos < en_pos < link_pos
    assert "*Заголовок*" in out
    assert "*Headline*" in out
    assert "Тело по-русски." in out
    assert "English body." in out


@pytest.mark.unit
@pytest.mark.req("REQ-F011-003")
def test_caption_works_without_link() -> None:
    out = bilingual_caption(
        title_ru="Т", content_ru="т", title_en="T", content_en="t",
        link=None,
    )
    assert "Т" in out and "T" in out
    assert "https://" not in out


@pytest.mark.unit
@pytest.mark.req("REQ-F011-003")
def test_caption_truncates_to_telegram_caption_limit() -> None:
    # Telegram caption hard limit is 1024 chars. Helper must truncate gracefully.
    big = "x" * 3000
    out = bilingual_caption(
        title_ru="t", content_ru=big, title_en="t", content_en=big, link=None,
    )
    assert len(out) <= 1024
