"""F001 — Atom feed parser (YouTube channels use Atom, not RSS 2.0).

Same parse_rss() entry point — should auto-detect format.

Traces: REQ-F01-001, REQ-F01-007.
"""
import pytest

from nup_pipeline.infra.sources.rss import parse_rss


YT_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id=UC123"/>
  <id>yt:channel:UC123</id>
  <yt:channelId>UC123</yt:channelId>
  <title>Lex Clips</title>
  <author><name>Lex Clips</name></author>
  <entry>
    <id>yt:video:abc123</id>
    <yt:videoId>abc123</yt:videoId>
    <title>Sam Altman on AGI timelines</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <author><name>Lex Clips</name></author>
    <published>2026-05-11T14:00:00+00:00</published>
    <updated>2026-05-11T14:00:00+00:00</updated>
    <media:group>
      <media:title>Sam Altman on AGI timelines</media:title>
      <media:description>A 15-minute clip about when AGI might arrive.</media:description>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:def456</id>
    <yt:videoId>def456</yt:videoId>
    <title>Yann LeCun on world models</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
    <published>2026-05-10T09:00:00+00:00</published>
    <media:group>
      <media:description>Why JEPA is a step beyond LLMs.</media:description>
    </media:group>
  </entry>
</feed>
"""


@pytest.mark.unit
@pytest.mark.req("REQ-F01-001")
def test_parse_youtube_atom_returns_entries() -> None:
    items = parse_rss(YT_ATOM)
    assert len(items) == 2
    first, second = items
    assert first["title"] == "Sam Altman on AGI timelines"
    assert first["link"] == "https://www.youtube.com/watch?v=abc123"
    assert "15-minute" in first["description"]
    assert first["pub_date"] == "2026-05-11T14:00:00+00:00"
    assert second["title"] == "Yann LeCun on world models"
    assert second["link"] == "https://www.youtube.com/watch?v=def456"


@pytest.mark.unit
def test_atom_without_media_group_falls_back_to_summary() -> None:
    atom = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Blog</title>
  <entry>
    <title>Post one</title>
    <link rel="alternate" href="https://example.com/post-1"/>
    <published>2026-05-11T00:00:00+00:00</published>
    <summary>Plain summary text here.</summary>
  </entry>
</feed>
"""
    items = parse_rss(atom)
    assert len(items) == 1
    assert items[0]["title"] == "Post one"
    assert items[0]["description"] == "Plain summary text here."


@pytest.mark.unit
def test_existing_rss_2_still_works() -> None:
    """Regression — adding Atom support must not break RSS 2.0."""
    rss = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>X</title>
<item><title>t</title><link>https://x/1</link><description>d</description></item>
</channel></rss>"""
    items = parse_rss(rss)
    assert len(items) == 1
    assert items[0]["title"] == "t"
    assert items[0]["link"] == "https://x/1"
