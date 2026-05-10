# Features Catalogue

Каждая фича имеет ID `Fxx`. Под каждой фичей — user stories `US-Fxx-N` и user flow.
BDD-сценарии живут в `docs/02-bdd/`, требования — в `docs/03-requirements/`.

| ID | Фича | Статус кода |
|---|---|---|
| F01 | Source Ingestion (RSS, HTML, YouTube, LinkedIn, X, Telegram) с прокси | spec only |
| F02 | Article Summarization (LLM) | spec only |
| F03 | Telegram Publication (текстовый пост) | spec only |
| F04 | Voiceover Script Generation (LLM) | spec only |
| F05 | Segment Decomposition (LLM → JSON segments) | spec only |
| F06 | TTS Synthesis (ElevenLabs → MinIO) | spec only |
| F07 | Stock Video Search & Vision Selection (Pexels + GPT-4o vision) | spec only |
| **F08** | **Video Assembly (FFmpeg)** | **implemented (TDD)** |
| F09 | Reels Publication (Telegram + DB update) | spec only |
| F10 | Pipeline Orchestration (Celery DAG) | spec only |

Cross-cutting:
- **CC1** Proxy Pool & Anti-bot.
- **CC2** Idempotency & deduplication (по `link`).
- **CC3** Observability (structured logs, metrics, traceability).
