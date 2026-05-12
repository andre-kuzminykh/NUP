"""CLI: переотправить уже отрендеренный review оператору в Telegram.

Полезно, если первый sendVideo упал ("chat not found" — оператор не нажал
Start у бота, бот забанили, и т.п.) и мы не хотим заново качать 30 клипов
+ рендерить mp4. Берёт review_id (или latest pending без message_id),
читает output_uri/caption из Postgres и пушит mp4 в чат оператора.

Запуск:
    docker compose run --rm news-worker python -m nup_pipeline.cli.resend_review
    docker compose run --rm news-worker python -m nup_pipeline.cli.resend_review --review-id <uuid>
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from nup_pipeline.infra.db import make_engine
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo, _ReviewRow
from nup_pipeline.infra.telegram import TelegramClient, TelegramError

log = logging.getLogger("resend_review")


def _inline_kb(review_id: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Опубликовать", "callback_data": f"review:approve:{review_id}"}],
            [{"text": "✏️ Редактировать", "callback_data": f"review:edit:{review_id}"}],
            [{"text": "❌ Отклонить", "callback_data": f"review:decline:{review_id}"}],
        ]
    }


def _latest_unsent(database_url: str) -> str | None:
    engine = make_engine(database_url)
    Session = sessionmaker(engine, expire_on_commit=False)
    with Session() as s:
        row = s.execute(
            select(_ReviewRow)
            .where(_ReviewRow.message_id.is_(None))
            .order_by(_ReviewRow.created_at.desc())
        ).scalar_one_or_none()
        if row:
            return row.id
        # Fallback: latest review regardless of message_id.
        row = s.execute(
            select(_ReviewRow).order_by(_ReviewRow.created_at.desc())
        ).scalar_one_or_none()
        return row.id if row else None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Resend an already-rendered review to operator.")
    p.add_argument("--review-id", default=None, help="UUID; default — latest unsent review.")
    args = p.parse_args()

    db_url = os.environ["DATABASE_URL"]
    repo = PostgresReviewRepo(db_url)

    review_id = args.review_id or _latest_unsent(db_url)
    if not review_id:
        print("no reviews in DB")
        return 1
    review = repo.get(review_id)
    if review is None:
        print(f"review {review_id} not found")
        return 1
    if not review.output_uri:
        print(f"review {review_id} has no output_uri (render not done?)")
        return 1
    if not os.path.exists(review.output_uri):
        print(f"output_uri missing on disk: {review.output_uri}")
        return 1

    review_token = os.environ.get("REVIEW_BOT_TOKEN") or os.environ["TELEGRAM_BOT_TOKEN"]
    tg = TelegramClient(token=review_token)
    print(f"resending review={review.id} to chat={review.reviewer_chat_id}")
    try:
        msg_id = tg.send_video_file(
            review.reviewer_chat_id,
            review.output_uri,
            caption=review.caption or "",
            reply_markup=_inline_kb(review.id),
        )
    except TelegramError as e:
        print(f"FAILED: {e}")
        return 2
    review.message_id = msg_id
    repo.save(review)
    print(f"OK, message_id={msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
