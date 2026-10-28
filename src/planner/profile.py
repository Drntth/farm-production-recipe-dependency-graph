"""
Player profile with every ``null`` resolved to its level default (option B).

The profile lists only what the player knows or what differs from the
defaults; everything else is derived from the level and the shared data
(see docs/player-profile.md):

- ``owned``: every copy unlocked at the level (``level_limits.json``), else
  1; trees and bushes stay unknown, the planner recommends them later;
- ``slots``: base slots per copy x copies, for locations with ``base_slots``;
- ``mastery_stars`` / ``workbench_level``: 0;
- ``animals``: copies x ``animal_capacity`` (full shelters); squirrel house 2;
- ``beehives``: 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import MasterySystem, PlayerConfig
from src.loaders.json_loader import DataSet
from src.models import LocationType

BEEHIVE_TREE = "beehive_tree"
DEFAULT_BEEHIVES = 1  # wiki: Beehive_Tree, one beehive at start
SQUIRREL_HOUSE = "squirrel_house"
DEFAULT_SQUIRRELS = 2  # wiki: Squirrel, room for two at first; the house grows

# Fields are counted globally (fields_owned); storage is barn / silo capacity.
_NOT_PROFILED = {LocationType.FIELD, LocationType.STORAGE}
_RECOMMENDED = {LocationType.TREE, LocationType.BUSH}


@dataclass(frozen=True)
class LocationState:
    """The player's resolved state of one location type (totals over copies)."""

    location_id: str
    owned: int | None  # None: not known yet (trees / bushes), to be recommended
    slots: int | None
    mastery_stars: int
    workbench_level: int
    animals: int | None
    beehives: int | None
    defaults: frozenset[str] = field(default_factory=frozenset)  # fields not given


@dataclass(frozen=True)
class ResolvedProfile:
    level: int
    mastery_system: MasterySystem
    barn_capacity: int | None
    silo_capacity: int | None
    fields_owned: int | None  # None: to be recommended
    fields_available: int | None  # granted up to the level
    fishing_spots_unlocked: int | None
    locations: dict[str, LocationState]

    def missing(self) -> list[str]:
        """Profile values that have no default and must come from the player."""
        names = ("barn_capacity", "silo_capacity")
        return [n for n in names if getattr(self, n) is None]


def _pick(
    values: dict[str, int | None], defaults: set[str], name: str, default: int | None
) -> int | None:
    """The profile value of *name*, else *default* (recorded in *defaults*)."""
    if values.get(name) is not None:
        return values[name]
    defaults.add(name)
    return default


def resolve_profile(player: PlayerConfig, dataset: DataSet) -> ResolvedProfile:
    """
    Fill every unknown value of *player* from the level and *dataset*.

    *dataset* should be filtered to the player level; profile entries for
    locations outside it are ignored (``validate_player_config`` reports them).
    """
    limits = dataset.level_limits
    level = player.level
    states: dict[str, LocationState] = {}
    for loc in sorted(dataset.location_list, key=lambda l: (l.unlock_level, l.id)):
        if loc.type in _NOT_PROFILED:
            continue
        given = player.locations.get(loc.id)
        values: dict[str, int | None] = given.model_dump() if given is not None else {}
        defaults: set[str] = set()

        has_rows = limits is not None and any(
            i.location_id == loc.id for i in limits.location_instances
        )
        if has_rows:
            owned_default = limits.instances_at(loc.id, level)
        elif loc.type in _RECOMMENDED:
            owned_default = None
        else:
            owned_default = 1
        owned = _pick(values, defaults, "owned", owned_default)

        slots_default = (
            loc.base_slots * owned
            if loc.base_slots is not None and owned is not None
            else None
        )
        animals_default = (
            loc.animal_capacity * owned
            if loc.animal_capacity is not None and owned is not None
            else None
        )
        if loc.id == SQUIRREL_HOUSE and owned:
            animals_default = DEFAULT_SQUIRRELS
        states[loc.id] = LocationState(
            location_id=loc.id,
            owned=owned,
            slots=_pick(values, defaults, "slots", slots_default),
            mastery_stars=_pick(values, defaults, "mastery_stars", 0),
            workbench_level=_pick(values, defaults, "workbench_level", 0),
            animals=_pick(values, defaults, "animals", animals_default),
            beehives=_pick(
                values,
                defaults,
                "beehives",
                DEFAULT_BEEHIVES if loc.id == BEEHIVE_TREE else None,
            ),
            defaults=frozenset(defaults),
        )

    return ResolvedProfile(
        level=level,
        mastery_system=player.mastery_system,
        barn_capacity=player.barn_capacity,
        silo_capacity=player.silo_capacity,
        fields_owned=player.fields_owned,
        fields_available=limits.fields_at(level) if limits is not None else None,
        fishing_spots_unlocked=player.fishing_spots_unlocked,
        locations=states,
    )
