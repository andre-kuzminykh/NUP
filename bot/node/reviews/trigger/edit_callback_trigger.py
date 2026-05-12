"""
EditCallbackTrigger — разбирает callback edit:{review_id}:{action}[:{arg}].

## Трассируемость
Feature: F003 — Review callbacks (edit mode)
Scenarios: SC003 (frame nav), SC004 (clip nav)
"""
from __future__ import annotations

from typing import Any


class EditCallbackTrigger:
    async def run(self, callback: Any, state: Any) -> dict:
        await callback.answer()  # ack spinner
        data = callback.data or ""
        parts = data.split(":")
        # edit:<review_id>:<action>[:arg]
        if len(parts) < 3 or parts[0] != "edit":
            return {"action": None, "review_id": None, "arg": None}
        review_id = parts[1]
        action = parts[2]
        arg = parts[3] if len(parts) >= 4 else None
        return {"action": action, "review_id": review_id, "arg": arg}
