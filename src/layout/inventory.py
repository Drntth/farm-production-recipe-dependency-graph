"""
How many copies of each farm location the layout places.

Without production data the counts come from the player profile, then from
the level limits:

- fields: ``fields_owned``, else every field granted up to the level;
- other locations: ``owned``, else every copy unlocked at the level
  (``level_limits.json``), else 1 - a placeholder for trees and bushes, which
  the Combiner (v0.9) will size from production quantities.

Copies unlocked at the level but not owned yet are *reserved*: the layout
keeps their space free for later (expansion-friendly placement).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config import PlayerConfig
from src.loaders.json_loader import DataSet
from src.models import Area, Location, LocationType


class CountSource(str, Enum):
    PROFILE = "profile"  # the player profile gives the number
    LEVEL = "level"  # everything the level allows
    PLACEHOLDER = "placeholder"  # unknown; one copy shown, to be sized later
    SINGLE = "single"  # a single building without level limit rows


@dataclass(frozen=True)
class Stock:
    location: Location
    count: int
    reserved: int
    source: CountSource


_PLACEHOLDER_TYPES = {LocationType.TREE, LocationType.BUSH}


def farm_stock(
    dataset: DataSet, player: PlayerConfig | None, level: int
) -> list[Stock]:
    """Count every movable farm location of the (level-filtered) *dataset*."""
    limits = dataset.level_limits
    stocks: list[Stock] = []
    for loc in sorted(dataset.location_list, key=lambda l: (l.unlock_level, l.id)):
        if loc.area != Area.FARM or not loc.movable:
            continue
        progress = player.locations.get(loc.id) if player is not None else None
        owned = progress.owned if progress is not None else None

        if loc.type == LocationType.FIELD:
            available = limits.fields_at(level) if limits is not None else None
            owned = player.fields_owned if player is not None else None
        elif limits is not None and any(
            i.location_id == loc.id for i in limits.location_instances
        ):
            available = limits.instances_at(loc.id, level)
        else:
            available = None

        if owned is not None:
            reserved = max(available - owned, 0) if available is not None else 0
            stocks.append(Stock(loc, owned, reserved, CountSource.PROFILE))
        elif available is not None:
            stocks.append(Stock(loc, available, 0, CountSource.LEVEL))
        elif loc.type in _PLACEHOLDER_TYPES:
            stocks.append(Stock(loc, 1, 0, CountSource.PLACEHOLDER))
        else:
            stocks.append(Stock(loc, 1, 0, CountSource.SINGLE))
    return [s for s in stocks if s.count + s.reserved > 0]
