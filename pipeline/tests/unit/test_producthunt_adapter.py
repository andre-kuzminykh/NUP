"""F001 — Product Hunt leaderboard adapter.

Traces: REQ-F01-001, REQ-F01-007.
"""
from datetime import datetime, timezone

import pytest

from nup_pipeline.infra.sources.producthunt import (
    parse_producthunt_leaderboard,
    yesterday_url,
)


@pytest.mark.unit
def test_yesterday_url_format() -> None:
    fixed = datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc)
    assert yesterday_url(now=fixed) == "https://www.producthunt.com/leaderboard/daily/2026/5/10"
    # Кросс-месяц.
    cross_month = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    assert yesterday_url(now=cross_month) == "https://www.producthunt.com/leaderboard/daily/2026/5/31"
    # Кросс-год.
    cross_year = datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert yesterday_url(now=cross_year) == "https://www.producthunt.com/leaderboard/daily/2026/12/31"


def _make_html(items_json: str) -> bytes:
    """Wrap items array in a fake SSR-state script tag, matching the page layout."""
    return (
        b'<html><body><script>'
        b'window.__APOLLO_STATE__ = {'
        b'"homefeed":{"items":' + items_json.encode() + b',"cursor":"x"}};'
        b'</script></body></html>'
    )


@pytest.mark.unit
@pytest.mark.req("REQ-F01-001")
def test_picks_post_with_daily_rank_1() -> None:
    items = (
        '['
        '{"__typename":"Post","dailyRank":"3","name":"Third place",'
        '"tagline":"meh","shortenedUrl":"/posts/third"},'
        '{"__typename":"Post","dailyRank":"1","name":"Winning Product",'
        '"tagline":"Best thing ever","shortenedUrl":"/posts/winning"},'
        '{"__typename":"Post","dailyRank":"2","name":"Runner Up",'
        '"tagline":"close","shortenedUrl":"/posts/runner"}'
        ']'
    )
    out = parse_producthunt_leaderboard(_make_html(items))
    assert len(out) == 1
    assert out[0]["title"] == "Winning Product"
    assert out[0]["link"] == "https://www.producthunt.com/posts/winning"
    assert out[0]["description"] == "Best thing ever"


@pytest.mark.unit
def test_falls_back_to_first_post_when_no_rank() -> None:
    items = (
        '['
        '{"__typename":"Topic","name":"Launching Today"},'
        '{"__typename":"Post","name":"Snapseed 4.0",'
        '"tagline":"Best photo editor","shortenedUrl":"/posts/snapseed-4-0"}'
        ']'
    )
    out = parse_producthunt_leaderboard(_make_html(items))
    assert len(out) == 1
    assert out[0]["title"] == "Snapseed 4.0"
    assert out[0]["link"].endswith("/posts/snapseed-4-0")


@pytest.mark.unit
def test_uses_product_slug_when_no_shortened_url() -> None:
    items = (
        '['
        '{"__typename":"Post","dailyRank":"1","name":"With Slug",'
        '"tagline":"x","product":{"slug":"with-slug"}}'
        ']'
    )
    out = parse_producthunt_leaderboard(_make_html(items))
    assert out[0]["link"] == "https://www.producthunt.com/products/with-slug"


@pytest.mark.unit
def test_no_posts_returns_empty() -> None:
    items = '[{"__typename":"Topic","name":"Launching Today"}]'
    out = parse_producthunt_leaderboard(_make_html(items))
    assert out == []


@pytest.mark.unit
def test_html_without_homefeed_returns_empty() -> None:
    assert parse_producthunt_leaderboard(b"<html>nothing here</html>") == []


@pytest.mark.unit
def test_malformed_json_returns_empty() -> None:
    payload = b'<script>window.x = {"homefeed":{"items":[{broken json}]}}</script>'
    assert parse_producthunt_leaderboard(payload) == []
