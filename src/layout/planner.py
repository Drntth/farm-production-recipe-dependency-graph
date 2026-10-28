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
   ``auto`` (coupling, then size if a block does not fit) or ``flow``
   (upstream blocks first along the processing order; it lowers the reserve
   first and falls back to size only if a block does not fit even without
   reserve). If a block still does not fit, placing every block comes first:
   the ``item_gap`` between the buildings of a block is lowered first (at the
   requested reserve), then steps 4-5 are repeated with a smaller reserve
   (``RESERVE_STEP``) down to 0.
   A design template of a block (``templates.py``) is a wish too: when the
   blocks do not fit even with no item gap, the templates are dropped before
   the reserve is lowered.
6. Optional design layer (``design=True``, ``design.py``): paths between the
   blocks and the key fixed buildings, and a decoration band along them.

Without production data block sizes come from the profile and the level. The
Combiner passes a ``Sizing`` (``sizing.py``): copies, fields per crop and the
goods flows of a production plan replace those estimates.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace

import networkx as nx

from src.config import PlayerConfig
from src.graph import build_graph
from src.loaders.json_loader import DataSet
from src.models import Area, LocationType
from src.settings import (
    DEFAULT_FIELD_POOL,
    DEFAULT_GAP,
    DEFAULT_ITEM_GAP,
    DEFAULT_MAIN_PATH_WIDTH,
    DEFAULT_PATH_STYLE,
    DEFAULT_PATH_TARGETS,
)
from src.settings import DEFAULT_RESERVE as DEFAULT_RESERVE_RATIO

from .blocks import (
    Block,
    block_coupling,
    block_flow_order,
    detect_named_blocks,
    direct_coupling,
)
from .design import DEFAULT_DECOR_BAND, Design, plan_design
from .farm_map import FarmMap
from .fields import (
    SHARED_BLOCK_ID,
    FieldShare,
    allocate_fields,
    allocate_fields_by_use,
)
from .inventory import CountSource, Stock, farm_stock
from .packing import Box, Rect, bounding_rect, oriented_units, pack, patch
from .sizing import Sizing
from .support import SupportRelation, active_relations
from .templates import BlockTemplate

logger = logging.getLogger(__name__)

RESERVE_STEP = 0.01
STRATEGIES = ("auto", "coupling", "size", "flow")
_ORDERS = {"auto": ("coupling", "size"), "flow": ("flow", "size")}
COPY_WEIGHT = 1.0  # keeps copies of the same building together
_TEMPLATE_KEY = "template"  # box / obstacle key of a block's design template

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
class PlacedTemplate:
    """The design template of a block: its area and (arrange) its taken tiles."""

    name: str
    mode: str  # reserve: the whole area is kept free; arrange: buildings placed
    rect: Rect
    decorations: list[Rect] = field(default_factory=list)  # arrange mode only

    def moved(self, dx: int, dy: int) -> PlacedTemplate:
        def mv(r: Rect) -> Rect:
            return Rect(r.x + dx, r.y + dy, r.w, r.h)

        return replace(
            self, rect=mv(self.rect), decorations=[mv(d) for d in self.decorations]
        )

    @property
    def kept_tiles(self) -> int:
        """Tiles the template keeps free of buildings."""
        if self.mode == "reserve":
            return self.rect.w * self.rect.h
        return sum(r.w * r.h for r in self.decorations)


