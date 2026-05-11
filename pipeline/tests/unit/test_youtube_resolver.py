"""F001 — YouTube channel resolver.

Traces: REQ-F01-001 (YouTube source kind).
"""
import pytest

from nup_pipeline.infra.sources.youtube import (
    already_feed_url,
    resolve_feed_url,
)


class _StaticFetcher:
    def __init__(self, html: bytes) -> None:
        self.calls: list[str] = []
        self._html = html

    def get(self, url: str, *, proxy=None) -> bytes:
        self.calls.append(url)
        return self._html


@pytest.mark.unit
def test_already_feed_url_is_returned_as_is() -> None:
    feed = "https://www.youtube.com/feeds/videos.xml?channel_id=UCAAAAAAAAAAAAAAAAAAAAAA"
    assert already_feed_url(feed)
    # No fetcher needed.
    assert resolve_feed_url(feed) == feed


@pytest.mark.unit
def test_channel_url_with_explicit_uc_id_resolves_offline() -> None:
    url = "https://www.youtube.com/channel/UCAAAAAAAAAAAAAAAAAAAAAA"
    # No fetcher needed — UC-id is right there.
    assert (
        resolve_feed_url(url)
        == "https://www.youtube.com/feeds/videos.xml?channel_id=UCAAAAAAAAAAAAAAAAAAAAAA"
    )


@pytest.mark.unit
def test_handle_url_resolves_via_html_channel_id_marker() -> None:
    html = b'<html>...{"channelId":"UCabcDEF1234567890123456"}...</html>'
    fetcher = _StaticFetcher(html)
    out = resolve_feed_url("https://www.youtube.com/@nateherk", fetcher=fetcher)
    assert out == "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcDEF1234567890123456"
    assert fetcher.calls == ["https://www.youtube.com/@nateherk"]


@pytest.mark.unit
def test_handle_url_falls_back_to_canonical_link() -> None:
    html = (
        b'<html><head>'
        b'<link rel="canonical" href="https://www.youtube.com/channel/UCxyz9876543210987654321">'
        b'</head></html>'
    )
    out = resolve_feed_url("https://www.youtube.com/@somehandle", fetcher=_StaticFetcher(html))
    assert "UCxyz9876543210987654321" in out


@pytest.mark.unit
def test_handle_without_channel_id_raises() -> None:
    fetcher = _StaticFetcher(b"<html>no UC here, only AB123</html>")
    with pytest.raises(LookupError):
        resolve_feed_url("https://www.youtube.com/@nochannel", fetcher=fetcher)


@pytest.mark.unit
def test_resolve_without_fetcher_when_html_needed_raises() -> None:
    with pytest.raises(ValueError):
        resolve_feed_url("https://www.youtube.com/@h")
