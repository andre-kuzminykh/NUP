# Data — ER Model

```
┌─────────────┐      1   N  ┌─────────────┐      1   1  ┌─────────────┐
│  sources    │─────────────│  articles   │─────────────│  summaries  │
│ id PK       │             │ id PK       │             │ article_id  │
│ kind        │             │ source_id FK│             │ title_ru    │
│ url         │             │ link UNIQUE │             │ content_ru  │
│ is_active   │             │ title       │             │ content_tg  │
│ last_seen   │             │ raw_content │             │ created_at  │
│ failure_cnt │             │ published_at│             └─────────────┘
│ cooldown_to │             │ created_at  │
└─────────────┘             └─────────────┘
                                   │ 1
                                   │
                                   │ 0..1
                            ┌─────────────┐      1    N ┌──────────────┐
                            │   reels     │─────────────│   segments   │
                            │ id PK       │             │ id PK        │
                            │ article_id  │             │ reels_id FK  │
                            │ voice_text  │             │ ord          │
                            │ status      │             │ text         │
                            │ video_url   │             │ keywords[]   │
                            │ title_video │             │ audio_uri    │
                            │ caption     │             │ audio_dur    │
                            │ created_at  │             │ video_uri    │
                            │ updated_at  │             └──────────────┘
                            └─────────────┘

┌──────────────┐      1   N  ┌──────────────┐
│ render_jobs  │─────────────│ publications │
│ id PK (uuid) │             │ id PK        │
│ reels_id FK  │             │ kind (text/  │
│ status       │             │  video)      │
│ output_uri   │             │ chat_id      │
│ error_msg    │             │ message_id   │
│ created_at   │             │ status       │
│ updated_at   │             │ error?       │
└──────────────┘             │ created_at   │
                             └──────────────┘
```

## Indexes / constraints

- `articles.link` — UNIQUE (после канонизации).
- `articles(source_id, created_at DESC)` — для «последняя из источника».
- `render_jobs.id` — UUID, primary key.
- `render_jobs(status, updated_at)` — для очереди мониторинга.
- `segments(reels_id, ord)` — UNIQUE.

## Замена Google Sheets

Исходный n8n хранил состояние в двух Sheets-доках (`PostedArticles`, `PostedContent`).
Маппинг:

| Sheet column | Replacement |
|---|---|
| `link` (PostedArticles) | `articles.link` UNIQUE |
| `content` | `summaries.content_ru` |
| `timestamp` | `articles.created_at` |
| `source` | `sources.kind` + `articles.source_id` |
| `voice_ru` | `reels.voice_text_ru` |
| `voice_urls_ru` | `segments.audio_uri[]` (через relation) |
| `video_url_ru` | `reels.video_url` |
| `title_video_ru` | `reels.title_video_ru` |
| `caption_video_ru` | `reels.caption_video_ru` |
