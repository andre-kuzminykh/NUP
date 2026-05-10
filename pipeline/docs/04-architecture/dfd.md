# Data Flow Diagram (Level 1)

```
                              ┌────────────────────┐
                              │  Source registry   │
                              └────────┬───────────┘
                                       │ (id, kind, url)
                                       ▼
   ┌──────────────┐  proxy   ┌──────────────────────────┐
   │ Proxy Pool   │◄─────────│  F01 Ingest Adapter      │──► raw HTML to S3 (debug, TTL 30d)
   └──────────────┘          │  (rss/html/yt/li/x/tg)   │
                             └─────────┬────────────────┘
                                       │  Article{link,...}
                                       ▼
                                ┌──────────────┐
                                │ articles     │ (insert ON CONFLICT DO NOTHING)
                                └──────┬───────┘
                                       │ event "article.ingested"
                                       ▼
                  ┌────────────────────────────────────┐
                  │ F02 Summarizer (LLM)               │
                  └─────┬───────────────────────┬──────┘
                        │ summary               │ event "article.summarized"
                        ▼                       ▼
                  ┌──────────┐         ┌────────────────────────┐
                  │summaries │         │ F03 TG Text Publisher  │──► Telegram channel
                  └─────┬────┘         └────────────────────────┘
                        │ event "summary.ready"
                        ▼
                  ┌──────────────────────────────────┐
                  │ F04 Voiceover (LLM)              │
                  └────────────┬─────────────────────┘
                               │ reels.voice_text_ru
                               ▼
                  ┌──────────────────────────────────┐
                  │ F05 Segmenter (LLM → JSON)       │
                  └────────────┬─────────────────────┘
                               │ segments[]
                  ┌────────────┴────────────┐
                  ▼                         ▼
       ┌──────────────────┐      ┌────────────────────────────────┐
       │ F06 TTS          │      │ F07 Stock + Vision picker      │
       │ ElevenLabs → MP3 │      │ Pexels → vision desc → picker  │
       │ → MinIO          │      │ → segments.video_uri           │
       └─────────┬────────┘      └─────────┬──────────────────────┘
                 │                         │
                 └─────────┬───────────────┘
                           ▼
                  ┌────────────────────────────────────────┐
                  │ F08 Video Assembly (FFmpeg)            │
                  │ pure FfmpegBuilder.build → argv        │
                  │ FfmpegRunner.run(argv)  → local mp4    │
                  │ Storage.upload → renders/{job_id}.mp4  │
                  └─────────────────┬──────────────────────┘
                                    │ event "render.succeeded"
                                    ▼
                  ┌────────────────────────────────────────┐
                  │ F09 Reels Publisher                    │
                  │ → Telegram (video + title + caption)   │
                  │ → DB update (video_url, ...)           │
                  └────────────────────────────────────────┘
```

## Trust boundaries

- **External net** ↔ **App**: только через `ProxyPool` (F01) и SDK-клиенты (F02/F04/…/F09 c таймаутами).
- **App** ↔ **MinIO**: pre-signed URLs для будущей раздачи (опционально).
- Секреты — только через env, не в логах.
