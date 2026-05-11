"""F001 / NFR-CC1 — ProxyPool basic rotation.

Traces: NFR-CC1-S01, NFR-CC1-S02.
"""
import pytest

from nup_pipeline.infra.proxies import ProxyPool


@pytest.mark.unit
@pytest.mark.req("NFR-CC1-S01")
def test_empty_pool_returns_none() -> None:
    pool = ProxyPool([])
    assert pool.acquire() is None


@pytest.mark.unit
@pytest.mark.req("NFR-CC1-S02")
def test_round_robin_cycles_through_proxies() -> None:
    pool = ProxyPool(["http://a", "http://b", "http://c"], strategy="round_robin")
    assert [pool.acquire() for _ in range(7)] == [
        "http://a", "http://b", "http://c",
        "http://a", "http://b", "http://c",
        "http://a",
    ]


@pytest.mark.unit
@pytest.mark.req("NFR-CC1-S02")
def test_least_used_picks_min() -> None:
    pool = ProxyPool(["http://a", "http://b"], strategy="least_used")
    a = pool.acquire(); pool.mark_used(a)
    b = pool.acquire(); pool.mark_used(b)
    a2 = pool.acquire(); pool.mark_used(a2)
    # After 1 use each, third pick goes to either; after another use, the
    # less-used one must be selected.
    counts = {"http://a": 0, "http://b": 0}
    counts[a] += 1; counts[b] += 1; counts[a2] += 1
    pick = pool.acquire()
    pool.mark_used(pick)
    counts[pick] += 1
    assert max(counts.values()) - min(counts.values()) <= 1
