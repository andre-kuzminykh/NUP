# F05 — Segment Decomposition

LLM режет дикторский текст на сегменты `[{id, text, keywords[3], estimated_duration_sec}]` — кадры для синхронизации со стоковым видеорядом.

## User stories

- **US-F05-1**: As an editor, I want short visual keywords (1–3 английских слова) attached to каждому сегменту so that stock search returns relevant clips.
- **US-F05-2**: As a developer, I want strict JSON output with schema validation so that downstream code can rely on structure.
- **US-F05-3**: As an operator, I want failed JSON parse to retry once с инструкцией «return ONLY JSON» so that мы не падаем на форматных ошибках.

## User flow

```
event "reels.voiceover_ready" ─► SegmenterService(reels_id)
   └─► OpenAI(prompt + voice_text) → JSON
       ├─► JSON.parse + jsonschema validate
       ├─► retry once on schema fail
       └─► SegmentRepo.bulk_insert([Segment, ...])
            └─► emit "reels.segments_ready"
```
