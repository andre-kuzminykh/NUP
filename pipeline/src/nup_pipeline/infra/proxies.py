"""ProxyPool — простой пул прокси с тремя стратегиями выбора.

In-memory; для production-варианта (с health/cooldown) Redis-backed
реализация будет на этой же сигнатуре.

Tested by tests/unit/test_proxy_pool.py.
"""
from __future__ import annotations

import random


class ProxyPool:
    def __init__(self, proxies: list[str], *, strategy: str = "round_robin") -> None:
        if strategy not in {"round_robin", "random", "least_used"}:
            raise ValueError(f"unknown strategy: {strategy!r}")
        self._proxies = list(proxies)
        self._strategy = strategy
        self._idx = 0
        self._uses: dict[str, int] = {p: 0 for p in self._proxies}

    def acquire(self) -> str | None:
        if not self._proxies:
            return None
        if self._strategy == "round_robin":
            p = self._proxies[self._idx % len(self._proxies)]
            self._idx += 1
            return p
        if self._strategy == "random":
            return random.choice(self._proxies)
        # least_used: pick min-uses; stable on ties (first wins).
        return min(self._proxies, key=lambda x: self._uses.get(x, 0))

    def mark_used(self, proxy: str) -> None:
        if proxy in self._uses:
            self._uses[proxy] += 1
