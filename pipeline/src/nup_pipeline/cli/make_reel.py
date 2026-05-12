"""CLI: собрать один Reels на русском из последней статьи в БД и опубликовать.

Шаги:
  1. Достать самую свежую Article из Postgres (опционально --source).
  2. BilingualSummarizer → title_ru, content_ru (EN не используем для этого
     ролика — только текст в подписи).
  3. ElevenLabs TTS озвучивает content_ru → MP3 (voice_id из env).
     При --tts=openai используется OpenAI tts-1 как fallback.
  4. ffprobe берёт длительность MP3.
  5. Pexels (или Pixabay-fallback) ищет вертикальный клип по ключевым словам
     из title_ru. Скачивается локально, используется как фон.
     При --bg=color или ошибке поиска — однотонный фон.
  6. simple_reel_builder склеивает 1080×1920 MP4 (фон + заголовок + субтитры).
  7. TelegramClient.send_video_file загружает в @d_media_ai.

Запуск:
    docker compose run --rm news-worker python -m nup_pipeline.cli.make_reel
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

from nup_pipeline.cli.news_loop import OpenAIJsonLlm
from nup_pipeline.domain.segment import chunk_subtitle
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.elevenlabs_tts import ElevenLabsTTS
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.ffprobe import probe_duration_sec
from nup_pipeline.infra.openai_tts import OpenAITTS
from nup_pipeline.infra.pexels import PexelsSearch
from nup_pipeline.infra.pixabay import PixabaySearch
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.simple_reel_builder import build_simple_reel_ffmpeg
from nup_pipeline.services.summarize import BilingualSummarizer

log = logging.getLogger("make_reel")


def _download(url: str, dest: str) -> None:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


def _find_stock_video(query: str, tmpdir: str) -> str | None:
    """Сначала Pexels, потом Pixabay. Скачивает первый портретный клип, возвращает path."""
    sources = []
    if os.environ.get("PEXELS_API_KEY"):
        sources.append(("pexels", PexelsSearch()))
    if os.environ.get("PIXABAY_API_KEY"):
        sources.append(("pixabay", PixabaySearch()))
    if not sources:
        log.warning("no stock-video keys configured (PEXELS_API_KEY / PIXABAY_API_KEY)")
        return None
    for name, client in sources:
        try:
            hits = client.search_videos(query, per_page=3)
        except Exception as e:
            log.warning(f"{name} search failed: {e}")
            continue
        if not hits:
            log.info(f"{name}: 0 hits for {query!r}")
            continue
        chosen = hits[0]
        url = chosen.get("video_url")
        if not url:
            continue
        ext = Path(url).suffix.split("?")[0] or ".mp4"
        local = f"{tmpdir}/bg_{name}{ext}"
        log.info(f"{name}: downloading {url}")
        try:
            _download(url, local)
        except Exception as e:
            log.warning(f"{name}: download failed: {e}")
            continue
        return local
    return None


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Build one Reels (RU) and post to channel.")
    p.add_argument("--source", default=None,
                   help="Use latest article from this source id. Default: latest overall.")
    p.add_argument("--tts", default="elevenlabs", choices=["elevenlabs", "openai"],
                   help="Voice engine. Default: elevenlabs.")
    p.add_argument("--bg", default="stock", choices=["stock", "color"],
                   help="Background. 'stock' = Pexels/Pixabay clip; 'color' = solid bg.")
    p.add_argument("--bg-color", default="0x1e293b", help="Solid bg when --bg=color.")
    p.add_argument("--no-publish", action="store_true",
                   help="Render mp4 but don't upload to Telegram (print local path).")
    args = p.parse_args()

    # 1. Pick article
    repo = PostgresArticleRepo(os.environ["DATABASE_URL"])
    candidates = repo.list_by_source(args.source) if args.source else repo.all()
    if not candidates:
        msg = (f"no articles for source={args.source!r}" if args.source
               else "no articles in DB; run `tick_once --seed` first")
        print(msg)
        return 1
    article = max(candidates, key=lambda a: a.created_at)
    print(f"article: [{article.source_id}] {article.title}")
    print(f"link:    {article.link}")

    # 2. Summary (берём только RU для озвучки)
    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    bundle = BilingualSummarizer(llm=llm).summarize(article)
    print(f"RU title:   {bundle.title_ru}")
    print(f"RU content: {bundle.content_ru[:120]}…")

    # 3. TTS
    print(f"synthesizing TTS via {args.tts}…")
    if args.tts == "elevenlabs":
        audio = ElevenLabsTTS().synthesize(bundle.content_ru)
    else:
        audio = OpenAITTS().synthesize(bundle.content_ru)
    print(f"TTS: {len(audio)} bytes")

    tmpdir = tempfile.mkdtemp(prefix="reel_")
    tts_path = f"{tmpdir}/voice.mp3"
    with open(tts_path, "wb") as f:
        f.write(audio)
    duration = probe_duration_sec(tts_path)
    print(f"duration: {duration:.1f} sec")

    # 4. Stock-video (если запрошено)
    bg_video_path: str | None = None
    if args.bg == "stock":
        # Используем title_en как поисковый запрос (Pexels/Pixabay лучше понимают англ).
        query = bundle.title_en or article.title or "technology"
        # Чистим хвостовое мусорное; делаем 3-4 слова.
        query = " ".join(query.split()[:4])
        print(f"searching stock video for: {query!r}")
        bg_video_path = _find_stock_video(query, tmpdir)
        if bg_video_path:
            print(f"stock bg: {bg_video_path}")
        else:
            print("no stock video found; falling back to solid color bg")

    # 5. Build mp4
    chunks = chunk_subtitle(bundle.content_ru, n=3)
    out_path = f"{tmpdir}/reel.mp4"
    argv = build_simple_reel_ffmpeg(
        audio_path=tts_path,
        duration_sec=duration,
        title=bundle.title_ru,
        chunks=chunks,
        output_path=out_path,
        bg_color=args.bg_color,
        bg_video_path=bg_video_path,
    )
    print("running ffmpeg…")
    FfmpegRunner().run(argv, output_path=out_path, timeout=300)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"rendered: {out_path} ({size_mb:.1f} MB)")

    if args.no_publish:
        # Скопируем в /tmp/reel_<id>.mp4 для удобного scp.
        keep = "/tmp/last_reel.mp4"
        shutil.copy(out_path, keep)
        print(f"saved local copy: {keep}  (use gcloud scp to download)")
        return 0

    # 6. Upload to channel
    tg = TelegramClient(token=os.environ["TELEGRAM_BOT_TOKEN"])
    channel = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "@d_media_ai")
    caption = (
        f"*{bundle.title_ru}*\n\n"
        f"[📰 Полная новость]({article.link})"
    )
    if len(caption) > 1024:
        caption = caption[:1020] + "…"
    print(f"uploading to {channel}…")
    msg_id = tg.send_video_file(channel, out_path, caption=caption)
    print(f"OK, message_id={msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
