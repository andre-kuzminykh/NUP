"""CLI: собрать Reels из последней статьи и отправить оператору на review.

Делает почти то же, что make_reel, но:
  1. На каждый сегмент ищет N кандидатов (для frame-edit), а не 1.
  2. Создаёт ReviewSession в Postgres с segments_snapshot (включая URL'ы
     всех кандидатов на сегмент + Telegram file_id для мгновенного swap).
  3. Отправляет MP4 в личку оператору (OPERATOR_CHAT_ID) с inline-клавиатурой.
  4. Сохраняет message_id, чтобы бот мог потом edit_reply_markup.

Запуск:
    docker compose run --rm news-worker python -m nup_pipeline.cli.submit_for_review
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path

from nup_pipeline.cli.news_loop import OpenAIJsonLlm
from nup_pipeline.domain.review import ReviewSession
from nup_pipeline.infra.article_repo_pg import PostgresArticleRepo
from nup_pipeline.infra.elevenlabs_tts import ElevenLabsTTS
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.infra.pexels import PexelsSearch
from nup_pipeline.infra.pixabay import PixabaySearch
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo
from nup_pipeline.infra.telegram import TelegramClient, TelegramError
from nup_pipeline.services.review_builder import ReviewBuilder

log = logging.getLogger("submit_for_review")


def _inline_kb(review_id: str) -> dict:
    """Главная клавиатура под reel'ом: большая «Перегенерировать» сверху,
    три кнопки поменьше внизу одной строкой."""
    return {
        "inline_keyboard": [
            [{"text": "🔁 Перегенерировать",
              "callback_data": f"review:regenerate:{review_id}"}],
            [
                {"text": "❌ Отклонить",
                 "callback_data": f"review:decline:{review_id}"},
                {"text": "✏️ Редактировать",
                 "callback_data": f"review:edit:{review_id}"},
                {"text": "✅ Принять",
                 "callback_data": f"review:approve:{review_id}"},
            ],
        ]
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Render Reel and submit for operator review.")
    p.add_argument("--source", default=None)
    p.add_argument("--candidates", type=int, default=10,
                   help="Сколько вариантов клипа держать на каждый сегмент.")
    args = p.parse_args()

    # 1. Article.
    art_repo = PostgresArticleRepo(os.environ["DATABASE_URL"])
    items = art_repo.list_by_source(args.source) if args.source else art_repo.all()
    if not items:
        print("no articles in DB; run `tick_once --seed` first")
        return 1
    article = max(items, key=lambda a: a.created_at)
    print(f"article: [{article.source_id}] {article.title}")

    # 2. Setup.
    reviewer_chat_id = int(os.environ.get("OPERATOR_CHAT_ID", "0"))
    if not reviewer_chat_id:
        print("OPERATOR_CHAT_ID not set; abort")
        return 1
    review_token = os.environ.get("REVIEW_BOT_TOKEN") or os.environ["TELEGRAM_BOT_TOKEN"]
    channel_id_raw = os.environ.get("TELEGRAM_CHANNEL_ID") or "0"
    channel_id = int(channel_id_raw) if channel_id_raw.lstrip("-").isdigit() else 0

    rev_repo = PostgresReviewRepo(os.environ["DATABASE_URL"])
    review = ReviewSession.new(
        render_job_id=str(uuid.uuid4()),
        reviewer_chat_id=reviewer_chat_id,
        channel_id=channel_id,
    )
    rev_repo.save(review)

    # 3. Build content (TTS + per-segment search + preupload + ffmpeg).
    llm = OpenAIJsonLlm(api_key=os.environ["OPENAI_API_KEY"])
    tg = TelegramClient(token=review_token)
    builder = ReviewBuilder(
        llm=llm,
        tts=ElevenLabsTTS(),
        pexels=PexelsSearch() if os.environ.get("PEXELS_API_KEY") else None,
        pixabay=PixabaySearch() if os.environ.get("PIXABAY_API_KEY") else None,
        telegram=tg,
        ffmpeg_runner=FfmpegRunner(),
        review_repo=rev_repo,
        out_root=Path(os.environ.get("REELS_OUT_DIR", "/tmp")),
        candidates_per_segment=args.candidates,
    )
    print("building review …")
    builder.build(article, review)
    print(f"review built: {review.id} → {review.output_uri}")

    # 4. Send to operator.
    try:
        msg_id = tg.send_video_file(
            reviewer_chat_id,
            review.output_uri,
            caption=review.caption,
            reply_markup=_inline_kb(review.id),
        )
    except TelegramError as e:
        print(f"FAILED to send to operator: {e}")
        if "Forbidden" in str(e):
            print(
                "→ Открой нового review-бота в Telegram и нажми Start.\n"
                "  Если используешь REVIEW_BOT_TOKEN — ищи его по username из BotFather."
            )
        return 2
    review.message_id = msg_id
    rev_repo.save(review)
    print(f"OK, review={review.id}, message_id={msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
