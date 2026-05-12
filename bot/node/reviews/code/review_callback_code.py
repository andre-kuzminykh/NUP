"""
ReviewCallbackCode — диспетчер действий approve/decline/edit.

## Трассируемость
Feature: F003 — Review callbacks
Scenarios: SC001 (approve), SC002 (decline), SC003 (edit), SC004 (malformed)
"""
from __future__ import annotations

from typing import Any

from service.api.reviews_api import BackendError, NotFoundError, ReviewsAPI


VALID_ACTIONS = {"approve", "decline", "edit"}


class ReviewCallbackCode:
    def __init__(self, api: ReviewsAPI | None = None) -> None:
        self._api = api or ReviewsAPI()

    async def run(self, trigger_data: dict, state: Any) -> dict:
        action = trigger_data.get("action")
        review_id = trigger_data.get("review_id")
        if action not in VALID_ACTIONS or not review_id:
            return {"answer_name": "review_invalid", "data": {}}

        try:
            if action == "approve":
                payload = await self._api.approve(review_id)
                return {"answer_name": "review_approved", "data": payload}
            if action == "decline":
                payload = await self._api.decline(review_id)
                return {"answer_name": "review_declined", "data": payload}
            # action == "edit" — переходим в edit-mode и сразу рисуем preview
            payload = await self._api.start_edit(review_id)
            return {"answer_name": "review_edit_preview", "data": payload}
        except NotFoundError:
            return {"answer_name": "review_invalid", "data": {}}
        except BackendError as e:
            return {"answer_name": "review_backend_error", "data": {"error": str(e)}}
