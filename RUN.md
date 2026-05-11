# Run-book для @dataist_media_bot → @d_media_ai

Этот файл — практический чек-лист, чтобы поднять стенд с твоим токеном. **Токены не коммитить.** `.env` уже в `.gitignore`.

## 0. Безопасность

Токен в открытом чате однажды засвечен. Когда стенд заработает, **сделай `/revoke` у @BotFather** и подставь новый токен в `.env` одной строчкой — код менять не придётся.

## 1. Проверка канала

Из своей машины (где есть выход в интернет) убедись, что бот действительно админ в @d_media_ai:

```bash
TOKEN='ВСТАВЬ_ТОКЕН'
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | jq
curl -s "https://api.telegram.org/bot${TOKEN}/getChat?chat_id=@d_media_ai" | jq
```

В `getChat` должен прийти `type: "channel"`. Если 400/403 — значит бот не добавлен админом, повтори шаг через настройки канала.

## 2. Локальный запуск backend

```bash
cd pipeline
cp .env.example .env
# в .env:
#   TELEGRAM_BOT_TOKEN=<твой токен>
#   TELEGRAM_DEFAULT_CHANNEL=@d_media_ai
docker compose up -d           # postgres + redis + minio
pip install -e ".[dev]"
make migrate                   # alembic upgrade head (когда добавим миграции)
uvicorn nup_pipeline.api.app:app --reload
```

API на `http://localhost:8000`; OpenAPI на `/docs`.

Готовые endpoints в этой ветке: `POST /v1/renders`, `GET /v1/renders/{job_id}`, `GET /health`.

## 3. Локальный запуск operator-бота

```bash
cd bot
cp example.env .env
# в .env:
#   BOT_TOKEN=<тот же токен>
#   BACKEND_URL=http://localhost:8000
pip install -r requirements.txt
python app.py
```

В Telegram открой `t.me/dataist_media_bot`:
- `/start` — приветствие, в нём подсказка про /render_status.
- `/render_status <uuid>` — статус рендера из БД pipeline.

## 4. Smoke-тест публикации в @d_media_ai

F003 (TextPublisher) уже в коде, под TDD. Endpoint поверх него ещё не вынесен — пока используется из Python:

```python
from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter
from nup_pipeline.infra.telegram import TelegramClient
from nup_pipeline.services.text_publication import TextPublisher

class _MemRepo:
    def __init__(self): self.rows = []
    def save(self, p): self.rows.append(p)

client = TelegramClient(token="<TOKEN>")     # реальные запросы к Bot API
publisher = TextPublisher(
    client=client,
    rate_limiter=InMemoryRateLimiter(min_interval_sec=60),
    repo=_MemRepo(),
)
publisher.publish("@d_media_ai", "*Тестовый пост*\n\nЭто проверка публикации через nup_pipeline.")
```

Если всё ок — пост появится в канале, в `publisher._repo.rows[-1]` будет `status=SENT`, `message_id=...`.

## 5. Что дальше по плану

| Когда нужно | Что | Где |
|---|---|---|
| Чтобы посты шли автоматически | F001 ingest + F002 summary + endpoint `POST /v1/publications` | `pipeline/docs/01-features/F01,F02.md` |
| Чтобы reels автоматически уезжали в канал | F009 (Reels Publication) поверх готового F08 | `pipeline/prd.json` → F009 |
| Чтобы оператор управлял из бота | новые виджеты `/ingest`, `/render`, `/articles` в `bot/handler/v1/user/...` | `bot/prd.json` |
