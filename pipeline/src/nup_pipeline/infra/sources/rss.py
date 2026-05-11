"""Minimal RSS 2.0 parser using stdlib xml.etree (no extra deps).

Tested by tests/unit/test_rss_adapter.py.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


def parse_rss(xml_bytes: bytes) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    channel = root.find("channel")
    if channel is None:
        return []
    out: list[dict] = []
    for item in channel.findall("item"):
        out.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "pub_date": (item.findtext("pubDate") or "").strip(),
            }
        )
    return out
