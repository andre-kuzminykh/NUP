# Infrastructure

## Local / dev

```
docker compose up -d
  ├─ postgres:16
  ├─ redis:7
  └─ minio (S3 :9000, console :9001)

uvicorn nup_pipeline.api.app:app --reload
celery -A nup_pipeline.infra.celery_app worker -Q ingest,llm,render,publish -l INFO
celery -A nup_pipeline.infra.celery_app beat -l INFO
```

## Production sketch

- **Compute**: один или несколько хостов; каждый сервис в Docker.
- **Storage**: managed Postgres (RDS/Cloud SQL), MinIO в одной сети, объёмные тома на быстрых дисках.
- **Network**: outbound через прокси-пул (residential или mobile, поставщик подключается через `PROXY_POOL` env).
- **Scaling**:
  - `worker-render` — CPU-bound, скейлится горизонтально по числу одновременных Reels.
  - `worker-llm` — bound by OpenAI rate limits → ограничивать `worker_concurrency` и Celery rate-limit.
- **Backups**: PostgreSQL pg_dump nightly, MinIO bucket replication weekly.
- **Secrets**: SOPS / Vault; никаких .env в git. `.env.example` в репо для разработчиков.

## Observability

- Logs: stdout JSON → Loki / OpenSearch.
- Metrics: Prometheus exporter из FastAPI (`prometheus-fastapi-instrumentator`) + Celery (custom signals).
- Traces: OpenTelemetry SDK на entrypoints (api, celery), exporter в OTLP collector.
