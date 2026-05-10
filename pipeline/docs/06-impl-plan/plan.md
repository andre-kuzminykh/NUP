# Implementation Plan

Этап = одна-две фичи + общие компоненты. Внутри этапа — задачи (Tx.y) с критериями приёмки.

## Этап 0 — Foundations (этой итерацией: частично)

| Task | Описание | Acceptance |
|---|---|---|
| T0.1 | Каркас репо (pyproject, docker-compose, Makefile, .env.example) | `pip install -e .` проходит, `docker compose up` поднимает 3 сервиса. |
| T0.2 | DB-миграции (Alembic), модели domain (Article, Source, Reels, Segment, RenderJob) | `alembic upgrade head` создаёт схему из ER. |
| T0.3 | S3/MinIO адаптер (`infra/storage.py`) | Round-trip put/get работает на testcontainers. |
| T0.4 | EventBus (Redis Streams), CeleryApp | `celery -A nup_pipeline.infra.celery_app worker` стартует. |
| T0.5 | Структурный JSON-логгер | NFR-CC3-O01. |
| T0.6 | ProxyPool (round_robin/random/least_used + cooldown) | NFR-CC1-S01..S04, REQ-F01-003..005. |

**В этой итерации сделано: T0.1 полностью; T0.2/T0.3 частично (только то, что нужно для F08 — модель `RenderJob`, `Storage` с `upload`).**

## Этап 1 — F01 Source Ingestion (next)

| Task | Acceptance |
|---|---|
| T1.1 | Адаптеры RSS, HTML — REQ-F01-001..002, REQ-F01-007 |
| T1.2 | Адаптер YouTube (yt-dlp metadata) — REQ-F01-001 |
| T1.3 | Адаптеры LinkedIn / X / Telegram — REQ-F01-001 |
| T1.4 | Дедупликация по канонической ссылке — REQ-F01-006 |
| T1.5 | Беат-задача `ingest_all_active` |

## Этап 2 — F02 / F03 (next)

| Task | Acceptance |
|---|---|
| T2.1 | LLM client + загрузчик промтов из MD — REQ-F02-001 |
| T2.2 | Summarizer + retry на нарушение формата — REQ-F02-002..003 |
| T2.3 | Telegram text publisher с throttling и retry — REQ-F03-001..003 |

## Этап 3 — F04 / F05 (next)

| Task | Acceptance |
|---|---|
| T3.1 | Voiceover service (REQ-F04-001..003) |
| T3.2 | Segmenter service + jsonschema (REQ-F05-001..003) |

## Этап 4 — F06 / F07 (next)

| Task | Acceptance |
|---|---|
| T4.1 | ElevenLabs adapter, ffprobe duration (REQ-F06-001..003) |
| T4.2 | Pexels adapter (REQ-F07-001) |
| T4.3 | Vision describer + picker + cross-segment dedupe (REQ-F07-002..003) |

## Этап 5 — F08 Video Assembly **(сделано в этой итерации)**

| Task | Acceptance | Tests |
|---|---|---|
| T5.1 | `domain.RenderJob` + state-machine | unit `test_render_job_state.py` (REQ-F08-008) |
| T5.2 | `services.ffmpeg_builder.build()` чистая | unit `test_ffmpeg_builder.py` (REQ-F08-002..006, F08-011, F08-012) |
| T5.3 | `infra.ffmpeg.FfmpegRunner.run()` обёртка | integration `test_ffmpeg_real.py` (REQ-F08-002..004) |
| T5.4 | `infra.storage.Storage.upload()` | integration `test_storage_minio.py` (REQ-F08-007) |
| T5.5 | `services.video_assembly.AssembleService` оркестратор + idempotency | unit `test_video_assembly_service.py` (REQ-F08-009..010) |
| T5.6 | API `/v1/renders` POST/GET | e2e `test_render_endpoint.py` (REQ-F08-001) |

## Этап 6 — F09 / F10 (next)

| Task | Acceptance |
|---|---|
| T6.1 | Reels publisher (REQ-F09-001..003) |
| T6.2 | Celery beat + DAG связки (REQ-F10-001..003) |
| T6.3 | CLI `nup replay` |

## Параллельно — observability

| Task | Acceptance |
|---|---|
| TO.1 | Prometheus metrics на api + Celery (NFR-CC3-O02) |
| TO.2 | OpenTelemetry traces |
