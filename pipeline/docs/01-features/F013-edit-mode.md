# F013 — Reels Edit Mode (Frame-by-frame)

Если оператор нажал **Edit / Править**, бот переходит в режим редактирования
кадров. По одному сегменту за раз: показывает текущий клип, навигация
стрелками `◀` / `▶` между сегментами, `🔄` обновить кандидатов,
`🖼 1/2/3` выбрать кандидата, `✅` сохранить и пересобрать видео,
`↩️ Cancel` выйти без изменений.

**Статус кода в этой итерации: спека + контрактные тесты. FSM-машина edit-mode будет реализована следующей итерацией.**

## User stories

- **US-F013-1**: As an operator, I want to navigate left/right between segments of the Reels so that I can audit them in order.
- **US-F013-2**: As an operator, for the current segment I want to see the active candidate (preview + 1-2 RU sentences description) and N alternative candidates with their previews.
- **US-F013-3**: As an operator, I want to pick a different candidate from a short list (1/2/3) so that I can swap an off-topic clip.
- **US-F013-4**: As an operator, I want to refresh the candidates (`🔄`) so that I get a new shortlist from Pexels without leaving edit mode.
- **US-F013-5**: As an operator, I want to press ✅ to commit my changes — backend re-renders the Reels and submits a **new** review session (looping back to F011).
- **US-F013-6**: As an operator, I want ↩️ Cancel so that I can leave edit mode without changes; the original review goes back to `PENDING_REVIEW`.

## Inline keyboard (per segment)

```
[◀] [1/N segments]  [▶]
[🖼 1] [🖼 2] [🖼 3]
[🔄 Refresh / Обновить]
[✅ Commit / Сохранить]   [↩️ Cancel / Отмена]
```

Все callback_data префиксованы как `edit:{review_id}:{action}[:{arg}]`.
Например: `edit:abc:prev`, `edit:abc:pick:2`, `edit:abc:refresh`, `edit:abc:commit`, `edit:abc:cancel`.

## State (server-side per review)

```
ReviewEditState {
  review_id:      uuid
  segments:       [SegmentEditState, ...]   # копия исходных
  cursor:         int                       # текущий индекс сегмента
}

SegmentEditState {
  active_candidate_idx:  int
  candidates:            [{video_url, preview_url, description_ru}, ...]
}
```

Хранится в БД (`reviews.edit_state` JSONB) либо в Redis (TTL 1 час) — на выбор реализации.

## Requirements

| ID | Требование |
|---|---|
| REQ-F013-001 | `ReviewEditor.start(review_id)` MUST: проверить `status == PENDING_REVIEW`, перевести в `IN_EDIT`, инициализировать `edit_state` по сегментам исходного Reels (active_candidate_idx=0, candidates из F07-cache). |
| REQ-F013-002 | `ReviewEditor.move(review_id, direction)` MUST менять cursor; на границах cursor MUST оставаться валидным (clamp 0..N-1). |
| REQ-F013-003 | `ReviewEditor.pick(review_id, candidate_idx)` MUST менять `active_candidate_idx` для текущего сегмента. |
| REQ-F013-004 | `ReviewEditor.refresh(review_id)` MUST вызвать F07 (Pexels + vision) для текущего сегмента и заменить `candidates`; cursor и active_candidate_idx NOT change. |
| REQ-F013-005 | `ReviewEditor.commit(review_id)` MUST: собрать новые сегменты из active candidates, создать новый `RenderJob` через F008, после успеха — новый `ReviewSession`. Старая сессия MUST остаться в `IN_EDIT` (журнал). |
| REQ-F013-006 | `ReviewEditor.cancel(review_id)` MUST перевести review обратно в `PENDING_REVIEW` и очистить `edit_state`. |
| REQ-F013-007 | Все ответы MUST содержать payload для бота, достаточный для отрисовки текущего экрана: `{cursor, total, segment_text, active_candidate, candidates[], buttons[]}`. |

## BDD: docs/02-bdd/F013-edit-mode.feature
