"""CLI loop: пробегает все источники, публикует свежие новости в канал.

Использует production-обвязку:
- httpx-fetcher (через ProxyPool, если PROXY_POOL задан);
- OpenAI LLM port (если OPENAI_API_KEY задан — иначе бросает на старте);
- TelegramClient → channel_id из env;
- InMemoryArticleRepo (Postgres-репо приходит вместе с миграциями, см. TODO).

Запуск:
    python -m nup_pipeline.cli.news_loop
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

from nup_pipeline.cli.sources import default_sources
from nup_pipeline.infra.article_repo import InMemoryArticleRepo
from nup_pipeline.infra.proxies import ProxyPool
from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.ingest import IngestService
from nup_pipeline.services.news_to_channel import NewsToChannel
from nup_pipeline.services.summarize import BilingualSummarizer
from nup_pipeline.services.text_publication import TextPublisher

log = logging.getLogger("news_loop")


class HttpxFetcher:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def get(self, url: str, *, proxy: str | None = None) -> bytes:
        kwargs = {"timeout": self._timeout, "follow_redirects": True}
        if proxy:
            kwargs["proxy"] = proxy
        with httpx.Client(**kwargs) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (NUP/0.1)"})
            resp.raise_for_status()
            return resp.content


class OpenAIJsonLlm:
    """Minimal LLM port: gpt-4.1 with response_format=json_object."""

    def __init__(self, api_key: str, model: str = "gpt-4.1") -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Install `openai` to use OpenAIJsonLlm (pip install openai)"
            ) from e
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete_json(self, prompt: str) -> dict:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}


def _build_orchestrator() -> NewsToChannel:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    channel = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "@d_media_ai")
    proxies = [p.strip() for p in (os.environ.get("PROXY_POOL", "") or "").replace(",", "\n").splitlines() if p.strip()]
    proxy_pool = ProxyPool(proxies, strategy=os.environ.get("PROXY_POOL_STRATEGY", "round_robin")) if proxies else None

    fetcher = HttpxFetcher(timeout=float(os.environ.get("FETCH_TIMEOUT_SEC", "30")))
    article_repo = InMemoryArticleRepo()
    ingest = IngestService(fetcher=fetcher, article_repo=article_repo, proxy_pool=proxy_pool)

    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    summarizer = BilingualSummarizer(llm=llm)

    tg = TelegramClient(token=token)
    rate_limiter = InMemoryRateLimiter(min_interval_sec=60)

    class _PubRepo:
        def __init__(self) -> None:
            self.rows: list[Any] = []
        def save(self, p) -> None:
            self.rows.append(p)

    publisher = TextPublisher(client=tg, rate_limiter=rate_limiter, repo=_PubRepo())
    return NewsToChannel(
        ingest=ingest,
        summarizer=summarizer,
        publisher=publisher,
        channel_id=channel,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    interval = int(os.environ.get("NEWS_LOOP_INTERVAL_SEC", "1800"))  # 30 мин по умолчанию
    sources = default_sources()
    orchestrator = _build_orchestrator()
    while True:
        try:
            stats = orchestrator.run_once(sources)
            log.info("tick done", extra={"stats": stats})
        except Exception:
            log.exception("tick failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
