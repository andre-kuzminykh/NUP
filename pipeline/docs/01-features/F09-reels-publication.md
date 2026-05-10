# F09 — Reels Publication

Публикация финального MP4 в Telegram-канал + апдейт реляционной строки в БД.

## User stories

- **US-F09-1**: As an editor, I want generated title + caption (LLM) to be posted alongside the video so that the post looks publishable without manual edits.
- **US-F09-2**: As an operator, I want a single retry on Telegram 5xx so that transient errors don't kill the whole job.
- **US-F09-3**: As an operator, I want the DB row updated with `video_url`, `title_video_ru`, `caption_video_ru` so that we have a final canonical record per article.

## User flow

```
event "render.succeeded" ─► gen_title(LLM) ║ gen_caption(LLM)  (parallel)
                          ─► TelegramAdapter.send_video(video_url, caption=title+caption)
                          ─► ReelsRepo.update(video_url, title, caption, status="published")
                          ─► emit "reels.published"
```
