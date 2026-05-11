# F012 — Review Decision (Approve / Decline)

Обработка решения оператора: approve → публикация в канал, decline → останавливаем.
Edit → переход в состояние `IN_EDIT`, дальше — F013.

## User stories

- **US-F012-1**: As an operator, when I tap **Approve**, I want the bot to publish the video to @d_media_ai with the same bilingual caption and confirm to me in chat.
- **US-F012-2**: As an operator, when I tap **Decline**, I want the bot to mark the Reels declined and reply «Отклонено / Declined», without ever posting to the channel.
- **US-F012-3**: As an operator, after my decision the inline keyboard MUST disappear from the original message so I don't accidentally click again.
- **US-F012-4**: As a developer, I want repeated approve/decline on the same review to be **idempotent** so that network retries don't double-post.

## State machine

```
PENDING_REVIEW ──approve───► APPROVED   ──► VideoPublisher.publish(channel_id, ...)
              ──decline───► DECLINED   (no publish)
              ──start_edit──► IN_EDIT  (F013 takes over)
```

Любой переход в произвольное состояние (например, `APPROVED → DECLINED`)
MUST падать `IllegalReviewStateError`. `start_edit` доступен только из `PENDING_REVIEW`.

## Requirements

| ID | Требование |
|---|---|
| REQ-F012-001 | `ReviewDecider.approve(review_id)` MUST: проверить, что `status == PENDING_REVIEW`; перевести в `APPROVED`; вызвать `VideoPublisher.publish(channel_id, output_uri, caption)`; вернуть обновлённую сессию. |
| REQ-F012-002 | `ReviewDecider.decline(review_id)` MUST перевести в `DECLINED` без вызова `VideoPublisher`. |
| REQ-F012-003 | Повторный `approve()` для `APPROVED` MUST вернуть существующий результат без повторной публикации (BR — идемпотентность). |
| REQ-F012-004 | Повторный `decline()` для `DECLINED` MUST вернуть существующий результат, без побочных эффектов. |
| REQ-F012-005 | После approve `Publication` запись в БД MUST содержать `kind=VIDEO`, `chat_id=channel_id`, `message_id=...`. |
| REQ-F012-006 | Caption публикации в канале MUST быть тем же двуязычным RU+EN текстом, что и в preview оператору. |
| REQ-F012-007 | Любой запрещённый переход MUST поднимать `IllegalReviewStateError`. |

## BDD: docs/02-bdd/F012-review-decision.feature
