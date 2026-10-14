"""
Design layer (farm): walkable paths and a free decoration band.

Optional on top of the functional layout (``design_layer`` in config/design.json):

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
- ``path_style``: ``shortest`` takes any shortest path (breadth-first search);
  ``straight`` adds ``TURN_COST`` for every change of direction, so paths have
  fewer corners and detours.
- A terminal may be several rects (a patch of fields): reached next to any.
  With ``path_targets: buildings`` the planner passes every building of a
  block as a terminal and only the items as obstacles, so paths run between
  the buildings (this needs ``item_gap`` >= 1).
- ``walk_only`` tiles (design zones) carry paths but no decoration band.
- The decoration band is the free tiles within ``decor_band`` steps of a path:
  room for decorations and fences along the paths, not for buildings.
- Figures for comparing settings: path tiles, ``corners`` (path tiles with a
  path neighbour along both axes: turns and junctions), ``detour_ratio``
  (tiles walked per tile of straight-line grid distance, over all connections).

Blocks keep at least one free tile between them (``gap`` >= 1), so a path can
always pass between two blocks.
"""

from __future__ import annotations

import heapq
import math
from collections import deque
from collections.abc import Collection
from dataclasses import dataclass, field

from src.settings import DEFAULT_DECOR_BAND

from .blocks import STORAGE_BLOCK_ID
from .farm_map import Tile
from .packing import Rect

TURN_COST = 3  # path_style "straight": one corner costs as much as 3 tiles
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
    path_style: str = "shortest"
    path_targets: str = "blocks"  # what the paths connect: blocks or buildings
    walked: int = 0  # tiles walked over all connections
    direct: int = 0  # grid distance (Manhattan) over all connections

    @property
    def corners(self) -> int:
        """Path tiles with a path neighbour along both axes (turns, junctions)."""
        p = self.paths
        return sum(
            1
            for x, y in p
            if ((x + 1, y) in p or (x - 1, y) in p)
            and ((x, y + 1) in p or (x, y - 1) in p)
        )

    @property
    def detour_ratio(self) -> float:
        """Tiles walked per tile of grid distance (1.0 = no detour)."""
        return self.walked / self.direct if self.direct else 1.0


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


def _cheapest(
    sources: set[Tile], targets: dict[str, set[Tile]], free: set[Tile], turn: int
) -> tuple[str, list[Tile]] | None:
    """Dijkstra from *sources*: one per step plus *turn* per change of direction."""
    owner = {t: key for key, tiles in targets.items() for t in tiles}
    best: dict[tuple[Tile, int], float] = {}
    prev: dict[tuple[Tile, int], tuple[Tile, int] | None] = {}
    heap: list[tuple[float, Tile, int]] = []
    for s in sorted(sources):
        best[(s, -1)] = 0
        prev[(s, -1)] = None
        heap.append((0, s, -1))
    heapq.heapify(heap)
    while heap:
        cost, tile, d = heapq.heappop(heap)
        if cost > best.get((tile, d), math.inf):
            continue
        if tile in owner:
            path, state = [], (tile, d)
            while state is not None:
                path.append(state[0])
                state = prev[state]
            return owner[tile], path
        for i, (dx, dy) in enumerate(_STEPS):
            nxt = (tile[0] + dx, tile[1] + dy)
            if nxt not in free:
                continue
            c = cost + 1 + (turn if d not in (-1, i) else 0)
            if c < best.get((nxt, i), math.inf):
                best[(nxt, i)] = c
                prev[(nxt, i)] = (tile, d)
                heapq.heappush(heap, (c, nxt, i))
    return None


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
    blocks: dict[str, Rect | list[Rect]],
    fixed: dict[str, Rect],
    decor_band: int = DEFAULT_DECOR_BAND,
    *,
    hubs: tuple[str, ...] = FARM_HUBS,
    keys: Collection[str] = KEY_BUILDINGS,
    path_style: str = "shortest",
    obstacles: Collection[Rect] = (),
    walk_only: Collection[Tile] = (),
) -> Design:
    """
    Paths and decoration band on *allowed* tiles around the placed *blocks*.

    *blocks* maps each terminal to its rect(s). *fixed* holds every placed
    fixed building (obstacles); the ones in *keys* are also connected. The
    first of *hubs* that exists starts the network. *obstacles* are more
    occupied rects that are no terminal (reserved space); *walk_only* tiles
    carry paths but no decoration band.
    """
    if decor_band < 0:
        raise ValueError("decor_band must not be negative")
    if path_style not in ("shortest", "straight"):
        raise ValueError(f"Unknown path_style {path_style!r}")
    groups = {k: v if isinstance(v, list) else [v] for k, v in blocks.items()}
    taken = [r for rects in groups.values() for r in rects]
    taken += [*fixed.values(), *obstacles]
    occupied = set().union(*(_tiles(r) for r in taken))
    free = allowed - occupied
    terminals = dict(groups)
    terminals.update({k: [r] for k, r in fixed.items() if k in keys})
    design = Design(decor_band=decor_band, path_style=path_style)
    if not terminals:
        return design

    def search(sources, targets):
        if path_style == "straight":
            return _cheapest(sources, targets, free, TURN_COST)
        return _shortest(sources, targets, free)

    borders = {
        key: set().union(*(_border(r, free) for r in rects))
        for key, rects in terminals.items()
    }
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
        found = search(sources, targets) if targets else None
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
        design.walked += len(path) - 1
        design.direct += abs(path[0][0] - path[-1][0]) + abs(path[0][1] - path[-1][1])
        design.connected.append(key)
        del borders[key]
    for key in borders:
        design.approached.pop(key, None)
    design.unreachable.extend(sorted(borders))

    # decoration band: free tiles within decor_band steps of a path
    decor_free = free - set(walk_only)
    frontier = set(design.paths)
    seen = set(design.paths)
    for _ in range(decor_band):
        nxt = {
            (x + dx, y + dy)
            for x, y in frontier
            for dx, dy in _STEPS
            if (x + dx, y + dy) in decor_free and (x + dx, y + dy) not in seen
        }
        design.decorations |= nxt
        seen |= nxt
        frontier = nxt
    design.unreachable.sort()
    return design
