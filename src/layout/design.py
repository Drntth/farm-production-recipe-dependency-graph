"""
Design layer (farm): walkable paths and a free decoration band.

Optional on top of the functional layout (``--design``):

- Paths connect every placed block and the key fixed buildings into one
  network of 1-tile paths on free tiles. The network grows from the hub (on
  the farm the farmhouse, else the Storage block; else the first) and each
  time adds
  the shortest path to the nearest terminal not reached yet (a greedy Steiner
  tree). A terminal is reached at any free tile next to it.
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
    for key in sorted(k for k, b in borders.items() if not b):
        design.unreachable.append(key)  # walled in: no free tile next to it
        del borders[key]
    if not borders:
        return design
    hub = next(
        (h for h in hubs if h in borders),
        min(borders),
    )
    design.connected.append(hub)
    sources = set(borders.pop(hub))
    first = True
    while borders:
        found = _shortest(sources, borders, free)
        if found is None:
            design.unreachable.extend(sorted(borders))
            break
        key, path = found
        if first:  # the hub's free side tiles were only candidates
            sources = set()
            first = False
        sources |= set(path)
        design.paths |= set(path)
        design.connected.append(key)
        del borders[key]

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
