"""
Capacity model of the farm: what the player can store and produce at once.

Built from the resolved profile, so it needs no layout. Game rules used
(docs/game-facts/):

- a machine produces one item at a time; its slots only queue items, so
  copies run in parallel and slots decide how long it runs unattended;
- every animal produces on its own, so a shelter type runs ``animals`` items
  in parallel; lobster pool and duck salon run one animal per slot;
- one planted crop gives two harvested ones (wiki: Crops), so a planting
  adds one crop net;
- a tree / bush gives ``lifetime_yield`` goods over ``lifetime_harvests``
  harvests, one harvest per growth time (the average of the estimate in
  docs/wiki-gaps.md);
- every beehive makes one honeycomb per growth time of honeycomb (estimate
  in docs/wiki-gaps.md).

Rates are upper bounds: items per hour if the location made only that
recipe, with someone always online. ``src.planner.quantities`` shares the
time and applies the login interval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from src.loaders.json_loader import DataSet
from src.models import Location, LocationType, ResourceType

from .mastery import MasteryModifier
from .profile import BEEHIVE_TREE, ResolvedProfile

CROP_YIELD = 2  # harvested crops per planted crop (wiki: Crops)
SECONDS_PER_HOUR = 3600


class LineKind(str, Enum):
    MACHINE = "machine"  # copies in parallel, slots as queue
    ANIMAL = "animal"  # animals in parallel
    SLOT_ANIMAL = "slot_animal"  # lobster pool, duck salon: one animal per slot
    BEEHIVE = "beehive"  # beehives on the beehive tree
    TREE = "tree"
    BUSH = "bush"
    OTHER = "other"  # mine, fishing lake


@dataclass(frozen=True)
class LocationCapacity:
    location_id: str
    kind: LineKind
    parallel: int | None  # items produced at the same time; None = unknown
    queue: int | None  # machine slots, summed over copies


@dataclass(frozen=True)
class RecipeRate:
    recipe_id: str
    location_id: str
    time_seconds: int | None  # after the mastery modifier
    max_per_hour: float | None  # if the location made only this recipe


@dataclass(frozen=True)
class CropRate:
    resource_id: str
    growth_time_seconds: int
    net_per_field_per_hour: float  # planted crop subtracted


@dataclass(frozen=True)
class FruitRate:
    """Goods of one tree / bush kind; yield None = not known (no source)."""

    resource_id: str
    location_id: str
    harvest_interval_seconds: int
    yield_per_harvest: float | None  # lifetime average
    per_plant_per_hour: float | None


@dataclass(frozen=True)
class HiveRate:
    """Goods the beehives make without a recipe (honeycomb)."""

    resource_id: str
    location_id: str
    cycle_seconds: int
    parallel: int | None  # beehives


@dataclass(frozen=True)
class CapacityModel:
    level: int
    barn_capacity: int | None
    silo_capacity: int | None
    fields: int | None
    fields_source: str  # "profile" or "level" (all granted fields)
    locations: dict[str, LocationCapacity]
    recipes: dict[str, RecipeRate]
    crops: dict[str, CropRate]
    fruits: dict[str, FruitRate]
    hives: dict[str, HiveRate]

    def to_dict(self) -> dict:
        data = asdict(self)
        for loc in data["locations"].values():
            loc["kind"] = loc["kind"].value
        return data


def _kind(loc: Location) -> LineKind:
    if loc.id == BEEHIVE_TREE:
        return LineKind.BEEHIVE
    if loc.type == LocationType.PRODUCTION:
        return LineKind.MACHINE
    if loc.type == LocationType.ANIMAL:
        return LineKind.ANIMAL if loc.animal_capacity else LineKind.SLOT_ANIMAL
    if loc.type == LocationType.TREE:
        return LineKind.TREE
    if loc.type == LocationType.BUSH:
        return LineKind.BUSH
    return LineKind.OTHER


def build_capacity(
    profile: ResolvedProfile, dataset: DataSet, modifier: MasteryModifier
) -> CapacityModel:
    """Capacity of every profiled location, recipe and crop in *dataset*."""
    locations: dict[str, LocationCapacity] = {}
    for loc_id, state in profile.locations.items():
        kind = _kind(dataset.locations[loc_id])
        parallel = {
            LineKind.MACHINE: state.owned,
            LineKind.ANIMAL: state.animals,
            LineKind.SLOT_ANIMAL: state.slots,
            LineKind.BEEHIVE: state.beehives,
        }.get(kind, state.owned)
        queue = state.slots if kind == LineKind.MACHINE else None
        locations[loc_id] = LocationCapacity(loc_id, kind, parallel, queue)

    recipes: dict[str, RecipeRate] = {}
    for rec in sorted(dataset.recipe_list, key=lambda r: r.id):
        cap = locations.get(rec.location_id)
        time = modifier.production_time(rec, profile.locations.get(rec.location_id))
        rate = None
        if cap is not None and cap.parallel and time:
            rate = cap.parallel * rec.output.amount * SECONDS_PER_HOUR / time
        recipes[rec.id] = RecipeRate(rec.id, rec.location_id, time, rate)

    crops: dict[str, CropRate] = {}
    fruits: dict[str, FruitRate] = {}
    for res in sorted(dataset.resource_list, key=lambda r: r.id):
        source = dataset.locations.get(res.source_location_id or "")
        if res.type != ResourceType.CROP or source is None:
            continue
        growth = res.growth_time_seconds
        if not growth:
            continue
        if source.type == LocationType.FIELD:
            crops[res.id] = CropRate(
                res.id, growth, (CROP_YIELD - 1) * SECONDS_PER_HOUR / growth
            )
        elif source.type in (LocationType.TREE, LocationType.BUSH):
            per_harvest = (
                source.lifetime_yield / source.lifetime_harvests
                if source.lifetime_yield and source.lifetime_harvests
                else None
            )
            per_hour = per_harvest * SECONDS_PER_HOUR / growth if per_harvest else None
            fruits[res.id] = FruitRate(res.id, source.id, growth, per_harvest, per_hour)

    hives: dict[str, HiveRate] = {}
    for res in sorted(dataset.resource_list, key=lambda r: r.id):
        cap = locations.get(res.source_location_id or "")
        if cap is not None and cap.kind == LineKind.BEEHIVE and res.growth_time_seconds:
            hives[res.id] = HiveRate(
                res.id, cap.location_id, res.growth_time_seconds, cap.parallel
            )

    if profile.fields_owned is not None:
        fields, fields_source = profile.fields_owned, "profile"
    else:
        fields, fields_source = profile.fields_available, "level"

    return CapacityModel(
        level=profile.level,
        barn_capacity=profile.barn_capacity,
        silo_capacity=profile.silo_capacity,
        fields=fields,
        fields_source=fields_source,
        locations=locations,
        recipes=recipes,
        crops=crops,
        fruits=fruits,
        hives=hives,
    )
