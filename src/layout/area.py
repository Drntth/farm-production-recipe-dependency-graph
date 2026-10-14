"""
Town and fishing lake layouts (``--area town | fishing_lake``).

These areas have no production, so no graph: the planner works from the
measured area map alone (``config/<area>_map.json``).

- Movable items (``movable: true``, e.g. the town's service buildings) keep
  their measured size and are rearranged around the fixed items, pulled
  towards the hub (the town hall), largest first.
- Fixed items stay where they are; on the fishing lake every building is
  fixed, so its layout only adds the design layer.
- The design layer (``design=True``) connects the hub and every item with
  paths and adds the decoration band, as on the farm.
"""

from __future__ import annotations

from src.models import Area

from .blocks import Block
from .design import DEFAULT_DECOR_BAND, plan_design
from .farm_map import FarmMap
from .packing import Box, Rect, oriented_units, pack
from .planner import Layout, PlacedBlock, PlacedItem

# where visitors arrive / the player starts on the area
AREA_HUBS: dict[Area, tuple[str, ...]] = {
    Area.TOWN: ("town_hall", "town_station"),
    Area.FISHING_LAKE: ("fishermans_hut",),
}
HUB_WEIGHT = 1.0


def plan_area_layout(
    area_map: FarmMap,
    *,
    level: int,
    gap: int = 1,
    design: bool = False,
    decor_band: int = DEFAULT_DECOR_BAND,
) -> Layout:
    """Arrange the movable items of a town / fishing lake map."""
    if area_map.area == Area.FARM:
        raise ValueError("Use plan_layout for the farm")
    if gap < 0:
        raise ValueError("gap must not be negative")
    if design:
        gap = max(gap, 1)
    hubs = AREA_HUBS.get(area_map.area, ())
    fixed = {f.id: Rect(f.x, f.y, f.width, f.height) for f in area_map.placed_fixed}
    movable = area_map.placed_movable
    boxes = [Box(f.id, f.width, f.height, False) for f in movable]
    hub = next((h for h in hubs if h in fixed), None)
    weights = {tuple(sorted((f.id, hub))): HUB_WEIGHT for f in movable} if hub else {}
    placements, _ = pack(
        boxes,
        weights,
        gap=gap,
        obstacles=fixed,
        bounds=(area_map.width, area_map.height) if area_map.bounded else None,
        area=area_map.usable_tiles(),
        order="size",
    )

    blocks: list[PlacedBlock] = []
    for f, box in zip(movable, boxes):
        block = Block(f.id, f.label, f.id, [f.id])
        p = placements.get(f.id)
        if p is None:
            blocks.append(PlacedBlock(block, None))
            continue
        frame = oriented_units(box, p)[0]
        item = PlacedItem(f.id, f.label, f.id, frame)
        blocks.append(PlacedBlock(block, frame, [item]))

    layout = Layout(
        level=level,
        farm_map=area_map,
        blocks=blocks,
        stock=[],
        flow_order=[],
        neighbourhoods=[],
        support=[],
        fixed_unplaced=sorted(
            f.id for f in area_map.fixed if not f.is_placed and not f.movable
        ),
        missing_footprint=sorted(
            f.id for f in area_map.fixed if not f.is_placed and f.movable
        ),
        reserve_ratio=0.0,
        strategy="size",
    )
    if design:
        allowed = area_map.usable_tiles()
        if allowed is None:
            e = layout.extent()
            allowed = {
                (x, y)
                for x in range(e.x - 1, e.x + e.w + 1)
                for y in range(e.y - 1, e.y + e.h + 1)
            }
        placed = {b.block.id: b.frame for b in blocks if b.frame is not None}
        layout.design = plan_design(
            allowed, placed, fixed, decor_band, hubs=hubs, keys=set(fixed)
        )
    return layout
