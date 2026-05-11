"""F003 — RateLimiter contract.

Traces: REQ-F03-001 / BR001 (≥60 s between two posts to the same chat).
"""
from __future__ import annotations

import pytest

from nup_pipeline.infra.rate_limiter import InMemoryRateLimiter


class FakeClock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_first_call_returns_zero_wait() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    assert rl.seconds_to_wait("@d_media_ai") == 0


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_immediate_second_call_returns_full_interval() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    rl.mark_sent("@d_media_ai")
    assert rl.seconds_to_wait("@d_media_ai") == pytest.approx(60.0)


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_after_interval_returns_zero_wait() -> None:
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    rl.mark_sent("@d_media_ai")
    clk.advance(60.1)
    assert rl.seconds_to_wait("@d_media_ai") == 0


@pytest.mark.unit
@pytest.mark.req("REQ-F03-001")
def test_independent_chat_ids() -> None:
    """Spacing is per-chat — posting to channel A does not block channel B."""
    clk = FakeClock()
    rl = InMemoryRateLimiter(min_interval_sec=60, clock=clk)
    rl.mark_sent("@a")
    assert rl.seconds_to_wait("@b") == 0
    assert rl.seconds_to_wait("@a") > 0
