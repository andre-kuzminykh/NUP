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


def _yt_handle(source_id: str, channel_url: str) -> Source:
    """YouTube-канал по @handle / /c/ URL — channel_id резолвится автоматически
    на первом fetch (см. infra/sources/youtube.py)."""
    return Source(id=source_id, kind=SourceKind.YOUTUBE_CHANNEL, url=channel_url)


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
        # NB: forbes-ai / forbes-leadership / cnbc.com/leadership / bbc.com/news/topics
        # — RSS-эндпоинтов нет (404 или не существует). Для них нужен HTML-адаптер
        # с CSS-селектором (см. план в docs/01-features/F01-source-ingestion.md).

        # ─── AI labs / vendor blogs ────────────────────────────────────────
        _rss("openai-blog",          "https://openai.com/blog/rss.xml"),
        _rss("googleblog-ai",        "https://blog.google/technology/ai/rss/"),
        _rss("deepmind-blog",        "https://deepmind.google/blog/rss.xml"),
        _rss("huggingface-blog",     "https://huggingface.co/blog/feed.xml"),
        _rss("nvidia-blog",          "https://blogs.nvidia.com/feed/"),
        # NB: metaai-blog (ai.meta.com/blog/rss/) → 404 на 2026-05, дропнут.
        # arxiv-cs-* / preprints — отключены: сотни новых препринтов в день
        # затопят канал. Включу обратно отдельно, с фильтром по ключевым словам.

        # ─── Robotics ──────────────────────────────────────────────────────
        _rss("mit-robotics",         "https://news.mit.edu/topic/mitrobotics-rss.xml"),
        _rss("techcrunch-robotics",  "https://techcrunch.com/category/robotics/feed/"),
        _rss("roadtovr",             "https://www.roadtovr.com/feed/"),
        _rss("robotreport",          "https://www.therobotreport.com/feed/"),
        _rss("roboticsautomation",   "https://roboticsandautomationnews.com/feed/"),
        _rss("ieee-spectrum",        "https://spectrum.ieee.org/feeds/feed.rss"),
        # NB: xrtoday (www.xrtoday.com/feed/) редиректит на маркетинг-страницу
        # uctoday.com — фид сломан, дропнут.

        # ─── Metaverse / XR ───────────────────────────────────────────────
        _rss("techcrunch-metaverse", "https://techcrunch.com/tag/metaverse/feed/"),
        # NB: xrtoday — публичный RSS не работает (200 OK, но 0 entries),
        # нужен HTML-адаптер.

        # ─── Business / Leadership ───────────────────────────────────────
        _rss("hrdive-news",          "https://www.hrdive.com/feeds/news/"),
        # NB: forbes-leadership / cnbc.com/leadership — без RSS, ждут HTML-адаптер.

        # ─── Product / Discovery ─────────────────────────────────────────
        # PRODUCT_HUNT-адаптер берёт пост с dailyRank=1 со страницы
        # /leaderboard/daily/yesterday — это «вчерашний продукт дня».
        # RSS на /feed отдаёт перемешанные «launching today» секции и
        # не годится; см. infra/sources/producthunt.py.
        Source(
            id="producthunt-yesterday",
            kind=SourceKind.PRODUCT_HUNT,
            url="https://www.producthunt.com/leaderboard/daily/yesterday",
        ),

        # NB: psychologytoday (US + intl) → 404, дропнуты. Их сайт сейчас отдаёт
        # RSS только через /feed?type=rss API, требует исследования.

        # ─── YouTube-каналы ───────────────────────────────────────────────
        # `_yt_handle` принимает @handle URL; channel_id резолвится автоматом
        # на первом fetch (см. infra/sources/youtube.py). Для скорости можно
        # дать сразу feed URL через _yt("id", "UC...").
        _yt_handle("nateherk-youtube",      "https://www.youtube.com/@nateherk"),
        _yt_handle("david-ondrej",          "https://www.youtube.com/@DavidOndrej"),
        _yt_handle("andrej-karpathy",       "https://www.youtube.com/@AndrejKarpathy"),
        _yt_handle("ai-jason-z",            "https://www.youtube.com/@AIJasonZ"),
        _yt_handle("matthew-berman",        "https://www.youtube.com/@matthew_berman"),
        _yt_handle("ai-engineer",           "https://www.youtube.com/@aiDotEngineer"),
        _yt_handle("dave-shap",             "https://www.youtube.com/@DaveShap"),
        _yt_handle("two-minute-papers",     "https://www.youtube.com/@TwoMinutePapers"),
    ]
