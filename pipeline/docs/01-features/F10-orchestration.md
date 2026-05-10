# F10 — Pipeline Orchestration

Связывает всё: Celery DAG из задач, привязанных к доменным событиям. Замена n8n.

## User stories

- **US-F10-1**: As an operator, I want a single Celery beat schedule to drive ingestion every N minutes per source so that I don't manage cron entries by hand.
- **US-F10-2**: As an operator, I want each domain event (`article.ingested`, `article.summarized`, …) to fan out to its handlers without code coupling so that we can add subscribers freely.
- **US-F10-3**: As an operator, I want a CLI to replay any failed step (`nup replay --reels-id … --from segments`) so that debugging is possible without rerunning the whole flow.

## User flow

```
beat (every 10 min) ─► dispatch_ingestion(source_id) per active source

handlers (workers, по очередям):
  ingestion.* → F01
  summarization → F02
  publication.text → F03
  reels.script → F04
  reels.segments → F05
  reels.tts → F06
  reels.stock_pick → F07
  reels.assemble → F08
  reels.publish → F09
```
