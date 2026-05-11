# Architecture Overview

## C4 — Context

```
┌───────────────────────────────────────────────────────────────────────┐
│                            External world                              │
│                                                                       │
│   RSS / HTML sites    YouTube     LinkedIn / X / TG profiles          │
│         │  │  │           │                  │                        │
│         ▼  ▼  ▼           ▼                  ▼                        │
│              [ ProxyPool (rotating, healthchecked) ]                  │
│                                  │                                    │
│                                  ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐  │
│   │                      NUP Pipeline                              │  │
│   │  FastAPI ⇆ Celery workers ⇆ EventBus(Redis Streams)            │  │
│   │   │                                       │                   │  │
│   │   ▼                                       ▼                   │  │
│   │ Postgres (state, jobs)           MinIO (audio, video, raw)    │  │
│   └───────────────────┬────────────────────┬──────────────────────┘  │
│                       │                    │                          │
│                       ▼                    ▼                          │
│             OpenAI / ElevenLabs / Pexels       Telegram Bot API       │
└───────────────────────────────────────────────────────────────────────┘
```

## C4 — Containers

- **api** (FastAPI): HTTP, OpenAPI, admin/manual triggers.
- **worker-ingest** (Celery): F01.
- **worker-llm** (Celery): F02, F04, F05, F07-vision/picker, F09 captions.
- **worker-render** (Celery): F08.
- **worker-publish** (Celery): F03, F09.
- **scheduler** (Celery beat): F10.
- **postgres**, **redis**, **minio** — managed via docker-compose.

## Layered packaging (Hexagonal-ish)

```
nup_pipeline/
  api/         ← HTTP transport, FastAPI routers, DTOs (Pydantic)
  domain/      ← entities, value objects, errors, rules (no I/O)
  services/    ← orchestration use-cases (depends only on domain + ports)
  ai/          ← prompt loaders, LLM clients (ports + adapters)
  infra/       ← DB models, S3, FFmpeg subprocess, HTTP, proxies
```

Правило зависимостей: `api → services → domain`; `services → ai/infra` через интерфейсы (`Protocol`).

## Идемпотентность

- `Article.link` — UNIQUE.
- `RenderJob.id` — клиент может задать его сам (UUID); повторный POST не ре-рендерит.
- Celery taskи имеют `task_id == reels_id` где это безопасно, чтобы acks_late+visibility_timeout не запускали дубль.
