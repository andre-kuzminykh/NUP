"""CLI: собрать Reels из последней статьи и отправить оператору на review.

Делает почти то же, что make_reel, но:
  1. На каждый сегмент ищет 3 кандидата (для frame-edit), а не 1.
  2. Первый рендер берёт candidate[0] на каждом сегменте.
  3. Создаёт ReviewSession в Postgres с segments_snapshot (включая URL'ы
     всех 3 кандидатов на сегмент).
  4. Отправляет MP4 в личку оператору (OPERATOR_CHAT_ID) с inline-клавиатурой
     [❌ Отклонить] [✏️ Редактировать] [✅ Опубликовать].
  5. Сохраняет message_id, чтобы бот мог потом edit_reply_markup.

Запуск:
    docker compose run --rm news-worker python -m nup_pipeline.cli.submit_for_review
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

from nup_pipeline.cli.news_loop import OpenAIJsonLlm
from nup_pipeline.domain.review import ReviewSession
from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.elevenlabs_tts import ElevenLabsTTS
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.ffprobe import probe_duration_sec
from nup_pipeline.infra.pexels import PexelsSearch
from nup_pipeline.infra.pixabay import PixabaySearch
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo
from nup_pipeline.infra.telegram import TelegramClient, TelegramError
from nup_pipeline.services.ffmpeg_builder import build as build_ffmpeg
from nup_pipeline.services.summarize import BilingualSummarizer
from nup_pipeline.services.visual_keywords import VisualKeywords
from nup_pipeline.services.voiceover_scripter import VoiceoverScripter
from nup_pipeline.cli.make_reel import split_sentences, _download

log = logging.getLogger("submit_for_review")


def _candidates_for(keyword: str, want: int = 3) -> list[dict]:
    out: list[dict] = []
    if os.environ.get("PEXELS_API_KEY"):
        try:
            out += PexelsSearch().search_videos(keyword, per_page=want)
        except Exception as e:
            log.warning(f"pexels {keyword!r}: {e}")
    if len(out) < want and os.environ.get("PIXABAY_API_KEY"):
        try:
            out += PixabaySearch().search_videos(keyword, per_page=want)
        except Exception as e:
            log.warning(f"pixabay {keyword!r}: {e}")
    # Pad by cycling if still short.
    if out and len(out) < want:
        while len(out) < want:
            out.append(out[len(out) % len(out)])
    return out[:want]


def _inline_kb(review_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Опубликовать", "callback_data": f"review:approve:{review_id}"},
            ],
            [
                {"text": "✏️ Редактировать", "callback_data": f"review:edit:{review_id}"},
            ],
            [
                {"text": "❌ Отклонить", "callback_data": f"review:decline:{review_id}"},
            ],
        ]
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Render Reel and submit for operator review.")
    p.add_argument("--source", default=None)
    p.add_argument("--candidates", type=int, default=5,
                   help="Сколько вариантов клипа держать на каждый сегмент.")
    args = p.parse_args()

    # 1. Article
    art_repo = PostgresArticleRepo(os.environ["DATABASE_URL"])
    items = art_repo.list_by_source(args.source) if args.source else art_repo.all()
    if not items:
        print("no articles in DB; run `tick_once --seed` first")
        return 1
    article = max(items, key=lambda a: a.created_at)
    print(f"article: [{article.source_id}] {article.title}")

    # 2. Summary + voiceover script
    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    bundle = BilingualSummarizer(llm=llm).summarize(article)
    print(f"RU title: {bundle.title_ru}")
    voice_text = VoiceoverScripter(llm=llm).script(bundle.content_ru)
    print(f"voice: {voice_text[:140]}…")

    # 3. Segments per sentence
    sentences = split_sentences(voice_text)
    n = len(sentences)
    if n == 0:
        print("empty voiceover; abort")
        return 1
    print(f"{n} segments")

    # 4. TTS per sentence
    tmpdir = Path(os.environ.get("REELS_OUT_DIR", "/tmp")) / f"reel_{uuid.uuid4().hex[:8]}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    tts = ElevenLabsTTS()
    audio_paths: list[Path] = []
    durations: list[float] = []
    for i, sentence in enumerate(sentences):
        path = tmpdir / f"voice_{i:02d}.mp3"
        path.write_bytes(tts.synthesize(sentence))
        durations.append(probe_duration_sec(str(path)))
        audio_paths.append(path)
        print(f"  seg{i}: {durations[-1]:.1f}s")

    # 5. Per-segment keywords + N candidates per segment (с дедупом active-клипа)
    per_seg_kws = VisualKeywords(llm=llm).keywords_per_segment(
        bundle.title_en, sentences,
        fallback=[bundle.title_en or "technology"],
    )
    print(f"per-segment keywords: {per_seg_kws}")

    # Preupload-клиент создаём заранее (нужен внутри цикла сегментов).
    review_token = os.environ.get("REVIEW_BOT_TOKEN") or os.environ["TELEGRAM_BOT_TOKEN"]
    reviewer_chat_id = int(os.environ.get("OPERATOR_CHAT_ID", "0"))
    if not reviewer_chat_id:
        print("OPERATOR_CHAT_ID not set; abort")
        return 1
    tg = TelegramClient(token=review_token)

    used_urls: set[str] = set()
    segments_snapshot: list[dict] = []
    chosen_video_paths: list[Path] = []
    uploaded = 0
    for i in range(n):
        kw = per_seg_kws[i]
        # Берём с запасом, чтобы найти ≥3 уникальных + еще для повтор-keyword'ов.
        cands_raw = _candidates_for(kw, want=max(args.candidates * 2, 6))
        if not cands_raw:
            print(f"  seg{i}: NO clips for {kw!r}; abort")
            return 1
        # Сначала пробуем выбрать active из не-использованных.
        unused = [c for c in cands_raw if c["video_url"] not in used_urls]
        ordered = unused + [c for c in cands_raw if c["video_url"] in used_urls]
        # Берём первые N для отображения в edit-mode.
        candidates = ordered[: args.candidates]
        active = candidates[0]
        used_urls.add(active["video_url"])

        candidates_meta = []
        for j, c in enumerate(candidates):
            url = c["video_url"]
            local = tmpdir / f"bg_{i:02d}_{j}{Path(url).suffix.split('?')[0] or '.mp4'}"
            _download(url, str(local))
            # Preupload в Telegram → file_id, сразу deleteMessage.
            file_id: str | None = None
            try:
                file_id, scratch_msg_id = tg.upload_video_for_file_id(
                    reviewer_chat_id, str(local),
                )
                tg.delete_message(reviewer_chat_id, scratch_msg_id)
                uploaded += 1
            except TelegramError as e:
                print(f"  seg{i}/cand{j} preupload failed: {e}; nav fallback to URL")
            # Локальный mp4 нужен только для ffmpeg-рендера активного клипа.
            # Остальные кандидаты — выкидываем, чтобы не забить диск.
            if j != 0:
                try:
                    local.unlink()
                except OSError:
                    pass
                local_path_str = ""
            else:
                local_path_str = str(local)
            candidates_meta.append({
                "video_url": url,
                "local_path": local_path_str,
                "preview_url": c.get("preview_url", ""),
                "file_id": file_id,
            })
            mark = " (DUP)" if c["video_url"] in used_urls and j > 0 else ""
            print(f"  seg{i}/cand{j} ({kw!r}){mark}: {url[:60]}… file_id={'✓' if file_id else '✗'}")
        segments_snapshot.append({
            "text": sentences[i],
            "audio_path": str(audio_paths[i]),
            "duration": durations[i],
            "keyword": kw,
            "candidates": candidates_meta,
            "active_idx": 0,
            "refresh_offset": 0,
        })
        chosen_video_paths.append(Path(candidates_meta[0]["local_path"]))
    print(f"preupload done: {uploaded} file_ids cached")

    # 6. Render
    segments_for_build = [
        Segment(
            audio_uri=str(audio_paths[i]),
            video_uri=str(chosen_video_paths[i]),
            audio_duration_sec=durations[i],
            subtitle_text=sentences[i],
        )
        for i in range(n)
    ]
    out_path = tmpdir / "reel.mp4"
    argv = build_ffmpeg(segments_for_build, music_uri=None, output_path=str(out_path))
    print("running ffmpeg…")
    FfmpegRunner().run(argv, output_path=str(out_path), timeout=600)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"rendered: {out_path} ({size_mb:.1f} MB)")
    # Latest copy under reels_out for scp.
    shutil.copy(out_path, Path(os.environ.get("REELS_OUT_DIR", "/tmp")) / "last_reel.mp4")

    # 7. Persist ReviewSession
    review_id = str(uuid.uuid4())
    channel_id_raw = os.environ.get("TELEGRAM_CHANNEL_ID") or "0"
    channel_id = int(channel_id_raw) if channel_id_raw.lstrip("-").isdigit() else 0
    review = ReviewSession.new(
        render_job_id=review_id,  # we don't have a separate render_job table here
        reviewer_chat_id=reviewer_chat_id,
        channel_id=channel_id,
        review_id=review_id,
    )
    review.output_uri = str(out_path)
    review.caption = (
        f"*{bundle.title_ru}*\n\n"
        f"[📰 Полная новость]({article.link})"
    )[:1024]
    review.segments_snapshot = segments_snapshot
    rev_repo = PostgresReviewRepo(os.environ["DATABASE_URL"])
    rev_repo.save(review)
    print(f"review session saved: {review.id}")

    # 8. Send to operator с [✅/✏️/❌] кнопками. file_id-ы кандидатов уже
    # собраны в шаге 5 — здесь только финальный reel с inline-клавиатурой.
    try:
        msg_id = tg.send_video_file(
            reviewer_chat_id,
            str(out_path),
            caption=review.caption,
            reply_markup=_inline_kb(review.id),
        )
    except TelegramError as e:
        print(f"FAILED to send to operator: {e}")
        if "Forbidden" in str(e):
            print(
                "→ Открой нового review-бота в Telegram и нажми Start.\n"
                "  Если используешь REVIEW_BOT_TOKEN — ищи его по username из BotFather,\n"
                "  иначе — https://t.me/dataist_media_bot."
            )
        return 2
    review.message_id = msg_id
    rev_repo.save(review)
    print(f"OK, review={review.id}, message_id={msg_id}")

    # ВАЖНО: tmpdir намеренно НЕ удаляем. Внутри лежат voice_NN.mp3 и
    # bg_NN_0.mp4 — они нужны для пересборки reel'а при «💾 Сохранить»
    # в edit-mode (если оператор сменил active_idx). Cleanup tmpdir
    # происходит на approve/decline.
    return 0


if __name__ == "__main__":
    sys.exit(main())
