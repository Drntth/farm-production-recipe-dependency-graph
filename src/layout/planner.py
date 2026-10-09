"""
Farm layout planning (v0.6): named blocks with footprints, placed on the grid.

Steps:

1. Detect named blocks from the production graph (``blocks.py``).
2. Count the copies of every location (``inventory.py``) and share the
   fields out among the blocks by crop demand (``fields.py``).
3. Pack each block's items: buildings one by one, fields / trees / bushes as
   patches; reserved copies take space but are marked as reserved.
4. Grow each block frame by ``reserve_ratio`` free area for later unlocks.
5. Pack the block frames on the farm map around the fixed buildings, with a
   ``gap`` of free tiles between blocks; when plots are marked unlocked in the
   farm map, only on unlocked plots. The ``strategy`` sets the order of the
   blocks: ``coupling`` (strongest neighbours first, related blocks end up
   close), ``size`` (largest first, fills an irregular area better) or
   ``auto`` (coupling, then size if a block does not fit). If a block still
   does not fit, steps 4-5 are repeated with a smaller reserve
   (``RESERVE_STEP``) down to 0.

No production data is used: block sizes come from the profile and the level.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field, replace

import networkx as nx

from src.config import PlayerConfig
from src.graph import build_graph
from src.loaders.json_loader import DataSet
from src.models import Area, LocationType

from .blocks import (
    Block,
    block_coupling,
    block_flow_order,
    detect_named_blocks,
    direct_coupling,
)
from .farm_map import FarmMap
from .fields import SHARED_BLOCK_ID, FieldShare, allocate_fields
from .inventory import Stock, farm_stock
from .packing import Box, Rect, bounding_rect, oriented_units, pack, patch
from .support import SupportRelation, active_relations

logger = logging.getLogger(__name__)

DEFAULT_RESERVE_RATIO = 0.2
RESERVE_STEP = 0.01
STRATEGIES = ("auto", "coupling", "size")
DEFAULT_GAP = 1
DEFAULT_FIELD_POOL = 0.0
COPY_WEIGHT = 1.0  # keeps copies of the same building together

_PATCH_TYPES = {LocationType.FIELD, LocationType.TREE, LocationType.BUSH}


@dataclass
class PlacedItem:
    location_id: str
    name: str
    block_id: str
    rect: Rect
    rotated: bool = False
    reserved: bool = False
    in_patch: bool = False  # one unit of a field / tree / bush patch


@dataclass
class PlacedBlock:
    block: Block
    frame: Rect | None  # None if the block did not fit on the map
    items: list[PlacedItem] = field(default_factory=list)  # empty if frame is None
    fields: FieldShare | None = None  # the block's dedicated fields

    @property
    def used_tiles(self) -> int:
        return sum(i.rect.w * i.rect.h for i in self.items if not i.reserved)

    @property
    def reserved_tiles(self) -> int:
        return sum(i.rect.w * i.rect.h for i in self.items if i.reserved)


@dataclass
class Neighbourhood:
    a: str
    b: str
    weight: float
    reason: str


@dataclass
class Layout:
    level: int
    farm_map: FarmMap
    blocks: list[PlacedBlock]
    stock: list[Stock]
    flow_order: list[str]
    neighbourhoods: list[Neighbourhood]
    support: list[SupportRelation]
    fixed_unplaced: list[str]  # fixed farm locations / map items without a position
    missing_footprint: list[str]
    reserve_ratio: (
        float  # used; lower than requested when the blocks did not fit otherwise
    )
    crop_names: dict[str, str] = field(default_factory=dict)
    reserve_requested: float | None = None
    strategy: str = "coupling"  # the block order actually used

    @property
    def unplaced_blocks(self) -> list[str]:
        return [b.block.id for b in self.blocks if b.frame is None]

    def extent(self) -> Rect:
        """Drawn area: the map, or the bounding box of everything placed."""
        if self.farm_map.bounded:
            return Rect(0, 0, self.farm_map.width, self.farm_map.height)
        rects = [b.frame for b in self.blocks if b.frame is not None]
        rects += [Rect(f.x, f.y, f.width, f.height) for f in self.farm_map.placed_fixed]
        return bounding_rect(rects) if rects else Rect(0, 0, 1, 1)


def plan_layout(
    dataset: DataSet,
    *,
    level: int,
    player: PlayerConfig | None = None,
    farm_map: FarmMap | None = None,
    reserve_ratio: float = DEFAULT_RESERVE_RATIO,
    gap: int = DEFAULT_GAP,
    field_pool: float = DEFAULT_FIELD_POOL,
    graph: nx.DiGraph | None = None,
    strategy: str = "auto",
) -> Layout:
    """Plan the farm layout for the level-filtered *dataset*."""
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy {strategy!r}; use one of {', '.join(STRATEGIES)}"
        )
    if reserve_ratio < 0 or gap < 0:
        raise ValueError("reserve_ratio and gap must not be negative")
    orders = ("coupling", "size") if strategy == "auto" else (strategy,)
    farm_map = farm_map or FarmMap()
    G = graph if graph is not None else build_graph(dataset)
    stock = {s.location.id: s for s in farm_stock(dataset, player, level)}

    # a movable location placed on the map by hand (e.g. the barn) stays there as
    # fixed: that copy leaves the stock, the other copies are still planned
    pinned_out: set[str] = set()
    for f in farm_map.placed_fixed:
        s = stock.get(f.id)
        if s is None:
            continue
        if s.count + s.reserved <= 1:
            pinned_out.add(f.id)
        elif s.count > 0:
            stock[f.id] = replace(s, count=s.count - 1)
        else:
            stock[f.id] = replace(s, reserved=s.reserved - 1)
    blocks = [
        Block(b.id, b.name, b.anchor, [x for x in b.locations if x not in pinned_out])
        for b in detect_named_blocks(G)
    ]
    blocks = [b for b in blocks if b.locations]

    farm_ids = {
        n
        for n, d in G.nodes(data=True)
        if d.get("kind") == "location" and d.get("area") == Area.FARM.value
    }
    P = direct_coupling(G, farm_ids)

    # fields: a dedicated share per block, optionally a shared pool block
    field_stock = next(
        (s for s in stock.values() if s.location.type == LocationType.FIELD), None
    )
    shares: dict[str, FieldShare] = {}
    if field_stock is not None:
        for share in allocate_fields(
            G, blocks, field_stock.count, field_stock.reserved, pool_ratio=field_pool
        ):
            shares[share.block_id] = share
        if SHARED_BLOCK_ID in shares:
            fid = field_stock.location.id
            blocks.append(Block(SHARED_BLOCK_ID, "Shared fields block", fid, [fid]))
    crop_names = {
        c: G.nodes[c].get("name", c) for share in shares.values() for c in share.crops
    }

    missing = sorted(
        {
            loc_id
            for b in blocks
            for loc_id in b.locations
            if loc_id in stock and stock[loc_id].location.footprint_width is None
        }
        | (
            {field_stock.location.id}
            if shares and field_stock.location.footprint_width is None
            else set()
        )
    )
    for loc_id in missing:
        logger.warning(
            "No footprint for %s; add it to data/overrides/locations.json", loc_id
        )

    # 3. blocks with their items, relative to the block origin
    block_items: dict[str, list[PlacedItem]] = {}
    for b in blocks:
        items = _pack_block(b, stock, P, shares.get(b.id), field_stock, crop_names)
        if items:
            block_items[b.id] = items

    def frames(ratio: float) -> list[Box]:
        """4. Block frames grown by *ratio* free area."""
        boxes = []
        for b in blocks:
            items = block_items.get(b.id)
            if not items:
                continue
            inner = bounding_rect([i.rect for i in items])
            frame = Rect(0, 0, *_grow(inner.w, inner.h, ratio))
            rotatable = all(
                i.rect.w == i.rect.h or stock[i.location_id].location.rotatable
                for i in items
            )
            boxes.append(
                Box(
                    b.id, frame.w, frame.h, rotatable, [frame] + [i.rect for i in items]
                )
            )
        return boxes

    # 5. blocks on the farm map
    fixed_rects = {
        f.id: Rect(f.x, f.y, f.width, f.height) for f in farm_map.placed_fixed
    }
    weights: dict[tuple[str, str], float] = dict(block_coupling(P, blocks))
    owner = {loc: b.id for b in blocks for loc in b.locations}
    for fixed_id in fixed_rects:
        if fixed_id not in P:
            continue
        for nb in P.neighbors(fixed_id):
            if nb in owner:
                key = tuple(sorted((fixed_id, owner[nb])))
                weights[key] = weights.get(key, 0.0) + P[fixed_id][nb]["weight"]
    bounds = (farm_map.width, farm_map.height) if farm_map.bounded else None
    area = farm_map.usable_tiles()
    requested = reserve_ratio
    while True:
        block_boxes = frames(reserve_ratio)
        for order in orders:
            placements, _ = pack(
                block_boxes,
                weights,
                gap=gap,
                obstacles=fixed_rects,
                bounds=bounds,
                area=area,
                order=order,
            )
            if len(placements) == len(block_boxes):
                break
        if len(placements) == len(block_boxes) or reserve_ratio <= 0:
            break
        # shrink the reserve until every block fits
        reserve_ratio = max(0.0, round(reserve_ratio - RESERVE_STEP, 4))
    if reserve_ratio < requested:
        logger.info(
            "Reserve lowered from %.0f%% to %.0f%% so that the blocks fit",
            requested * 100,
            reserve_ratio * 100,
        )

    placed_blocks: list[PlacedBlock] = []
    for box in block_boxes:
        b = next(x for x in blocks if x.id == box.key)
        p = placements.get(box.key)
        if p is None:
            logger.warning("Block %s does not fit on the farm map", b.id)
            # no items: their block-relative rects would look like map positions
            placed_blocks.append(PlacedBlock(b, None, [], shares.get(b.id)))
            continue
        frame, *units = oriented_units(box, p)
        items = [
            PlacedItem(
                i.location_id,
                i.name,
                b.id,
                u,
                i.rotated != p.rotated,
                i.reserved,
                i.in_patch,
            )
            for i, u in zip(block_items[b.id], units)
        ]
        placed_blocks.append(PlacedBlock(b, frame, items, shares.get(b.id)))

    if not farm_map.bounded and not fixed_rects:
        _shift_to_origin(placed_blocks)

    fixed_unplaced = sorted(
        {f.id for f in farm_map.fixed if not f.is_placed and f.id not in stock}
        | {
            loc.id
            for loc in dataset.location_list
            if loc.area == Area.FARM and not loc.movable and loc.id not in fixed_rects
        }
    )
    return Layout(
        level=level,
        farm_map=farm_map,
        blocks=placed_blocks,
        stock=list(stock.values()),
        flow_order=[i for i in block_flow_order(G, blocks) if i in block_items],
        neighbourhoods=_neighbourhoods(
            P, blocks, weights, set(fixed_rects) | set(fixed_unplaced)
        ),
        support=active_relations(farm_ids),
        fixed_unplaced=fixed_unplaced,
        missing_footprint=missing,
        reserve_ratio=reserve_ratio,
        crop_names=crop_names,
        reserve_requested=requested,
        strategy=order,
    )


def _grow(w: int, h: int, ratio: float) -> tuple[int, int]:
    """
    Smallest frame (w' >= w, h' >= h) with at least ``ratio`` extra area.

    Growing both sides by sqrt(1 + ratio) and rounding up would turn a 5 %
    reserve into +50 % on a 2-tile wide block; here the extra tiles may go to
    one side only. Ties prefer the more square frame.
    """
    target = w * h * (1 + ratio) - 1e-9
    best: tuple[int, int, int, int] | None = None
    for fw in range(w, math.ceil(w * (1 + ratio)) + 1):
        fh = max(h, math.ceil(target / fw))
        cand = (fw * fh, abs(fw - fh), fw, fh)
        if best is None or cand < best:
            best = cand
    return best[2], best[3]


def _pack_block(
    block: Block,
    stock: dict[str, Stock],
    P: nx.Graph,
    share: FieldShare | None,
    field_stock: Stock | None,
    crop_names: dict[str, str],
) -> list[PlacedItem]:
    """Pack the items of one block; returns items relative to the block origin."""
    boxes: list[Box] = []
    meta: dict[str, tuple[str, bool]] = {}  # box key -> (location id, reserved)
    reserved_units: dict[str, int] = {}
    names: dict[str, str] = {}
    if share is not None and field_stock.location.footprint_width is not None:
        f = field_stock.location
        boxes.append(
            patch(
                f.id,
                f.footprint_width,
                f.footprint_height,
                share.count + share.reserved,
                False,
            )
        )
        meta[f.id] = (f.id, False)
        reserved_units[f.id] = share.reserved
        crops = ", ".join(crop_names[c] for c in share.crops[:2]) or "shared"
        names[f.id] = f"{f.name} ({crops})"
    for loc_id in block.locations:
        s = stock.get(loc_id)
        if s is None or s.location.footprint_width is None:
            continue
        if s.location.type == LocationType.FIELD:
            continue
        loc = s.location
        w, h = loc.footprint_width, loc.footprint_height
        if loc.type in _PATCH_TYPES and s.count + s.reserved > 1:
            boxes.append(patch(loc_id, w, h, s.count + s.reserved, loc.rotatable))
            meta[loc_id] = (loc_id, False)
            reserved_units[loc_id] = s.reserved
            continue
        for i in range(s.count + s.reserved):
            key = f"{loc_id}#{i + 1}"
            boxes.append(Box(key, w, h, loc.rotatable))
            meta[key] = (loc_id, i >= s.count)

    weights: dict[tuple[str, str], float] = defaultdict(float)
    for a in boxes:
        for b in boxes:
            if a.key >= b.key:
                continue
            la, lb = meta[a.key][0], meta[b.key][0]
            if la == lb:
                weights[(a.key, b.key)] += COPY_WEIGHT
            elif P.has_edge(la, lb):
                weights[(a.key, b.key)] += P[la][lb]["weight"]
    placements, _ = pack(boxes, weights)

    items: list[PlacedItem] = []
    by_key = {b.key: b for b in boxes}
    for key, p in placements.items():
        loc_id, reserved = meta[key]
        name = names.get(key, stock[loc_id].location.name)
        units = oriented_units(by_key[key], p)
        n_reserved = reserved_units.get(key, 0)
        for idx, u in enumerate(units):
            is_reserved = reserved or idx >= len(units) - n_reserved
            items.append(
                PlacedItem(
                    loc_id,
                    name,
                    block.id,
                    u,
                    p.rotated,
                    is_reserved,
                    key in reserved_units,
                )
            )
    if items:
        origin = bounding_rect([i.rect for i in items])
        for i in items:
            i.rect = Rect(i.rect.x - origin.x, i.rect.y - origin.y, i.rect.w, i.rect.h)
    return items


def _shift_to_origin(blocks: list[PlacedBlock]) -> None:
    frames = [b.frame for b in blocks if b.frame is not None]
    if not frames:
        return
    o = bounding_rect(frames)
    for b in blocks:
        if b.frame is not None:
            b.frame = Rect(b.frame.x - o.x, b.frame.y - o.y, b.frame.w, b.frame.h)
        for i in b.items:
            i.rect = Rect(i.rect.x - o.x, i.rect.y - o.y, i.rect.w, i.rect.h)


def _neighbourhoods(
    P: nx.Graph,
    blocks: list[Block],
    weights: dict[tuple[str, str], float],
    fixed_ids: set[str],
    top_n: int = 10,
) -> list[Neighbourhood]:
    """Strongest block pairs, plus every block coupled to a fixed building."""
    block_ids = {b.id for b in blocks}
    result = [
        Neighbourhood(a, b, w, "shared goods")
        for (a, b), w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
        if a in block_ids and b in block_ids
    ][:top_n]
    owner = {loc: b.id for b in blocks for loc in b.locations}
    for fixed_id in sorted(fixed_ids):
        if fixed_id not in P:
            continue
        coupled: dict[str, float] = defaultdict(float)
        for nb in P.neighbors(fixed_id):
            if nb in owner:
                coupled[owner[nb]] += P[fixed_id][nb]["weight"]
        for block_id, w in sorted(coupled.items(), key=lambda kv: -kv[1]):
            result.append(Neighbourhood(block_id, fixed_id, w, "fixed building"))
    return result
