# Non-Functional Requirements

ID-конвенция: `NFR-Cxx-NNN` для cross-cutting и `NFR-Fxx-NNN` для фич.

## Performance

| ID | Требование |
|---|---|
| NFR-F08-P01 | Рендер 1-минутного Reels MUST завершаться за ≤60 сек на 4-core машине без GPU. |
| NFR-F08-P02 | RAM-потребление одной задачи рендера MUST быть ≤1 GiB. |
| NFR-F06-P01 | TTS одного сегмента (≤10 сек речи) MUST завершаться за ≤8 сек p95. |

## Reliability

| ID | Требование |
|---|---|
| NFR-CC-R01 | Каждая внешняя зависимость (OpenAI, ElevenLabs, Pexels, Telegram, S3) MUST вызываться с явным таймаутом (по умолчанию 30 сек). |
| NFR-CC-R02 | Все идемпотентные операции (POST /renders с тем же job_id, апдейты БД по `link`) MUST давать одинаковый результат при повторе. |
| NFR-CC-R03 | Worker MUST переживать падение БД: задача переходит в retry-очередь с экспоненциальным backoff. |

## Security & Anti-bot (CC1)

| ID | Требование |
|---|---|
| NFR-CC1-S01 | Все исходящие HTTP-запросы к источникам (F01) MUST идти через `ProxyPool`. |
| NFR-CC1-S02 | `ProxyPool` MUST поддерживать стратегии `round_robin`, `random`, `least_used`. |
| NFR-CC1-S03 | Прокси с 3 подряд провалами MUST быть в cooldown 10 мин (configurable). |
| NFR-CC1-S04 | User-Agent MUST ротироваться из пула из ≥5 строк, чтобы не выглядеть как бот. |
| NFR-CC-S05 | Секреты (API-ключи, пароли) MUST читаться только из env, никогда из репозитория. |

## Observability (CC3)

| ID | Требование |
|---|---|
| NFR-CC3-O01 | Все сервисы MUST логировать в JSON с полями `ts`, `level`, `service`, `req_id`, `job_id?`, `event`, `payload`. |
| NFR-CC3-O02 | На каждый Celery task MUST экспортироваться Prometheus метрики `task_duration_seconds`, `task_failures_total`. |
| NFR-CC3-O03 | Каждое требование REQ-Fxx-NNN MUST иметь хотя бы один автоматический тест (см. `docs/07-tests-matrix/traceability.md`). |

## Compatibility

| ID | Требование |
|---|---|
| NFR-CC-C01 | Поддерживаемая платформа: Linux x86_64, Python 3.11+, FFmpeg ≥6.0. |
| NFR-CC-C02 | Postgres ≥15, Redis ≥7, MinIO ≥latest stable. |
