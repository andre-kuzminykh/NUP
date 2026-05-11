"""Минимальный парсер фидов: RSS 2.0 и Atom (YouTube использует Atom).

Auto-detect by root element tag — `parse_rss()` остаётся единой точкой входа,
вызывается из IngestService безотносительно конкретного формата фида.

Tested by tests/unit/test_rss_adapter.py и tests/unit/test_atom_youtube.py.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

_NS_ATOM = "http://www.w3.org/2005/Atom"
_NS_MEDIA = "http://search.yahoo.com/mrss/"


def parse_rss(xml_bytes: bytes) -> list[dict]:
    """Парсит RSS 2.0 или Atom-фид в list[{title, link, description, pub_date}]."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    local = root.tag.split("}")[-1].lower()
    if local == "rss":
        channel = root.find("channel")
        return _parse_rss_items(channel) if channel is not None else []
    if local == "feed":
        return _parse_atom_entries(root)
    return []


def _parse_rss_items(channel: ET.Element) -> list[dict]:
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


def _parse_atom_entries(feed: ET.Element) -> list[dict]:
    out: list[dict] = []
    for entry in feed.findall(f"{{{_NS_ATOM}}}entry"):
        title_el = entry.find(f"{{{_NS_ATOM}}}title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        # rel="alternate" предпочтительно; иначе первый <link href=...>
        link = ""
        alt = entry.find(f"{{{_NS_ATOM}}}link[@rel='alternate']")
        if alt is not None:
            link = alt.get("href") or ""
        if not link:
            any_link = entry.find(f"{{{_NS_ATOM}}}link")
            if any_link is not None:
                link = any_link.get("href") or ""

        # description: media:description (YouTube) > atom:summary > atom:content
        desc = ""
        media_group = entry.find(f"{{{_NS_MEDIA}}}group")
        if media_group is not None:
            md = media_group.find(f"{{{_NS_MEDIA}}}description")
            if md is not None and md.text:
                desc = md.text.strip()
        if not desc:
            summary = entry.find(f"{{{_NS_ATOM}}}summary")
            if summary is not None and summary.text:
                desc = summary.text.strip()
        if not desc:
            content = entry.find(f"{{{_NS_ATOM}}}content")
            if content is not None and content.text:
                desc = content.text.strip()

        pub = (
            entry.findtext(f"{{{_NS_ATOM}}}published")
            or entry.findtext(f"{{{_NS_ATOM}}}updated")
            or ""
        ).strip()

        out.append({"title": title, "link": link.strip(), "description": desc, "pub_date": pub})
    return out
