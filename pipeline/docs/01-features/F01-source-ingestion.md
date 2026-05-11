# F01 — Source Ingestion

Объединяет RSS-фиды, HTML-листинги, и профили в социальных платформах в единую модель `Article{link, title, source, published_at, raw_content}`.

## User stories

- **US-F01-1**: As an editor, I want to register a new source by URL and type so that the pipeline starts pulling articles from it without code changes.
- **US-F01-2**: As an editor, I want each source to fetch only the latest item per cycle so that we don't flood the queue.
- **US-F01-3**: As an operator, I want all outbound HTTP to go through a rotating proxy pool so that target sites don't block us as a bot.
- **US-F01-4**: As an editor, I want to add YouTube channel URLs as a source so that new videos are picked up.
- **US-F01-5**: As an editor, I want to add LinkedIn / X / Telegram public profile URLs as a source so that their latest posts are picked up.
- **US-F01-6**: As an operator, I want articles to be deduplicated by canonical `link` so that we never publish the same item twice.

## User flow (RSS / HTML)

```
Schedule (cron) ─► SourceRegistry.list_active()
                  └─► for each Source:
                       ProxyPool.acquire() ─► HTTP GET via httpx (proxy)
                       └─► AdapterByType(source.kind).parse(payload) → Article(s)
                          └─► Dedup.is_seen(link)?  yes → drop
                                                    no  → ArticleRepo.save()
                                                          ► EventBus.emit("article.ingested")
```

## User flow (YouTube / LinkedIn / X / Telegram profile)

Same as above, but adapter depends on `source.kind`:
- `youtube_channel` → YouTube Data API or `yt-dlp --flat-playlist` для последнего видео.
- `linkedin_profile` → авторизованный сессионный куки + прокси, парсинг последнего поста.
- `x_profile` → Nitter mirror (через прокси) или X API v2 (если есть токен).
- `telegram_channel` → telethon (read-only) либо публичный t.me/s/{channel}.

Адаптеры **должны** возвращать одинаковый `Article` и помечать `source.kind` в метаданных.

## Edge cases

- Source даёт пустой ответ → не считать ошибкой, не плодить алертов; metrics counter `source.empty`.
- HTTP 403/429 → перебрать следующий прокси; после N подряд провалов на одном прокси — пометить его `unhealthy` на TTL.
- HTML-структура изменилась → `parse()` вернёт `None` + лог уровня ERROR, чтобы можно было быстро поправить селектор.

## Open questions

- Хранить ли «сырой» HTML в S3 для отладки селекторов? Предложение: да, ключ `raw/{source_id}/{date}/{hash}.html`, TTL 30д.
