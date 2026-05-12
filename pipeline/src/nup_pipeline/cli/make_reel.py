"""CLI: собрать MULTI-сегментный Reels на русском из последней статьи в БД.

Поток:
  1. Достать самую свежую Article из Postgres (опционально --source).
  2. BilingualSummarizer → title_ru, content_ru.
  3. content_ru рубится на ПРЕДЛОЖЕНИЯ — каждое предложение = отдельный
     сегмент ролика. Количество сегментов — динамическое.
  4. На каждое предложение:
       - ElevenLabs TTS → MP3
       - ffprobe → длительность сегмента
  5. ОДИН Pexels-search по title_en (или title_ru), берёт N≥len(segments)
     кандидатов; распределяет по сегментам (round-robin). Pixabay-fallback.
  6. F008 FfmpegBuilder склеивает мульти-сегментный 1080×1920 MP4:
       - каждый сегмент = scale+crop стокового клипа + drawtext-субтитры
         (по 3 слова в кадр, длинные чанки авто-переносятся на 2 строки).
       - заголовка нет, только субтитры.
       - концат всех сегментов в один файл.
  7. TelegramClient.send_video_file отправляет файл оператору в личку
     (chat_id = OPERATOR_CHAT_ID из env). --to-channel шлёт в канал.

Запуск:
    docker compose run --rm news-worker python -m nup_pipeline.cli.make_reel
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

from nup_pipeline.cli.news_loop import OpenAIJsonLlm
from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.elevenlabs_tts import ElevenLabsTTS
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.ffprobe import probe_duration_sec
from nup_pipeline.infra.pexels import PexelsSearch
from nup_pipeline.infra.pixabay import PixabaySearch
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.ffmpeg_builder import build as build_ffmpeg
from nup_pipeline.services.summarize import BilingualSummarizer
from nup_pipeline.services.visual_keywords import VisualKeywords
from nup_pipeline.services.voiceover_scripter import VoiceoverScripter

log = logging.getLogger("make_reel")

# Делим по [.!?] + последующий пробел. Простое правило, без сокращений.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT.split(cleaned)
    return [p.strip() for p in parts if p.strip()]


def _download(url: str, dest: str) -> None:
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


def _get_candidates(query: str, need: int) -> list[dict]:
    """Сначала Pexels, добиваем Pixabay'ем, если всё ещё мало — повтор по кругу."""
    out: list[dict] = []
    if os.environ.get("PEXELS_API_KEY"):
        try:
            out += PexelsSearch().search_videos(query, per_page=max(need, 5))
        except Exception as e:
            log.warning(f"pexels: {e}")
    if len(out) < need and os.environ.get("PIXABAY_API_KEY"):
        try:
            out += PixabaySearch().search_videos(query, per_page=max(need, 5))
        except Exception as e:
            log.warning(f"pixabay: {e}")
    if not out:
        return []
    while len(out) < need:
        out.append(out[len(out) % max(1, len(out))])
    return out[:need]


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Build one multi-segment Reels (RU).")
    p.add_argument("--source", default=None,
                   help="Use latest article from this source id. Default: latest overall.")
    p.add_argument("--to-channel", action="store_true",
                   help="Send to @d_media_ai channel (default: send to OPERATOR_CHAT_ID DM).")
    p.add_argument("--no-publish", action="store_true",
                   help="Render mp4 but don't upload to Telegram (save under REELS_OUT_DIR).")
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

    # 2. Bilingual summary (для заголовка, подписи и keyword-search)
    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    bundle = BilingualSummarizer(llm=llm).summarize(article)
    print(f"RU title:   {bundle.title_ru}")

    # 2b. Voiceover-script со структурой Hook→Суть→Почему→Контекст→Вывод.
    # Озвучка отличается от summary — это полноценный сценарий для Shorts.
    print("generating voiceover script (hook→…→outro)…")
    voice_text = VoiceoverScripter(llm=llm).script(bundle.content_ru)
    print(f"voice ({len(voice_text)} chars): {voice_text[:140]}…")

    # 3. Split voice_text into sentences (= segments)
    sentences = split_sentences(voice_text)
    n = len(sentences)
    if n == 0:
        print("empty voiceover; abort")
        return 1
    print(f"{n} sentences → {n} segments")

    # 4. TTS per sentence
    tmpdir = tempfile.mkdtemp(prefix="reel_")
    tts = ElevenLabsTTS()
    audio_paths: list[str] = []
    durations: list[float] = []
    print("synthesizing TTS…")
    for i, sentence in enumerate(sentences):
        audio = tts.synthesize(sentence)
        path = f"{tmpdir}/voice_{i:02d}.mp3"
        with open(path, "wb") as f:
            f.write(audio)
        dur = probe_duration_sec(path)
        audio_paths.append(path)
        durations.append(dur)
        print(f"  seg{i}: {dur:.1f}s  {sentence[:70]}…")
    total_dur = sum(durations)
    print(f"total duration: {total_dur:.1f} sec")

    # 5. Stock clips — keywords подбирает отдельный LLM-вызов на основе
    # title_en + content_en (без proper nouns, чтобы Pexels попадал в тему).
    print("extracting visual keywords for stock search…")
    kws = VisualKeywords(llm=llm).keywords_for(bundle.title_en, bundle.content_en)
    if not kws:
        kws = [bundle.title_en or article.title or "technology"]
    print(f"keywords: {kws}")

    # Для разнообразия фоны разных сегментов ищем по РАЗНЫМ keywords.
    clips: list[dict] = []
    for i in range(n):
        kw = kws[i % len(kws)]
        try:
            seg_clips = (
                PexelsSearch().search_videos(kw, per_page=3)
                if os.environ.get("PEXELS_API_KEY") else []
            )
        except Exception as e:
            log.warning(f"pexels {kw!r}: {e}")
            seg_clips = []
        if not seg_clips and os.environ.get("PIXABAY_API_KEY"):
            try:
                seg_clips = PixabaySearch().search_videos(kw, per_page=3)
            except Exception as e:
                log.warning(f"pixabay {kw!r}: {e}")
        if seg_clips:
            clips.append(seg_clips[0])
            print(f"  seg{i} ({kw!r}): {seg_clips[0]['video_url'][:80]}…")
        else:
            print(f"  seg{i} ({kw!r}): no clip")
    # Если для каких-то сегментов клипов не нашли — забиваем дублями.
    if len(clips) < n and clips:
        while len(clips) < n:
            clips.append(clips[len(clips) % len(clips)])
    if not clips:
        print("no stock clips; configure PEXELS_API_KEY / PIXABAY_API_KEY")
        return 1
    video_paths: list[str] = []
    for i in range(n):
        url = clips[i]["video_url"]
        local = f"{tmpdir}/bg_{i:02d}{Path(url).suffix.split('?')[0] or '.mp4'}"
        print(f"  bg{i}: {url[:80]}…")
        _download(url, local)
        video_paths.append(local)

    # 6. Build Segment[] and render via F008 builder
    segments = [
        Segment(
            audio_uri=audio_paths[i],
            video_uri=video_paths[i],
            audio_duration_sec=durations[i],
            subtitle_text=sentences[i],
        )
        for i in range(n)
    ]
    out_path = f"{tmpdir}/reel.mp4"
    argv = build_ffmpeg(segments, music_uri=None, output_path=out_path)
    print("running ffmpeg…")
    FfmpegRunner().run(argv, output_path=out_path, timeout=600)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"rendered: {out_path} ({size_mb:.1f} MB, ~{total_dur:.0f}s)")

    # Save to host-mounted dir ALWAYS, regardless of --no-publish.
    # Если TG-upload потом упадёт, файл всё равно остаётся на хосте.
    out_dir = os.environ.get("REELS_OUT_DIR", "/tmp")
    os.makedirs(out_dir, exist_ok=True)
    keep = os.path.join(out_dir, "last_reel.mp4")
    shutil.copy(out_path, keep)
    print(f"saved: {keep}")

    if args.no_publish:
        return 0

    # 7. Telegram upload
    tg = TelegramClient(token=os.environ["TELEGRAM_BOT_TOKEN"])
    caption = f"*{bundle.title_ru}*\n\n[📰 Полная новость]({article.link})"
    if len(caption) > 1024:
        caption = caption[:1020] + "…"
    if args.to_channel:
        target = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "@d_media_ai")
    else:
        op = os.environ.get("OPERATOR_CHAT_ID", "")
        if not op:
            print("OPERATOR_CHAT_ID not set; use --to-channel or set it")
            return 1
        target = int(op)
    print(f"uploading to {target}…")
    try:
        msg_id = tg.send_video_file(target, out_path, caption=caption)
        print(f"OK, message_id={msg_id}")
    except Exception as e:
        msg = str(e)
        print(f"FAILED to upload to Telegram: {msg}")
        if "bot can't initiate conversation" in msg or "Forbidden" in msg:
            print(
                "\n→ Telegram запретил боту писать тебе первым.\n"
                "  Открой https://t.me/dataist_media_bot и нажми Start (или напиши /start),\n"
                "  потом запусти make_reel ещё раз. Файл уже сохранён локально:\n"
                f"  {keep}"
            )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
