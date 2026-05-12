"""
EditCallbackCode — диспетчер действий edit-mode: move/pick/cancel + start.

## Трассируемость
Feature: F003 — Review callbacks (edit mode)

## Бизнес-контекст
Из trigger приходит {action: "frame_prev|frame_next|clip_prev|clip_next|save|cancel|refresh|approve|decline", review_id, arg}.
- frame_prev/next → backend /move {prev|next}
- clip_prev/next  → backend /pick {prev|next}
- refresh         → backend /refresh-candidates (новые 10 клипов на сегмент)
- save            → backend /cancel-edit (выйти из edit-mode, сохранив picks)
- cancel          → backend /cancel-edit-revert (выйти, откатив active_idx=0)
- approve         → backend /approve  (после выхода из edit-mode, из главного меню)
- decline         → backend /decline
"""
from __future__ import annotations

from typing import Any

from service.api.reviews_api import BackendError, NotFoundError, ReviewsAPI


class EditCallbackCode:
    def __init__(self, api: ReviewsAPI | None = None) -> None:
        self._api = api or ReviewsAPI()

    async def run(self, trigger_data: dict, state: Any) -> dict:
        action = trigger_data.get("action")
        review_id = trigger_data.get("review_id")
        if not (action and review_id):
            return {"answer_name": "review_invalid", "data": {}}

        try:
            if action == "frame_prev":
                payload = await self._api.move(review_id, "prev")
            elif action == "frame_next":
                payload = await self._api.move(review_id, "next")
            elif action == "clip_prev":
                payload = await self._api.pick(review_id, "prev")
            elif action == "clip_next":
                payload = await self._api.pick(review_id, "next")
            elif action == "save":
                # «💾 Сохранить» — пересобираем reel.mp4 из выбранных
                # candidates[active_idx], меняем видео в чате оператора,
                # выходим из IN_EDIT в PENDING_REVIEW.
                payload = await self._api.save_edit(review_id)
                return {"answer_name": "review_edit_cancelled", "data": payload}
            elif action == "cancel":
                # «↩️ Отмена» — выходим с полным откатом active_idx → 0.
                payload = await self._api.cancel_edit_revert(review_id)
                return {"answer_name": "review_edit_cancelled", "data": payload}
            elif action == "approve":
                # Legacy путь: оставлен на случай, если оператор тапнет
                # подвисший callback с предыдущей клавиатуры.
                payload = await self._api.approve(review_id)
                return {"answer_name": "review_approved", "data": payload}
            elif action == "decline":
                payload = await self._api.decline(review_id)
                return {"answer_name": "review_declined", "data": payload}
            elif action == "refresh":
                payload = await self._api.refresh_candidates(review_id)
            else:
                return {"answer_name": "review_invalid", "data": {}}
        except NotFoundError:
            return {"answer_name": "review_invalid", "data": {}}
        except BackendError as e:
            return {"answer_name": "review_backend_error", "data": {"error": str(e)}}

        return {"answer_name": "review_edit_preview", "data": payload}
