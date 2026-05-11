"""Seed-список источников для F001 ingestion.

Совпадает с RSS-фидами из исходного n8n-конвейера (Guardian, Wired,
Decoder, MIT Tech Review и т.д.). При появлении админ-UI этот список
переезжает в БД (таблица `sources`); пока — конфиг в коде, легко править.
"""
from __future__ import annotations

from nup_pipeline.domain.source import Source, SourceKind


def default_sources() -> list[Source]:
    return [
        Source(id="guardian-ai", kind=SourceKind.RSS,
               url="https://www.theguardian.com/technology/artificialintelligenceai/rss"),
        Source(id="wired-ai", kind=SourceKind.RSS,
               url="https://www.wired.com/feed/tag/ai/latest/rss"),
        Source(id="mit-technologyreview", kind=SourceKind.RSS,
               url="https://www.technologyreview.com/feed/"),
        Source(id="the-decoder", kind=SourceKind.RSS,
               url="https://the-decoder.com/feed/"),
        Source(id="mit-robotics", kind=SourceKind.RSS,
               url="https://news.mit.edu/topic/mitrobotics-rss.xml"),
        # HTML / YouTube / LinkedIn / X / Telegram sources are spec'd in
        # docs/01-features/F01-source-ingestion.md and arrive next iter.
    ]
