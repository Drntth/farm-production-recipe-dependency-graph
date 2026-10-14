"""
Design layer (farm): walkable paths and a free decoration band.

Optional on top of the functional layout (``--design``):

- Paths connect every placed block and the key fixed buildings into one
  network of 1-tile paths on free tiles. The network grows from the hub (on
  the farm the farmhouse, else the Storage block; else the first) and each
  time adds
  the shortest path to the nearest terminal not reached yet (a greedy Steiner
  tree). A terminal is reached at any free tile next to it.
- A key building with no reachable free tile next to it (on the farm the
  riverboat and the leaderboard: a paved strip that is not buildable lies
  between them and the farm) gets a path to its connection point instead: the
  reachable free tile nearest to it, if at most ``MAX_APPROACH_GAP`` tiles
  are left between that point and the building (``approached``); farther
  away it stays unreachable.
- The decoration band is the free tiles within ``decor_band`` steps of a path:
  room for decorations and fences along the paths, not for buildings.

Blocks keep at least one free tile between them (``gap`` >= 1), so a path can
always pass between two blocks. Tiles inside block frames are never used.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass, field

from .blocks import STORAGE_BLOCK_ID
from .farm_map import Tile
from .packing import Rect

DEFAULT_DECOR_BAND = 1
MAX_APPROACH_GAP = 5  # tiles of non-buildable ground a connection point may leave
FARM_HUBS = ("farmhouse", STORAGE_BLOCK_ID)
# fixed farm buildings the player walks to often (ids of config/farm_map*.json)
KEY_BUILDINGS = ("farmhouse", "barn", "silo", "truck", "roadside_shop", "riverboat")
_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class Design:
    paths: set[Tile] = field(default_factory=set)
    decorations: set[Tile] = field(default_factory=set)
    connected: list[str] = field(default_factory=list)  # in the order reached
    unreachable: list[str] = field(default_factory=list)
    # key building -> tiles between its connection point and the building
    approached: dict[str, int] = field(default_factory=dict)
    decor_band: int = DEFAULT_DECOR_BAND


def _tiles(r: Rect) -> set[Tile]:
    return {(r.x + i, r.y + j) for i in range(r.w) for j in range(r.h)}


def _border(r: Rect, free: set[Tile]) -> set[Tile]:
    """Free tiles next to a side of *r*."""
    around = {(r.x + i, r.y - 1) for i in range(r.w)}
    around |= {(r.x + i, r.y + r.h) for i in range(r.w)}
    around |= {(r.x - 1, r.y + j) for j in range(r.h)}
    around |= {(r.x + r.w, r.y + j) for j in range(r.h)}
    return around & free


def _gap(tile: Tile, r: Rect) -> int:
    """Tiles between *tile* and *r* along the grid (0 = next to it)."""
    dx = max(r.x - tile[0], 0, tile[0] - (r.x + r.w - 1))
    dy = max(r.y - tile[1], 0, tile[1] - (r.y + r.h - 1))
    return dx + dy - 1


def _reachable(sources: set[Tile], free: set[Tile]) -> set[Tile]:
    """Free tiles connected to *sources*."""
    seen = set(sources)
    queue = deque(sources)
    while queue:
        x, y = queue.popleft()
        for dx, dy in _STEPS:
            nxt = (x + dx, y + dy)
            if nxt in free and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _shortest(
    sources: set[Tile], targets: dict[str, set[Tile]], free: set[Tile]
) -> tuple[str, list[Tile]] | None:
    """Breadth-first search from *sources* to the nearest target tile set."""
    owner = {t: key for key, tiles in targets.items() for t in tiles}
    prev: dict[Tile, Tile | None] = {}
    queue = deque()
    for s in sorted(sources):
        prev[s] = None
        queue.append(s)
    while queue:
        tile = queue.popleft()
        if tile in owner:
            path = [tile]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            return owner[tile], path
        for dx, dy in _STEPS:
            nxt = (tile[0] + dx, tile[1] + dy)
            if nxt in free and nxt not in prev:
                prev[nxt] = tile
                queue.append(nxt)
    return None


def plan_design(
    allowed: set[Tile],
    blocks: dict[str, Rect],
    fixed: dict[str, Rect],
    decor_band: int = DEFAULT_DECOR_BAND,
    *,
    hubs: tuple[str, ...] = FARM_HUBS,
    keys: Collection[str] = KEY_BUILDINGS,
) -> Design:
    """
    Paths and decoration band on *allowed* tiles around the placed *blocks*.

    *fixed* holds every placed fixed building (obstacles); the ones in *keys*
    are also connected. The first of *hubs* that exists starts the network.
    """
    if decor_band < 0:
        raise ValueError("decor_band must not be negative")
    occupied = set().union(*(_tiles(r) for r in [*blocks.values(), *fixed.values()]))
    free = allowed - occupied
    terminals = dict(blocks)
    terminals.update({k: r for k, r in fixed.items() if k in keys})
    design = Design(decor_band=decor_band)
    if not terminals:
        return design

    borders = {key: _border(r, free) for key, r in terminals.items()}
    hub = next(
        (h for h in hubs if borders.get(h)),
        min((k for k, b in borders.items() if b), default=None),
    )
    if hub is None:  # nothing has a free tile next to it
        design.unreachable = sorted(terminals)
        return design
    design.connected.append(hub)
    sources = set(borders.pop(hub))
    first = True
    approach_done = False
    while borders:
        targets = {k: b for k, b in borders.items() if b}
        found = _shortest(sources, targets, free) if targets else None
        if found is None:
            if approach_done:
                break
            # cut off key buildings: aim at the nearest reachable free tile
            approach_done = True
            component = _reachable(sources, free)
            for key in sorted(borders):
                if key in fixed and component:
                    gap = min(_gap(t, fixed[key]) for t in component)
                    if gap > MAX_APPROACH_GAP:
                        continue
                    borders[key] = {t for t in component if _gap(t, fixed[key]) == gap}
                    design.approached[key] = gap
            continue
        key, path = found
        if first:  # the hub's free side tiles were only candidates
            sources = set()
            first = False
        sources |= set(path)
        design.paths |= set(path)
        design.connected.append(key)
        del borders[key]
    for key in borders:
        design.approached.pop(key, None)
    design.unreachable.extend(sorted(borders))

    # decoration band: free tiles within decor_band steps of a path
    frontier = set(design.paths)
    seen = set(design.paths)
    for _ in range(decor_band):
        nxt = {
            (x + dx, y + dy)
            for x, y in frontier
            for dx, dy in _STEPS
            if (x + dx, y + dy) in free and (x + dx, y + dy) not in seen
        }
        design.decorations |= nxt
        seen |= nxt
        frontier = nxt
    design.unreachable.sort()
    return design
