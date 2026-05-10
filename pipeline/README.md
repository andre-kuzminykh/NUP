# NUP Pipeline

Self-hosted замена n8n-конвейера: ingest news → summarize → publish to Telegram → generate Reels (own DB + own renderer).

## Стек

- **Backend / orchestration**: Python 3.11, FastAPI, Celery (Redis broker), SQLAlchemy 2 + Alembic.
- **Storage**: PostgreSQL 16 (state, jobs, traceability), MinIO (S3-совместимое; аудио, видео, рендеры).
- **Render**: FFmpeg напрямую (concat + drawtext + amix), без Shotstack.
- **Outbound HTTP**: httpx с обязательной ротацией прокси (anti-bot).
- **AI**: OpenAI (GPT-4.1, gpt-4o-mini vision), ElevenLabs TTS, Pexels API.

## Документация

| Каталог | Содержание |
|---|---|
| `docs/01-features/` | Каталог фич, user stories, user flows |
| `docs/02-bdd/` | Gherkin-сценарии (`*.feature`) |
| `docs/03-requirements/` | Функциональные и нефункциональные требования (с ID) |
| `docs/04-architecture/` | C4-обзор, ER, DFD, инфраструктура, OpenAPI |
| `docs/05-prompts/` | Промты как отдельные MD-файлы (одна ответственность на файл) |
| `docs/06-impl-plan/` | План имплементации, декомпозиция по задачам |
| `docs/07-tests-matrix/` | Матрица трассируемости REQ-ID → тесты |

## Скоуп этой итерации

В этом ходе сделана **полная TDD-вертикаль по фиче F08 «Video Assembly (FFmpeg)»**:

1. Спека: features, user stories, BDD, requirements (с ID).
2. Архитектура: ER, DFD, infra, OpenAPI.
3. Тесты: unit + integration + e2e (все ссылаются на REQ-ID через маркеры).
4. Имплементация: FFmpeg builder + assembly service + storage adapter + REST endpoint.

Остальные фичи (F01–F07, F09–F10) описаны в спеке и архитектуре, но кода не имеют — это roadmap.

## Quick start

```bash
make install           # uv pip install -e ".[dev]"
docker compose up -d   # postgres, redis, minio
make migrate           # alembic upgrade head
make test              # pytest -m "not docker"      — only unit
make test-all          # включая integration + e2e
make run               # uvicorn nup_pipeline.api.app:app --reload
```
