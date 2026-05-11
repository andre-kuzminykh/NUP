# NUP — самостоятельный конвейер (замена n8n + Sheets + Shotstack)

Репозиторий содержит два связанных проекта:

| Каталог | Назначение | Точка входа | PRD |
|---|---|---|---|
| `pipeline/` | Backend (FastAPI + Celery + Postgres + MinIO + FFmpeg). Источник данных, БД, рендер. | `uvicorn nup_pipeline.api.app:app` | `pipeline/prd.json` |
| `bot/` | Telegram-бот для оператора (aiogram 3, виджетная архитектура). Не содержит БД — общается с pipeline по HTTP. | `python bot/app.py` | `bot/prd.json` |

```
   Telegram ─► bot/  ──HTTP──► pipeline/ ──► Postgres + MinIO + FFmpeg + LLM-провайдеры
```

## Реализовано в этой ветке

**Backend** (`pipeline/`, фича F008 «Video Assembly» под TDD):
- `domain/` — `Segment + chunk_subtitle`, `RenderJob + state machine` (REQ-F08-008/012).
- `services/ffmpeg_builder.py` — чистая функция, собирает argv (REQ-F08-002..006, 011).
- `services/video_assembly.py` — оркестратор с идемпотентным re-submit (REQ-F08-007, 009, 010).
- `infra/ffmpeg.py` — обёртка над subprocess.
- `api/routers/renders.py` — POST/GET `/v1/renders` (REQ-F08-001).
- 35 тестов: 30 unit + 4 e2e (TestClient + in-memory fakes) + 1 integration (реальный FFmpeg, рендерит 1080×1920 H.264).
- Спека на остальные F001–F010 — в `pipeline/docs/` и `pipeline/prd.json`.

**Bot** (`bot/`, две фичи под TDD):
- F001 `/start` — приветствие, очистка FSM (1 сценарий, 1 тест).
- F002 `/render_status <uuid>` — статус рендера через `service/api/renders_api.py`. 3 сценария (found / not-found / invalid-uuid), 6 тестов с параметризацией.
- Архитектура строго по инструкции:
  - `node/{tag}/{trigger,code,answer}/` — UI-кирпичики.
  - `handler/v1/user/{tag}/{Feature ID}/{name}_widget.py` — виджеты-оркестраторы.
  - `service/api/{name}_api.py` — HTTP-клиенты к backend.
  - Тесты в `tests/{Feature ID}_{name}/test_{Scenario ID}_*.py`.
  - Каждый модуль имеет `## Трассируемость` в docstring.
- Бот не подключается к БД — только REST к pipeline.

## Run / test

```bash
# backend
cd pipeline
docker compose up -d                  # postgres, redis, minio
make install                          # pip install -e ".[dev]"
make test                             # 30 unit
make test-all                         # +4 e2e +1 integration
make run                              # uvicorn ...

# bot — после установки aiogram, httpx и подстановки BOT_TOKEN
cd bot
pip install -r requirements.txt
cp example.env .env && $EDITOR .env   # вставить BOT_TOKEN
BACKEND_URL=http://localhost:8000 python app.py

# tests
cd bot && python -m pytest -v         # 7 tests, без сети, на моках
```

## Маппинг старых ID → новых

В первой итерации фичи именовались `F01..F10` (markdown-доки в `pipeline/docs/01-features/`).
Канонический формат по инструкции — `F001..F010`. Соответствие 1:1:
`F01 ↔ F001`, `F02 ↔ F002`, ..., `F08 ↔ F008`, `F10 ↔ F010`. В новых артефактах
(`prd.json`, тесты бота) используется только `Fxxx`. Старые markdown-доки оставлены
как есть, чтобы не плодить шумных переименований; маппинг очевиден.
