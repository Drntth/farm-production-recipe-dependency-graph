"""Parse level-gated limits that are not tied to a single location (field grants)."""

from __future__ import annotations

import re
from typing import Any

from src.scraper.wiki_client import WikiClient

LEVEL_PAGES_PREFIX = "Experience_Levels/"
_RANGE_RE = re.compile(r"Levels?\s+(\d+)\s*-\s*(\d+)")
_LEVEL_RE = re.compile(r"Level\s+(\d+)")
_FIELDS_RE = re.compile(r"(\d+)\s+fields\b", re.IGNORECASE)


def _level_pages(client: WikiClient, max_level: int) -> list[str]:
    """Titles of the 'Levels X-Y' sub-pages that cover levels 1..max_level."""
    pages: list[tuple[int, str]] = []
    for title in client.list_pages(LEVEL_PAGES_PREFIX):
        m = _RANGE_RE.search(title)
        if m and int(m.group(1)) <= max_level:
            pages.append((int(m.group(1)), title))
    return [title.replace(" ", "_") for _, title in sorted(pages)]


def parse_field_grants(client: WikiClient, max_level: int) -> list[dict[str, Any]]:
    """
    Return ``[{"level": 1, "count": 6}, {"level": 3, "count": 3}, …]``.

    Source: the "Items" column of the Experience Levels sub-pages, which
    lists e.g. "3 fields" for every level that grants new fields.
    """
    grants: dict[int, int] = {}
    for page in _level_pages(client, max_level):
        soup = client.get_page(page)
        table = soup.find("table")
        if table is None:
            continue
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            level_match = _LEVEL_RE.search(cells[0].get_text(" ", strip=True))
            if level_match is None:
                continue
            level = int(level_match.group(1))
            if level > max_level:
                continue
            fields = _FIELDS_RE.search(cells[1].get_text(" ", strip=True))
            if fields:
                grants[level] = int(fields.group(1))
    return [{"level": lv, "count": n} for lv, n in sorted(grants.items())]
