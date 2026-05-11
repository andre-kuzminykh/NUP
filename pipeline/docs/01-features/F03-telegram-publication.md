# F03 — Telegram Publication (text post)

Публикация суммаризированной статьи в Telegram-канал.

## User stories

- **US-F03-1**: As an editor, I want the bot to publish a Markdown-formatted summary with a source link so that readers can read the original.
- **US-F03-2**: As an operator, I want publishes throttled (≥60 s между постами в канал) so that we don't hit Telegram rate limits.
- **US-F03-3**: As an operator, I want failed publishes auto-retried with exponential backoff (3 attempts) so that flaky network doesn't lose posts.

## User flow

```
event "article.summarized" ─► RateLimiter.wait(channel_id)
                            ─► TelegramAdapter.send_message(...)
                              ├─► success → PublicationRepo.save(status="sent", message_id)
                              └─► failure → retry x3 (1s, 4s, 16s) → status="failed"
                            ─► emit "article.published"
```
