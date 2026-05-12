"""CLI: собрать один смок-Reels из последней статьи в БД и опубликовать в канал.

Шаги:
  1. Достать самую свежую Article из Postgres (опционально --source).
  2. BilingualSummarizer → bundle (title_ru, content_ru, title_en, content_en).
  3. OpenAI TTS озвучивает content_ru → MP3.
  4. ffprobe берёт длительность MP3.
  5. simple_reel_builder собирает 1080×1920 MP4 с цветным фоном, заголовком
     сверху и субтитрами по 3 слова в кадр (синхронно с озвучкой).
  6. TelegramClient.send_video_file загружает MP4 в @d_media_ai.

Запуск:
    docker compose exec news-worker python -m nup_pipeline.cli.make_reel
    docker compose exec news-worker python -m nup_pipeline.cli.make_reel --source guardian-ai
    docker compose exec news-worker python -m nup_pipeline.cli.make_reel --voice nova --bg 0x4338ca
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile

from nup_pipeline.cli.news_loop import OpenAIJsonLlm
from nup_pipeline.domain.segment import chunk_subtitle
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.ffprobe import probe_duration_sec
from nup_pipeline.infra.openai_tts import OpenAITTS
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.simple_reel_builder import build_simple_reel_ffmpeg
from nup_pipeline.services.summarize import BilingualSummarizer

log = logging.getLogger("make_reel")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Build one smoke-test Reels and post to channel.")
    p.add_argument("--source", default=None,
                   help="Use latest article from this source id. Default: latest across all.")
    p.add_argument(
        "--voice", default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="OpenAI TTS voice.",
    )
    p.add_argument("--bg", default="0x1e293b",
                   help="Background color (ffmpeg color spec, e.g. 0x1e293b).")
    args = p.parse_args()

    # 1. Pick article
    repo = PostgresArticleRepo(os.environ["DATABASE_URL"])
    candidates = repo.list_by_source(args.source) if args.source else repo.all()
    if not candidates:
        msg = (
            f"no articles for source={args.source!r}" if args.source
            else "no articles in DB; run `tick_once --seed` first"
        )
        print(msg)
        return 1
    article = max(candidates, key=lambda a: a.created_at)
    print(f"article: [{article.source_id}] {article.title}")
    print(f"link:    {article.link}")

    # 2. Summary
    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    bundle = BilingualSummarizer(llm=llm).summarize(article)
    print(f"RU title:   {bundle.title_ru}")
    print(f"RU content: {bundle.content_ru[:120]}…")

    # 3. TTS
    print("synthesizing TTS…")
    audio = OpenAITTS(voice=args.voice).synthesize(bundle.content_ru)
    print(f"TTS: {len(audio)} bytes")

    tmpdir = tempfile.mkdtemp(prefix="reel_")
    tts_path = f"{tmpdir}/voice.mp3"
    with open(tts_path, "wb") as f:
        f.write(audio)
    duration = probe_duration_sec(tts_path)
    print(f"duration: {duration:.1f} sec")

    # 4. Build mp4
    chunks = chunk_subtitle(bundle.content_ru, n=3)
    out_path = f"{tmpdir}/reel.mp4"
    argv = build_simple_reel_ffmpeg(
        audio_path=tts_path,
        duration_sec=duration,
        title=bundle.title_ru,
        chunks=chunks,
        output_path=out_path,
        bg_color=args.bg,
    )
    print("running ffmpeg…")
    FfmpegRunner().run(argv, output_path=out_path, timeout=180)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"rendered: {out_path} ({size_mb:.1f} MB)")

    # 5. Upload to channel
    tg = TelegramClient(token=os.environ["TELEGRAM_BOT_TOKEN"])
    channel = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "@d_media_ai")
    caption = (
        f"*{bundle.title_ru}*\n"
        f"*{bundle.title_en}*\n\n"
        f"[📰 Полная новость]({article.link}) / "
        f"[📰 Full story]({article.link})"
    )
    if len(caption) > 1024:
        caption = caption[:1020] + "…"
    print(f"uploading to {channel}…")
    msg_id = tg.send_video_file(channel, out_path, caption=caption)
    print(f"OK, message_id={msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
