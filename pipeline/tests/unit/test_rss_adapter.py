"""F001 — RSS adapter parses an RSS 2.0 feed into Article-like dicts.

Traces: REQ-F01-001, REQ-F01-007.
"""
import pytest

from nup_pipeline.infra.sources.rss import parse_rss


SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Guardian AI</title>
    <link>https://www.theguardian.com/technology/artificialintelligenceai</link>
    <description>AI news</description>
    <item>
      <title>OpenAI launches GPT-5</title>
      <link>https://www.theguardian.com/tech/gpt-5</link>
      <pubDate>Mon, 11 May 2026 14:00:00 GMT</pubDate>
      <description><![CDATA[OpenAI announced GPT-5 today.]]></description>
    </item>
    <item>
      <title>Anthropic raises money</title>
      <link>https://www.theguardian.com/tech/anthropic-funding</link>
      <pubDate>Mon, 11 May 2026 12:00:00 GMT</pubDate>
      <description>Funding round.</description>
    </item>
  </channel>
</rss>
"""


@pytest.mark.unit
@pytest.mark.req("REQ-F01-001")
def test_parses_basic_rss_items() -> None:
    items = parse_rss(SAMPLE_RSS)
    assert len(items) == 2
    first = items[0]
    assert first["title"] == "OpenAI launches GPT-5"
    assert first["link"] == "https://www.theguardian.com/tech/gpt-5"
    assert "GPT-5" in first["description"]
    assert first["pub_date"] == "Mon, 11 May 2026 14:00:00 GMT"


@pytest.mark.unit
@pytest.mark.req("REQ-F01-007")
def test_empty_feed_returns_empty_list() -> None:
    empty = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>x</title></channel></rss>"""
    assert parse_rss(empty) == []


@pytest.mark.unit
def test_invalid_xml_returns_empty_list() -> None:
    assert parse_rss(b"<not-xml") == []
