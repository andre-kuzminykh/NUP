"""
Bot entrypoint. Запуск через `python app.py`.

## Трассируемость
Feature: F001, F002 (общая инфра)
"""
from __future__ import annotations

import asyncio
import logging

from core.config import config
from core.loader import make_bot, make_dispatcher
from handler.include_router import setup_routers


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot = make_bot(config.BOT_TOKEN)
    dp = make_dispatcher()
    setup_routers(dp)
    logging.info("bot started, polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
