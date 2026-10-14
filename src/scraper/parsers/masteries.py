"""Parse production speed-ups per mastery star from the Masteries page."""

from __future__ import annotations

import re
from typing import Any

from src.scraper.normalizer import to_snake_case
from src.scraper.wiki_client import WikiClient

MASTERIES_PAGE = "Masteries"

# Each building row starts with a rowspan cell holding the building link.
_ROW_SPLIT_RE = re.compile(r'\n\|\s*rowspan="2"\s*\|')
_BUILDING_RE = re.compile(r"\[\[([^\]|#]+)")
# Bonus images: [[File:Feed Mill Mastery I.png|100px|5% faster]] (or 100x100px)
_BONUS_ALT_RE = re.compile(r"\[\[File:[^|\]]+\|[\dx]+px\|([^|\]]+)")
_FASTER_RE = re.compile(r"(\d+)\s*%\s*faster", re.IGNORECASE)
_STAR_COUNT = 3


def parse_mastery_wikitext(wikitext: str) -> list[dict[str, Any]]:
    """
    Return ``{location_id, stars, time_reduction_percent}`` rows.

    The table lists three bonus images per building, one per star; only
    "N% faster" bonuses are kept (coin and XP bonuses do not change times).
    """
    rows: list[dict[str, Any]] = []
    for block in _ROW_SPLIT_RE.split(wikitext)[1:]:
        building = _BUILDING_RE.search(block)
        if building is None:
            continue
        loc_id = to_snake_case(building.group(1))
        alts = _BONUS_ALT_RE.findall(block)[:_STAR_COUNT]
        for stars, alt in enumerate(alts, start=1):
            faster = _FASTER_RE.search(alt)
            if faster is not None:
                rows.append(
                    {
                        "location_id": loc_id,
                        "stars": stars,
                        "time_reduction_percent": int(faster.group(1)),
                    }
                )
    return rows


def parse_masteries(client: WikiClient) -> list[dict[str, Any]]:
    """Fetch the Masteries page and parse its speed-up bonuses."""
    return parse_mastery_wikitext(client.get_wikitext(MASTERIES_PAGE))
