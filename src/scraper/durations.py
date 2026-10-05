"""Parse wiki duration texts ("1 d 3 h", "2 h 30 min", "40 sec", "Instant") into seconds."""

from __future__ import annotations

import re

_UNIT_SECONDS = {"d": 86400, "h": 3600, "min": 60, "m": 60, "sec": 1, "s": 1}
_PART_RE = re.compile(r"(\d+)\s*(d|h|min|sec|m|s)\b", re.IGNORECASE)
_STAR_MARK = "★★★"


def parse_duration_seconds(text: str) -> int | None:
    """
    Return the duration in seconds, or None if *text* holds no duration.

    "Instant" (also "Instant or 20 h") is 0: the good needs no waiting.
    """
    text = text.strip()
    if text.lower().startswith("instant"):
        return 0
    parts = _PART_RE.findall(text)
    if not parts:
        return None
    return sum(int(n) * _UNIT_SECONDS[unit.lower()] for n, unit in parts)


def parse_timed_cell(text: str) -> tuple[int | None, int | None]:
    """
    Split a Goods List "Time" cell into (base, with full 3-star mastery).

    "30 min ★★★ 25 min" → (1800, 1500); "2 h" → (7200, None).
    """
    base, _, mastered = text.partition(_STAR_MARK)
    return parse_duration_seconds(base), (
        parse_duration_seconds(mastered) if mastered else None
    )
