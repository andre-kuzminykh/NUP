"""Text formatters for the channel.

- `single_lang_post(...)` — one language per post (used by F003 channel
  publishing: RU and EN go as two separate messages).
- `bilingual_caption(...)` — RU + EN packed into one caption (used by F011
  operator preview, where one Reels = one preview message).

Tested by tests/unit/test_single_lang_post.py and test_bilingual_caption.py.
"""
from __future__ import annotations

# Telegram caption limit (sendVideo). sendMessage has 4096.
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

_SOURCE_LABEL = {
    "ru": "📰 Полная новость",
    "en": "📰 Full story",
}


def _fit(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget <= 1:
        return text[:budget]
    return text[: budget - 1].rstrip() + "…"


def single_lang_post(
    *,
    title: str,
    content: str,
    link: str | None = None,
    lang: str = "ru",
) -> str:
    """One-language post for the channel: bold headline, body, hyperlinked source.

    Layout (Markdown for Telegram sendMessage):
        *{title}*

        {content}

        [📰 Полная новость](link)        # lang="ru"
        [📰 Full story](link)            # lang="en"

    Capped at 4096 chars (Telegram sendMessage limit).
    """
    if lang not in _SOURCE_LABEL:
        raise ValueError(f"unknown lang {lang!r}, expected one of {list(_SOURCE_LABEL)}")
    head = f"*{title.strip()}*"
    body = content.strip()
    link_block = f"[{_SOURCE_LABEL[lang]}]({link})" if link else ""
    parts = [p for p in (head, body, link_block) if p]
    out = "\n\n".join(parts)
    if len(out) > MESSAGE_LIMIT:
        out = out[: MESSAGE_LIMIT - 1].rstrip() + "…"
    return out


def bilingual_caption(
    *,
    title_ru: str,
    content_ru: str,
    title_en: str,
    content_en: str,
    link: str | None = None,
) -> str:
    head_ru = f"*{title_ru.strip()}*"
    head_en = f"*{title_en.strip()}*"
    link_block = link.strip() if link else ""

    # Fixed-overhead chars: 4 line breaks between the 4-5 blocks.
    fixed = head_ru + "\n\n" + head_en + ("\n\n" + link_block if link_block else "")
    fixed_with_seps = fixed + "\n\n" * 2  # two body blocks add two more \n\n
    overhead = len(fixed_with_seps)
    body_budget = max(0, CAPTION_LIMIT - overhead)
    per_body = body_budget // 2

    parts = [head_ru, _fit(content_ru.strip(), per_body), head_en, _fit(content_en.strip(), per_body)]
    if link_block:
        parts.append(link_block)
    out = "\n\n".join(p for p in parts if p)
    # Belt-and-braces: still cap at CAPTION_LIMIT in case of rounding.
    if len(out) > CAPTION_LIMIT:
        out = out[: CAPTION_LIMIT - 1].rstrip() + "…"
    return out
