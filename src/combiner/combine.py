"""
Combiner (v0.9): the farm layout sized by the production plan.

The only place that joins the two planners:

1. The Production Planner solves the plan for the player profile (login
   interval, quantities, recommendations).
2. ``sizing_from_plan`` turns the plan into a layout ``Sizing``: recommended
   tree / bush counts, fields per crop with the locations that use each crop,
   and the goods flows between locations.
3. ``upcoming_unlocks`` looks ``lookahead`` levels ahead: more copies of
   placed buildings and more fields get reserved space in their blocks; new
   buildings are listed with the tiles they will need.
4. The Layout Planner places the sized blocks, by default in processing order
   (``strategy="flow"``: upstream blocks first, coupled blocks pulled together,
   the goods flows strengthening the pull). The design layer is added only
   when requested.
5. The result reports the goods flows between blocks with the tiles between
   their frames, and whether the free land covers the coming buildings.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace

from src.config import PlayerConfig
from src.layout import FarmMap, Layout, plan_layout
from src.layout.design import DEFAULT_DECOR_BAND
from src.layout.fields import apportion
from src.layout.packing import Rect
from src.layout.planner import DEFAULT_GAP, DEFAULT_RESERVE_RATIO
from src.layout.sizing import Sizing
from src.loaders.json_loader import DataSet
from src.models import Area, LocationType
from src.planner import PlanRun, ProductionPlan, run_planner
from src.settings import DEFAULT_COMBINER_STRATEGY as DEFAULT_STRATEGY
from src.settings import (
    DEFAULT_ITEM_GAP,
    DEFAULT_LOOKAHEAD,
    DEFAULT_MAIN_PATH_WIDTH,
    DEFAULT_MIN_EFFICIENCY,
    DEFAULT_PATH_STYLE,
    DEFAULT_PATH_TARGETS,
    DEFAULT_STORAGE_SHARE,
)

_EPS = 1e-6


@dataclass(frozen=True)
class FlowLink:
    source: str  # upstream block id
    target: str  # downstream block id
    per_hour: float  # goods per hour from source to target
    distance: int | None  # free tiles between the frames; None if one is not placed


@dataclass(frozen=True)
class Upcoming:
    location_id: str
    name: str
    unlock_level: int  # first level in the lookahead that adds it
    count: int  # copies (or fields) added up to the lookahead level
    tiles: int  # footprint area x count; 0 if the footprint is unknown
    kind: str  # "new" building, more "copies", more "fields"


@dataclass
class CombinedPlan:
    level: int
    lookahead: int
    dataset: DataSet  # filtered to the level
    run: PlanRun
    sizing: Sizing
    layout: Layout
    flow_links: list[FlowLink]
    upcoming: list[Upcoming]
    free_tiles: int | None  # usable tiles outside blocks and fixed items
    warnings: list[str] = field(default_factory=list)

    @property
    def new_building_tiles(self) -> int:
        return sum(u.tiles for u in self.upcoming if u.kind == "new")


def sizing_from_plan(plan: ProductionPlan, dataset: DataSet) -> Sizing:
    """Copies, fields per crop and goods flows of *plan*."""
    counts = {
        fp.location_id: math.ceil(fp.plants - _EPS)
        for fp in plan.fruits.values()
        if fp.plants_source == "recommended"
    }
    crop_fields = apportion(
        math.ceil(plan.fields_used - _EPS),
        {c: cp.fields for c, cp in plan.crops.items() if cp.fields > _EPS},
    )

    makers: dict[str, set[str]] = defaultdict(set)
    for rp in plan.recipes.values():
        if rp.per_hour > _EPS:
            makers[dataset.recipes[rp.recipe_id].output.resource_id].add(rp.location_id)
    for res in dataset.resource_list:
        if res.source_location_id:
            makers[res.id].add(res.source_location_id)
    # every block has its own fields: crops are no flow between blocks
    field_ids = {
        loc.id for loc in dataset.location_list if loc.type == LocationType.FIELD
    }

    crop_use: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    flows: dict[tuple[str, str], float] = defaultdict(float)
    for rp in plan.recipes.values():
        if rp.per_hour <= _EPS:
            continue
        for inp in dataset.recipes[rp.recipe_id].inputs:
            use = rp.per_hour * inp.amount
            if inp.resource_id in plan.crops:
                crop_use[inp.resource_id][rp.location_id] += use
            sources = makers.get(inp.resource_id, set()) - {rp.location_id} - field_ids
            for src in sources:
                flows[(src, rp.location_id)] += use / len(sources)
    return Sizing(
        counts=counts,
        crop_fields=crop_fields,
        crop_use={c: dict(u) for c, u in crop_use.items()},
        flows=dict(flows),
    )


def upcoming_unlocks(
    full: DataSet, level: int, lookahead: int
) -> tuple[dict[str, int], list[Upcoming]]:
    """
    Unlocks of the next *lookahead* levels in the unfiltered *full* data.

    Returns the extra copies to reserve per location already on the farm, and
    every upcoming unlock (new buildings, more copies, more fields).
    """
    extra: dict[str, int] = {}
    upcoming: list[Upcoming] = []
    if lookahead <= 0:
        return extra, upcoming
    target = level + lookahead
    limits = full.level_limits
    for loc in sorted(full.location_list, key=lambda l: (l.unlock_level, l.id)):
        if loc.area != Area.FARM or not loc.movable:
            continue
        unit = (loc.footprint_width or 0) * (loc.footprint_height or 0)
        if loc.type == LocationType.FIELD:
            if limits is None:
                continue
            n = limits.fields_at(target) - limits.fields_at(level)
            levels = [g.level for g in limits.field_grants if level < g.level <= target]
            if n > 0:
                extra[loc.id] = n
                upcoming.append(
                    Upcoming(loc.id, loc.name, min(levels), n, n * unit, "fields")
                )
            continue
        rows = (
            [i for i in limits.location_instances if i.location_id == loc.id]
            if limits is not None
            else []
        )
        if level < loc.unlock_level <= target:
            n = sum(1 for i in rows if i.unlock_level <= target) if rows else 1
            upcoming.append(
                Upcoming(loc.id, loc.name, loc.unlock_level, n, n * unit, "new")
            )
        elif loc.unlock_level <= level and rows:
            later = [i.unlock_level for i in rows if level < i.unlock_level <= target]
            if later:
                extra[loc.id] = len(later)
                upcoming.append(
                    Upcoming(
                        loc.id,
                        loc.name,
                        min(later),
                        len(later),
                        len(later) * unit,
                        "copies",
                    )
                )
    return extra, upcoming


def flow_links(layout: Layout, flows: dict[tuple[str, str], float]) -> list[FlowLink]:
    """Goods flows between blocks, heaviest first, with the tiles between them."""
    owner = {loc: pb.block.id for pb in layout.blocks for loc in pb.block.locations}
    frames = {pb.block.id: pb.frame for pb in layout.blocks}
    by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for (src, dst), amount in flows.items():
        a, b = owner.get(src), owner.get(dst)
        if a is not None and b is not None and a != b and amount > _EPS:
            by_pair[(a, b)] += amount
    links = [
        FlowLink(a, b, amount, _distance(frames.get(a), frames.get(b)))
        for (a, b), amount in by_pair.items()
    ]
    return sorted(links, key=lambda link: (-link.per_hour, link.source, link.target))


def free_tiles(layout: Layout) -> int | None:
    """Usable map tiles outside the block frames and the fixed items."""
    fm = layout.farm_map
    area = fm.usable_tiles(layout.design_zones)
    if area is None:
        if not fm.bounded:
            return None
        area = {(x, y) for x in range(fm.width) for y in range(fm.height)}
    taken = [pb.frame for pb in layout.blocks if pb.frame is not None]
    taken += [Rect(f.x, f.y, f.width, f.height) for f in fm.placed_fixed]
    used = {(r.x + i, r.y + j) for r in taken for i in range(r.w) for j in range(r.h)}
    return len(area - used)


def combine(
    full: DataSet,
    player: PlayerConfig,
    farm_map: FarmMap | None = None,
    *,
    lookahead: int = DEFAULT_LOOKAHEAD,
    login_interval: float | None = None,
    storage_share: float = DEFAULT_STORAGE_SHARE,
    min_efficiency: float = DEFAULT_MIN_EFFICIENCY,
    reserve_ratio: float = DEFAULT_RESERVE_RATIO,
    gap: int = DEFAULT_GAP,
    strategy: str = DEFAULT_STRATEGY,
    design: bool = False,
    decor_band: int = DEFAULT_DECOR_BAND,
    item_gap: int = DEFAULT_ITEM_GAP,
    path_style: str = DEFAULT_PATH_STYLE,
    path_targets: str = DEFAULT_PATH_TARGETS,
    design_zones: bool = True,
    main_path_style: str | None = None,
    main_path_width: int = DEFAULT_MAIN_PATH_WIDTH,
) -> CombinedPlan:
    """
    Plan production, then the farm layout sized by it.

    *full* is the unfiltered data set (the lookahead needs later unlocks).
    Raises ``RuntimeError`` when the production plan cannot be solved.
    """
    if lookahead < 0:
        raise ValueError("lookahead must not be negative")
    level = player.level
    data = full.filter_by_max_level(level)
    run = run_planner(
        player,
        data,
        login_interval=login_interval,
        storage_share=storage_share,
        min_efficiency=min_efficiency,
    )
    extra, upcoming = upcoming_unlocks(full, level, lookahead)
    sizing = replace(sizing_from_plan(run.chosen, data), extra_reserved=extra)
    layout = plan_layout(
        data,
        level=level,
        player=player,
        farm_map=farm_map,
        reserve_ratio=reserve_ratio,
        gap=gap,
        strategy=strategy,
        design=design,
        decor_band=decor_band,
        sizing=sizing,
        item_gap=item_gap,
        path_style=path_style,
        path_targets=path_targets,
        design_zones=design_zones,
        main_path_style=main_path_style,
        main_path_width=main_path_width,
    )
    result = CombinedPlan(
        level=level,
        lookahead=lookahead,
        dataset=data,
        run=run,
        sizing=sizing,
        layout=layout,
        flow_links=flow_links(layout, sizing.flows),
        upcoming=upcoming,
        free_tiles=free_tiles(layout),
        warnings=list(run.chosen.warnings),
    )
    if layout.unplaced_blocks:
        result.warnings.append(
            "Blocks that do not fit on the map: " + ", ".join(layout.unplaced_blocks)
        )
    need = result.new_building_tiles
    if result.free_tiles is not None and need > result.free_tiles:
        result.warnings.append(
            f"New buildings up to level {level + lookahead} need about {need} "
            f"tiles, but only {result.free_tiles} are free: unlock more land"
        )
    return result


def _distance(a: Rect | None, b: Rect | None) -> int | None:
    """Free tiles between two frames along the grid (0 = touching)."""
    if a is None or b is None:
        return None
    dx = max(0, b.x - (a.x + a.w), a.x - (b.x + b.w))
    dy = max(0, b.y - (a.y + a.h), a.y - (b.y + b.h))
    return dx + dy
