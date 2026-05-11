# F011 — Reels Review Submission

После успешного F008 (рендер) Reels **не публикуется сразу в канал**, а уходит оператору
в бот на ревью. Видео отправляется в личку оператору с inline-клавиатурой
`[✅ Approve / Одобрить] [❌ Decline / Отклонить] [✏️ Edit / Править]`.

## User stories

- **US-F011-1**: As an operator, I want to receive every generated Reels in my private chat with the bot **before** it goes to the channel, so that I can catch failures and off-topic content.
- **US-F011-2**: As an operator, I want the caption shown together with the preview to be **bilingual (RU + EN)** so that I can quickly judge both versions.
- **US-F011-3**: As an operator, I want exactly one inline keyboard with three actions (approve / decline / edit) so the decision is one tap away.
- **US-F011-4**: As a developer, I want a stable `ReviewSession` record per submission so that subsequent approval / decline / edit calls have a single ID to reference.

## User flow

```
F008.assemble succeeded  ─►  ReviewSubmitter.submit(render_job_id, reviewer_chat_id, channel_id)
   ├─► TelegramClient.send_video(
   │       chat_id=reviewer_chat_id,
   │       video=render_job.output_uri,
   │       caption=bilingual_caption(title_ru, content_ru, title_en, content_en),
   │       reply_markup=InlineKeyboard([
   │           ("✅ Approve / Одобрить",  "review:approve:{id}"),
   │           ("❌ Decline / Отклонить", "review:decline:{id}"),
   │           ("✏️ Edit / Править",      "review:edit:{id}"),
   │       ])
   │   ) → message_id M
   ├─► ReviewSessionRepo.save(ReviewSession{
   │       id, render_job_id, reviewer_chat_id, channel_id,
   │       status=PENDING_REVIEW, message_id=M,
   │   })
   └─► emit "reels.submitted_for_review"
```

## Requirements

| ID | Требование |
|---|---|
| REQ-F011-001 | `ReviewSubmitter.submit()` MUST принимать `render_job_id`, `reviewer_chat_id`, `channel_id` и возвращать персистентный `ReviewSession`. |
| REQ-F011-002 | Если `RenderJob` не найден или его `status != succeeded`, MUST падать `IllegalReviewStateError`, не отправляя сообщение в TG. |
| REQ-F011-003 | Caption MUST быть двуязычным: блок RU, разделитель пустой строкой, блок EN, разделитель пустой строкой, ссылка на источник. |
| REQ-F011-004 | Inline-клавиатура MUST содержать ровно 3 кнопки с callback_data `review:approve:{id}`, `review:decline:{id}`, `review:edit:{id}`. |
| REQ-F011-005 | Стартовое состояние `ReviewSession` MUST быть `PENDING_REVIEW`, поле `message_id` MUST быть сохранено. |
| REQ-F011-006 | Повторный `submit()` для уже отправленного `render_job_id` MUST вернуть существующий `ReviewSession` (идемпотентность). |

## BDD: docs/02-bdd/F011-review-submission.feature