@dataclass
class PlacedBlock:
    block: Block
    frame: Rect | None  # None if the block did not fit on the map
    items: list[PlacedItem] = field(default_factory=list)  # empty if frame is None
    fields: FieldShare | None = None  # the block's dedicated fields
    template: PlacedTemplate | None = None

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
    design: Design | None = None  # paths and decoration band, if requested
    sized: bool = False  # block sizes from production quantities (Combiner)
    item_gap: int = 0  # free tiles between the buildings of a block (used)
    item_gap_requested: int = 0  # lowered when the blocks did not fit otherwise
    design_zones: bool = False  # the map's design zones were kept free
    templates: dict[str, str] = field(default_factory=dict)  # block -> template
    templates_dropped: list[str] = field(default_factory=list)  # blocks

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
    design: bool = False,
    decor_band: int = DEFAULT_DECOR_BAND,
    sizing: Sizing | None = None,
    item_gap: int = DEFAULT_ITEM_GAP,
    path_style: str = DEFAULT_PATH_STYLE,
    path_targets: str = DEFAULT_PATH_TARGETS,
    design_zones: bool = True,
    main_path_style: str | None = None,
    main_path_width: int = DEFAULT_MAIN_PATH_WIDTH,
    templates: dict[str, BlockTemplate] | None = None,
) -> Layout:
    """
    Plan the farm layout for the level-filtered *dataset*.

    *sizing* (from the Combiner) replaces the profile / level estimates of
    copies and fields with production quantities; *field_pool* is then unused.
    *templates* maps block ids to design templates (``templates.py``).
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy {strategy!r}; use one of {', '.join(STRATEGIES)}"
        )
    if reserve_ratio < 0 or gap < 0 or item_gap < 0:
        raise ValueError("reserve_ratio, gap and item_gap must not be negative")
    if path_targets not in ("blocks", "buildings"):
        raise ValueError(f"Unknown path_targets {path_targets!r}")
    if design and path_targets == "buildings" and item_gap < 1:
        raise ValueError("path_targets 'buildings' needs item_gap >= 1")
    if design:
        gap = max(gap, 1)  # room for a path between two blocks
    orders = _ORDERS.get(strategy, (strategy,))
    farm_map = farm_map or FarmMap()
    G = graph if graph is not None else build_graph(dataset)
    stock = {s.location.id: s for s in farm_stock(dataset, player, level)}
    if sizing is not None:
        _apply_sizing(stock, sizing)

    # "fixed" holds only buildings the game never moves; movable items are planned
    movable = sorted(
        f.id
        for f in farm_map.fixed
        if (loc := dataset.locations.get(f.id)) is not None
        and loc.area == Area.FARM
        and loc.movable
    )
    if movable:
        raise ValueError(
            f"Farm map lists movable items as fixed: {', '.join(movable)}. 'fixed' "
            "holds only buildings the game never moves; where they stand now goes "
            "into 'current' (open the map in tools/farm_map_editor.html and save it "
            "again)"
        )
    blocks = detect_named_blocks(G)
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
        if sizing is not None and any(n > 0 for n in sizing.crop_fields.values()):
            allocated = allocate_fields_by_use(
                blocks,
                sizing.crop_fields,
                sizing.crop_use,
                field_stock.count,
                field_stock.reserved,
            )
        else:
            allocated = allocate_fields(
                G,
                blocks,
                field_stock.count,
                field_stock.reserved,
                pool_ratio=field_pool,
            )
        for share in allocated:
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

    fits = _fit_templates(templates or {}, blocks, shares, field_stock, dataset)

    # 3. blocks with their items, relative to the block origin
    def pack_blocks(g: int, with_templates: bool = True):
        packed, areas = {}, {}
        for b in blocks:
            fit = fits.get(b.id) if with_templates else None
            items, area = _pack_block(
                b, stock, P, shares.get(b.id), field_stock, crop_names, g, fit
            )
            if items:
                packed[b.id] = items
                if area is not None:
                    areas[b.id] = area
        return packed, areas

    block_items, block_areas = pack_blocks(item_gap)
    # a block without items is not placed: its template is neither used nor dropped
    for block_id in [b for b in fits if b not in block_items]:
        logger.warning(
            "Block %s has no items; its design template is skipped", block_id
        )
        del fits[block_id]

    def frames(ratio: float) -> list[Box]:
        """4. Block frames grown by *ratio* free area."""
        boxes = []
        for b in blocks:
            items = block_items.get(b.id)
            if not items:
                continue
            t = block_areas.get(b.id)
            extra = [t.rect, *t.decorations] if t is not None else []
            inner = bounding_rect([i.rect for i in items] + extra[:1])
            frame = Rect(0, 0, *_grow(inner.w, inner.h, ratio))
            # a template is never rotated or mirrored
            rotatable = t is None and all(
                i.rect.w == i.rect.h or stock[i.location_id].location.rotatable
                for i in items
            )
            units = [frame] + [i.rect for i in items] + extra
            boxes.append(Box(b.id, frame.w, frame.h, rotatable, units))
        return boxes

    # 5. blocks on the farm map
    fixed_rects = {
        f.id: Rect(f.x, f.y, f.width, f.height) for f in farm_map.placed_fixed
    }
    weights: dict[tuple[str, str], float] = dict(block_coupling(P, blocks))
    owner = {loc: b.id for b in blocks for loc in b.locations}
    if sizing is not None and sizing.flows:
        _add_flow_weights(weights, sizing.flows, owner)
    flow_order = [i for i in block_flow_order(G, blocks) if i in block_items]
    for fixed_id in fixed_rects:
        if fixed_id not in P:
            continue
        for nb in P.neighbors(fixed_id):
            if nb in owner:
                key = tuple(sorted((fixed_id, owner[nb])))
                weights[key] = weights.get(key, 0.0) + P[fixed_id][nb]["weight"]
    bounds = (farm_map.width, farm_map.height) if farm_map.bounded else None
    area = farm_map.usable_tiles(design_zones)
    requested = reserve_ratio
    requested_gap = item_gap
    # auto tries both orders at every reserve; flow keeps the processing order
    # down to a zero reserve before it falls back to size
    phases = [(o,) for o in orders] if strategy == "flow" else [orders]
    sweep = [requested]
    while sweep[-1] > 0:  # shrink the reserve until every block fits
        sweep.append(max(0.0, round(sweep[-1] - RESERVE_STEP, 4)))

    def place(ratios: list[float]):
        for phase in phases:
            for ratio in ratios:
                boxes = frames(ratio)
                for order in phase:
                    placed, _ = pack(
                        boxes,
                        weights,
                        gap=gap,
                        obstacles=fixed_rects,
                        bounds=bounds,
                        area=area,
                        order=order,
                        sequence=flow_order,
                    )
                    if len(placed) == len(boxes):
                        return placed, boxes, order, ratio
        return placed, boxes, order, ratio

    # placing every block comes first, looks second: the item gap shrinks
    # (at the requested reserve), then the templates are dropped, and only
    # then the reserve shrinks
    attempts = [(g, True) for g in range(requested_gap, 0, -1)]
    if fits:
        attempts.append((0, True))
    packed_for = (requested_gap, True)
    for g, with_templates in attempts:
        if (g, with_templates) != packed_for:
            block_items, block_areas = pack_blocks(g, with_templates)
            packed_for = (g, with_templates)
        placements, block_boxes, order, reserve_ratio = place([requested])
        if len(placements) == len(block_boxes):
            item_gap = g
            break
    else:
        item_gap = 0
        if packed_for != (0, False) and (requested_gap > 0 or fits):
            block_items, block_areas = pack_blocks(0, False)
            packed_for = (0, False)
        placements, block_boxes, order, reserve_ratio = place(sweep)
    dropped = sorted(fits) if fits and not packed_for[1] else []
    if dropped:
        logger.warning(
            "Design templates dropped so that every block fits: %s",
            ", ".join(f"{fits[b].name} ({b})" for b in dropped),
        )
    if item_gap < requested_gap:
        logger.warning(
            "Item gap lowered from %d to %d so that every block fits",
            requested_gap,
            item_gap,
        )
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
        template = None
        t = block_areas.get(b.id)
        if t is not None:
            rest = units[len(block_items[b.id]) :]
            template = PlacedTemplate(t.name, t.mode, rest[0], rest[1:])
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
        placed_blocks.append(PlacedBlock(b, frame, items, shares.get(b.id), template))

    if not farm_map.bounded and not fixed_rects:
        _shift_to_origin(placed_blocks)

    fixed_unplaced = sorted(
        {f.id for f in farm_map.fixed if not f.is_placed}
        | {
            loc.id
            for loc in dataset.location_list
            if loc.area == Area.FARM and not loc.movable and loc.id not in fixed_rects
        }
    )
    layout = Layout(
        level=level,
        farm_map=farm_map,
        blocks=placed_blocks,
        stock=list(stock.values()),
        flow_order=flow_order,
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
        sized=sizing is not None,
        item_gap=item_gap,
        item_gap_requested=requested_gap,
        design_zones=design_zones and bool(farm_map.design_tiles()),
        templates={b: f.name for b, f in sorted(fits.items())},
        templates_dropped=dropped,
    )
    if design and path_targets == "buildings" and item_gap < 1:
        logger.warning(
            "No item gap left: paths go to the blocks, not to every building"
        )
        path_targets = "blocks"
    if design:
        layout.design = _design(
            layout,
            fixed_rects,
            decor_band,
            path_style,
            path_targets,
            design_zones,
            main_path_style,
            main_path_width,
        )
    return layout


def _design(
    layout: Layout,
    fixed: dict[str, Rect],
    decor_band: int,
    path_style: str = DEFAULT_PATH_STYLE,
    path_targets: str = DEFAULT_PATH_TARGETS,
    design_zones: bool = True,
    main_path_style: str | None = None,
    main_path_width: int = DEFAULT_MAIN_PATH_WIDTH,
) -> Design:
    """
    6. Paths and decoration band on the usable tiles of the map.

    Paths may cross design zones, but the band leaves them alone. With
    *path_targets* ``buildings`` every building (and every patch of fields,
    trees or bushes) of a block is a terminal, and paths run inside the
    block frames between them; reserved space stays an obstacle.
    """
    allowed = layout.farm_map.usable_tiles()
    if allowed is None:  # unbounded map: the drawn grid (extent + 1 tile)
        e = layout.extent()
        allowed = {
            (x, y)
            for x in range(e.x - 1, e.x + e.w + 1)
            for y in range(e.y - 1, e.y + e.h + 1)
        }
    walk_only = layout.farm_map.design_tiles() if design_zones else set()
    if path_targets == "blocks":
        blocks = {pb.block.id: pb.frame for pb in layout.blocks if pb.frame is not None}
        return plan_design(
            allowed,
            blocks,
            fixed,
            decor_band,
            path_style=path_style,
            main_path_style=main_path_style,
            main_path_width=main_path_width,
            walk_only=walk_only,
        )
    terminals: dict[str, list[Rect]] = {}
    reserved: list[Rect] = []
    # paths may run inside the block frames, but the band stays out: the free
    # part of a frame is the reserve for later unlocks
    in_frames = {
        (pb.frame.x + i, pb.frame.y + j)
        for pb in layout.blocks
        if pb.frame is not None
        for i in range(pb.frame.w)
        for j in range(pb.frame.h)
    }
    for pb in layout.blocks:
        t = pb.template
        if t is not None:  # the template's free tiles stay free
            reserved += [t.rect] if t.mode == "reserve" else t.decorations
        counts: dict[str, int] = defaultdict(int)
        for item in pb.items:
            if item.reserved:
                reserved.append(item.rect)
            elif item.in_patch:  # one terminal per patch
                terminals.setdefault(f"{pb.block.id}/{item.location_id}", []).append(
                    item.rect
                )
            else:
                counts[item.location_id] += 1
                key = f"{pb.block.id}/{item.location_id}#{counts[item.location_id]}"
                terminals[key] = [item.rect]
    design = plan_design(
        allowed,
        terminals,
        fixed,
        decor_band,
        path_style=path_style,
        main_path_style=main_path_style,
        main_path_width=main_path_width,
        obstacles=reserved,
        walk_only=set(walk_only) | in_frames,
    )
    design.path_targets = "buildings"
    return design


def _apply_sizing(stock: dict[str, Stock], sizing: Sizing) -> None:
    """Copies from production quantities, plus space kept for later unlocks."""
    for loc_id, n in sizing.counts.items():
        s = stock.get(loc_id)
        if s is not None:
            stock[loc_id] = replace(s, count=max(n, 0), source=CountSource.PRODUCTION)
    for loc_id, n in sizing.extra_reserved.items():
        s = stock.get(loc_id)
        if s is not None and n > 0:
            stock[loc_id] = replace(s, reserved=s.reserved + n)
    for loc_id in [k for k, s in stock.items() if s.count + s.reserved <= 0]:
        del stock[loc_id]


def _add_flow_weights(
    weights: dict[tuple[str, str], float],
    flows: dict[tuple[str, str], float],
    owner: dict[str, str],
) -> None:
    """
    Add the goods flows between blocks to their coupling.

    Flows are scaled so the largest one equals the strongest graph coupling,
    so neither source drowns the other.
    """
    by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for (src, dst), amount in flows.items():
        a, b = owner.get(src), owner.get(dst)
        if a is None or b is None or a == b or amount <= 0:
            continue
        by_pair[(a, b) if a < b else (b, a)] += amount
    if not by_pair:
        return
    scale = max(weights.values(), default=1.0) / max(by_pair.values())
    for key, amount in by_pair.items():
        weights[key] = weights.get(key, 0.0) + amount * scale


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


@dataclass(frozen=True)
class _TemplateFit:
    """A checked template of one block: buildings with their relative rects."""

    name: str
    mode: str
    width: int
    height: int
    buildings: list[tuple[str, Rect, bool]]  # location id, rect, rotated
    decorations: list[Rect]


def _fit_templates(
    templates: dict[str, BlockTemplate],
    blocks: list[Block],
    shares: dict[str, FieldShare],
    field_stock: Stock | None,
    dataset: DataSet,
) -> dict[str, _TemplateFit]:
    """Check each template against its block; a building not in the block is an error."""
    by_id = {b.id: b for b in blocks}
    fits: dict[str, _TemplateFit] = {}
    for block_id, bt in sorted(templates.items()):
        block = by_id.get(block_id)
        if block is None:
            logger.warning(
                "Design template %s: no block %s at this level; skipped",
                bt.name,
                block_id,
            )
            continue
        allowed = set(block.locations)
        if block_id in shares and field_stock is not None:
            allowed.add(field_stock.location.id)
        buildings = []
        for tb in bt.template.buildings:
            if tb.location_id not in allowed:
                raise ValueError(
                    f"Design template {bt.name}: {tb.location_id} is not in block "
                    f"{block_id} ({', '.join(sorted(allowed))})"
                )
            loc = dataset.locations[tb.location_id]
            size = (loc.footprint_width, loc.footprint_height)
            if loc.footprint_width is None:
                raise ValueError(
                    f"Design template {bt.name}: {tb.location_id} has no footprint"
                )
            if (tb.width, tb.height) == size:
                rotated = False
            elif loc.rotatable and (tb.height, tb.width) == size:
                rotated = True
            else:
                raise ValueError(
                    f"Design template {bt.name}: {tb.location_id} is "
                    f"{tb.width}x{tb.height}, its footprint is {size[0]}x{size[1]}"
                )
            buildings.append(
                (tb.location_id, Rect(tb.x, tb.y, tb.width, tb.height), rotated)
            )
        fits[block_id] = _TemplateFit(
            bt.name,
            bt.mode,
            bt.template.width,
            bt.template.height,
            buildings,
            [Rect(*cell) for cell in bt.template.decorations],
        )
    return fits


def _pack_block(
    block: Block,
    stock: dict[str, Stock],
    P: nx.Graph,
    share: FieldShare | None,
    field_stock: Stock | None,
    crop_names: dict[str, str],
    item_gap: int = 0,
    fit: _TemplateFit | None = None,
) -> tuple[list[PlacedItem], PlacedTemplate | None]:
    """
    Pack the items of one block; returns items relative to the block origin.

    With a template (*fit*) the template area is returned too, relative to the
    same origin: ``reserve`` packs it as one free box with the items, ``arrange``
    puts its buildings at their template positions and packs the rest around.
    """
    arrange = fit is not None and fit.mode == "arrange"
    in_template = Counter(loc for loc, _, _ in fit.buildings) if arrange else Counter()

    def copies(loc_id: str, owned: int, total: int) -> tuple[int, int]:
        """(owned, total) copies left after the template buildings."""
        n = in_template[loc_id]
        return max(0, owned - n), max(0, total - n)

    boxes: list[Box] = []
    meta: dict[str, tuple[str, bool]] = {}  # box key -> (location id, reserved)
    reserved_units: dict[str, int] = {}
    names: dict[str, str] = {}
    if share is not None and field_stock.location.footprint_width is not None:
        f = field_stock.location
        crops = ", ".join(crop_names[c] for c in share.crops[:2]) or "shared"
        names[f.id] = f"{f.name} ({crops})"
        owned, total = copies(f.id, share.count, share.count + share.reserved)
        if total:
            boxes.append(
                patch(f.id, f.footprint_width, f.footprint_height, total, False)
            )
            meta[f.id] = (f.id, False)
            reserved_units[f.id] = total - owned
    for loc_id in block.locations:
        s = stock.get(loc_id)
        if s is None or s.location.footprint_width is None:
            continue
        if s.location.type == LocationType.FIELD:
            continue
        loc = s.location
        w, h = loc.footprint_width, loc.footprint_height
        owned, total = copies(loc_id, s.count, s.count + s.reserved)
        if loc.type in _PATCH_TYPES and total > 1:
            boxes.append(patch(loc_id, w, h, total, loc.rotatable))
            meta[loc_id] = (loc_id, False)
            reserved_units[loc_id] = total - owned
            continue
        for i in range(total):
            key = f"{loc_id}#{i + 1}"
            boxes.append(Box(key, w, h, loc.rotatable))
            meta[key] = (loc_id, i >= owned)

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

    # the template is the box (reserve) or the obstacle (arrange) "template";
    # it pulls the boxes of its buildings and their neighbours
    obstacles: dict[str, Rect] = {}
    if fit is not None:
        template_rect = Rect(0, 0, fit.width, fit.height)
        own = {loc for loc, _, _ in fit.buildings}
        for b in boxes:
            la = meta[b.key][0]
            wt = COPY_WEIGHT if la in own else 0.0
            wt += sum(P[la][lb]["weight"] for lb in own if P.has_edge(la, lb))
            if wt:
                weights[tuple(sorted((b.key, _TEMPLATE_KEY)))] += wt
        if arrange:
            obstacles[_TEMPLATE_KEY] = template_rect
        else:
            boxes.append(Box(_TEMPLATE_KEY, fit.width, fit.height, False))
    # item_gap: free tiles between the boxes; a patch is one box, so it stays whole
    placements, _ = pack(boxes, weights, gap=item_gap, obstacles=obstacles)

    items: list[PlacedItem] = []
    template: PlacedTemplate | None = None
    if fit is not None:
        if arrange:
            template = PlacedTemplate(
                fit.name, fit.mode, template_rect, fit.decorations
            )
            seen: Counter[str] = Counter()
            for loc_id, rect, rotated in fit.buildings:
                owned = (
                    share.count
                    if field_stock is not None and loc_id == field_stock.location.id
                    else (stock[loc_id].count if loc_id in stock else 0)
                )
                name = names.get(loc_id) or (
                    stock[loc_id].location.name if loc_id in stock else loc_id
                )
                items.append(
                    PlacedItem(
                        loc_id,
                        name,
                        block.id,
                        rect,
                        rotated,
                        seen[loc_id] >= owned,
                        False,
                    )
                )
                seen[loc_id] += 1
        elif _TEMPLATE_KEY in placements:
            template = PlacedTemplate(
                fit.name, fit.mode, placements.pop(_TEMPLATE_KEY).rect
            )
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
        rects = [i.rect for i in items] + ([template.rect] if template else [])
        origin = bounding_rect(rects)

        def shift(r: Rect) -> Rect:
            return Rect(r.x - origin.x, r.y - origin.y, r.w, r.h)

        for i in items:
            i.rect = shift(i.rect)
        if template is not None:
            template = PlacedTemplate(
                template.name,
                template.mode,
                shift(template.rect),
                [
                    shift(Rect(template.rect.x + d.x, template.rect.y + d.y, d.w, d.h))
                    for d in template.decorations
                ],
            )
    return items, template


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
        if b.template is not None:
            b.template = b.template.moved(-o.x, -o.y)


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
