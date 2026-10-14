"""
Mastery modifiers: production time of a recipe for the player's mastery.

``mastery_system`` in the profile picks the modifier, so a new system
(Workbench, v1.72) can be added without touching the planner:

- ``stars`` (default): the scraped 3-star time at three stars, otherwise the
  base time reduced by the building's mastery bonus at that star level
  (``mastery_bonuses.json``; the feed mill, lure workbench and net maker
  already speed up at one and two stars);
- ``workbench``: no data yet, so the base time is used and a warning logged.
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.config import MasterySystem
from src.loaders.json_loader import DataSet
from src.models import MasteryBonus, Recipe

from .profile import LocationState

logger = logging.getLogger(__name__)

MAX_STARS = 3


class MasteryModifier(Protocol):
    def production_time(
        self, recipe: Recipe, state: LocationState | None
    ) -> int | None: ...


class StarsModifier:
    """Classic 3-star mastery."""

    def __init__(self, bonuses: list[MasteryBonus]) -> None:
        self._bonuses: dict[str, dict[int, int]] = {}
        for b in bonuses:
            self._bonuses.setdefault(b.location_id, {})[b.stars] = (
                b.time_reduction_percent
            )

    def reduction_percent(self, location_id: str, stars: int) -> int:
        """Total time reduction at *stars*; bonuses are totals, not increments."""
        by_star = self._bonuses.get(location_id, {})
        return max((p for s, p in by_star.items() if s <= stars), default=0)

    def production_time(
        self, recipe: Recipe, state: LocationState | None
    ) -> int | None:
        base = recipe.production_time_seconds
        stars = state.mastery_stars if state is not None else 0
        if stars >= MAX_STARS and recipe.production_time_3star_seconds is not None:
            return recipe.production_time_3star_seconds
        if base is None:
            return None
        percent = self.reduction_percent(recipe.location_id, stars)
        return round(base * (100 - percent) / 100)


class WorkbenchModifier:
    """Building Mastery / Workbench: placeholder until its bonuses are known."""

    def __init__(self) -> None:
        self._warned = False

    def production_time(
        self, recipe: Recipe, state: LocationState | None
    ) -> int | None:
        if not self._warned:
            logger.warning(
                "Workbench mastery has no data yet; using base production times"
            )
            self._warned = True
        return recipe.production_time_seconds


def mastery_modifier(system: MasterySystem, dataset: DataSet) -> MasteryModifier:
    if system == MasterySystem.WORKBENCH:
        return WorkbenchModifier()
    return StarsModifier(dataset.mastery_bonuses)
