"""Per-chat rate limiter (F003 BR001).

Pure in-memory tracker — for production replace with Redis-backed impl that
shares state across worker processes.

Tested by tests/unit/test_rate_limiter.py.
"""
from __future__ import annotations

import time
from typing import Callable


class InMemoryRateLimiter:
    def __init__(
        self,
        min_interval_sec: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min = float(min_interval_sec)
        self._clock = clock
        self._last: dict[str, float] = {}

    def seconds_to_wait(self, key: str) -> float:
        last = self._last.get(key)
        if last is None:
            return 0.0
        elapsed = self._clock() - last
        remaining = self._min - elapsed
        return max(0.0, remaining)

    def mark_sent(self, key: str) -> None:
        self._last[key] = self._clock()
