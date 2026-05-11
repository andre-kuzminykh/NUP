"""Seed-список источников для F001 ingestion.

Сгруппировано по тематикам. Все источники здесь — RSS 2.0 или Atom (Atom
автоматически поддержан тем же парсером, см. infra/sources/rss.py).

После добавления новых источников запусти
    docker compose exec news-worker python -m nup_pipeline.cli.sources_check
чтобы увидеть, какие действительно отдают данные. Если STATUS=FAIL / EMPTY —
URL надо подправить или источник вернёт RSS только под авторизованным
запросом (тогда нужен отдельный адаптер).

YouTube-каналы: формат
    https://www.youtube.com/feeds/videos.xml?channel_id=UC...
Чтобы найти channel_id — открой канал в браузере, View Source, поищи
"channelId":". Скидывай мне URL @handle, я найду ID и добавлю строку.
"""
from __future__ import annotations

from nup_pipeline.domain.source import Source, SourceKind

# Удобный шорткат — все эти источники RSS/Atom; sources_check сам определит
# формат по корневому тегу XML.
def _rss(source_id: str, url: str) -> Source:
    return Source(id=source_id, kind=SourceKind.RSS, url=url)


def _yt(source_id: str, channel_id: str) -> Source:
    return Source(
        id=source_id,
        kind=SourceKind.YOUTUBE_CHANNEL,
        url=f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
    )


def default_sources() -> list[Source]:
    return [
        # ─── AI / general tech press ───────────────────────────────────────
        _rss("guardian-ai",          "https://www.theguardian.com/technology/artificialintelligenceai/rss"),
        _rss("wired-ai",             "https://www.wired.com/feed/tag/ai/latest/rss"),
        _rss("mit-technologyreview", "https://www.technologyreview.com/feed/"),
        _rss("the-decoder",          "https://the-decoder.com/feed/"),
        _rss("techcrunch-ai",        "https://techcrunch.com/category/artificial-intelligence/feed/"),
        _rss("venturebeat-ai",       "https://venturebeat.com/category/ai/feed/"),
        _rss("marktechpost",         "https://www.marktechpost.com/feed/"),
        _rss("arstechnica-ai",       "https://arstechnica.com/ai/feed/"),
        _rss("theverge-ai",          "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        _rss("bbc-technology",       "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        _rss("futurism-ai",          "https://futurism.com/categories/ai-artificial-intelligence/feed"),

        # ─── AI labs / vendor blogs ────────────────────────────────────────
        _rss("openai-blog",          "https://openai.com/blog/rss.xml"),
        _rss("googleblog-ai",        "https://blog.google/technology/ai/rss/"),
        _rss("deepmind-blog",        "https://deepmind.google/blog/rss.xml"),
        _rss("metaai-blog",          "https://ai.meta.com/blog/rss/"),
        _rss("huggingface-blog",     "https://huggingface.co/blog/feed.xml"),
        _rss("nvidia-blog",          "https://blogs.nvidia.com/feed/"),

        # ─── Research feeds (preprints) ────────────────────────────────────
        _rss("arxiv-cs-ai",          "https://export.arxiv.org/rss/cs.AI"),
        _rss("arxiv-cs-lg",          "https://export.arxiv.org/rss/cs.LG"),
        _rss("arxiv-cs-ro",          "https://export.arxiv.org/rss/cs.RO"),

        # ─── Robotics ──────────────────────────────────────────────────────
        _rss("mit-robotics",         "https://news.mit.edu/topic/mitrobotics-rss.xml"),
        _rss("techcrunch-robotics",  "https://techcrunch.com/category/robotics/feed/"),
        _rss("roadtovr",             "https://www.roadtovr.com/feed/"),
        _rss("robotreport",          "https://www.therobotreport.com/feed/"),
        _rss("xrtoday",              "https://www.xrtoday.com/feed/"),
        _rss("roboticsautomation",   "https://roboticsandautomationnews.com/feed/"),
        _rss("ieee-spectrum",        "https://spectrum.ieee.org/feeds/feed.rss"),

        # ─── Metaverse / XR ───────────────────────────────────────────────
        _rss("techcrunch-metaverse", "https://techcrunch.com/tag/metaverse/feed/"),

        # ─── YouTube-каналы. Чтобы добавить — пришли @handle, я найду
        #      channel_id и подставлю сюда новую строку _yt(...).
        # _yt("lex-fridman",      "UCSHZKyawb77ixDdsGog4iWA"),  # пример
    ]
