"""Bilingual caption / message formatter (F011, F009).

Layout:
    *{title_ru}*

    {content_ru}

    *{title_en}*

    {content_en}

    {link?}

Hard-truncated to 1024 chars (Telegram caption limit). Truncation strategy:
keep RU and EN headlines intact, distribute the body budget equally.

Tested by tests/unit/test_bilingual_caption.py (REQ-F011-003).
"""
from __future__ import annotations

# Telegram caption limit (sendVideo). sendMessage has 4096, but a caption is
# the common case for F011/F012 — pick the stricter one to be safe everywhere.
CAPTION_LIMIT = 1024


def _fit(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget <= 1:
        return text[:budget]
    return text[: budget - 1].rstrip() + "…"


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
