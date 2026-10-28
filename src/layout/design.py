"""
Design layer (farm): walkable paths and a free decoration band.

Optional on top of the functional layout (``design_layer`` in config/design.json):

- Paths connect every placed block and the key fixed buildings into one
  network of paths on free tiles. The network grows from the hub (on the farm
  the farmhouse, else the Storage block; else the first) and each time adds
  the shortest path to the nearest terminal not reached yet (a greedy Steiner
  tree). A terminal is reached at any free tile next to it.
- The main path comes first: it reaches the key buildings and the Storage
  block (barn and silo). Side paths then join every other terminal to the
  nearest point of the network.
- ``main_path_width`` 2 adds a second lane to the main path: the path shifted
  by one diagonal step to the side with the most free tiles. Where the lane
  does not fit (between two blocks with ``gap`` 1) the main path narrows to 1
  tile; ``narrowed`` counts those tiles.
- A key building with no reachable free tile next to it (on the farm the
  riverboat and the leaderboard: a paved strip that is not buildable lies
  between them and the farm) gets a path to its connection point instead: the
  reachable free tile nearest to it, if at most ``MAX_APPROACH_GAP`` tiles
  are left between that point and the building (``approached``); farther
  away it stays unreachable.
- ``path_style``: ``shortest`` takes any shortest path (breadth-first search);
  ``straight`` adds ``TURN_COST`` for every change of direction, so paths have
  fewer corners and detours; ``stepped`` takes the shortest path closest to
  the straight line between its ends (a staircase: diagonal on the isometric
  grid). ``main_path_style`` (default: ``path_style``) styles the main path.
- A terminal may be several rects (a patch of fields): reached next to any.
  With ``path_targets: buildings`` the planner passes every building of a
  block as a terminal and only the items as obstacles, so paths run between
  the buildings (this needs ``item_gap`` >= 1).
- ``walk_only`` tiles (design zones) carry paths but no decoration band.
- The decoration band is the free tiles within ``decor_band`` steps of a path:
  room for decorations and fences along the paths, not for buildings.
- Figures for comparing settings: path tiles (main and side apart),
  ``corners`` (centre-line tiles with a path neighbour along both axes: turns
  and junctions; the second lane is left out), ``detour_ratio``
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
PATH_STYLES = ("shortest", "straight", "stepped")
_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_LANE_SHIFTS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


@dataclass
class Design:
    paths: set[Tile] = field(default_factory=set)  # main and side paths
    main_paths: set[Tile] = field(default_factory=set)  # incl. the second lane
    lanes: set[Tile] = field(default_factory=set)  # second lane, not a centre line
    decorations: set[Tile] = field(default_factory=set)
    connected: list[str] = field(default_factory=list)  # in the order reached
    unreachable: list[str] = field(default_factory=list)
    # key building -> tiles between its connection point and the building
    approached: dict[str, int] = field(default_factory=dict)
    decor_band: int = DEFAULT_DECOR_BAND
    path_style: str = "shortest"
    main_path_style: str = "shortest"
    main_path_width: int = 1
    narrowed: int = 0  # main path tiles where the second lane did not fit
    path_targets: str = "blocks"  # what the paths connect: blocks or buildings
    walked: int = 0  # tiles walked over all connections
    direct: int = 0  # grid distance (Manhattan) over all connections

    @property
    def side_paths(self) -> set[Tile]:
        return self.paths - self.main_paths

    @property
    def corners(self) -> int:
        """Centre-line tiles with a path neighbour along both axes (turns, junctions)."""
        p = self.paths - self.lanes
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


def _stepped(
    sources: set[Tile], targets: dict[str, set[Tile]], free: set[Tile]
) -> tuple[str, list[Tile]] | None:
    """
    Shortest path to the nearest target whose tiles stay closest to the
    straight line between its ends: fewest steps first, then the least summed
    distance from the line.
    """
    found = _shortest(sources, targets, free)
    if found is None:
        return None
    key, path = found
    (sx, sy), end = path[-1], path[0]
    ex, ey = end

    def off(t: Tile) -> int:  # distance from the line, times its length
        return abs((ex - sx) * (t[1] - sy) - (ey - sy) * (t[0] - sx))

    start = (sx, sy)
    best: dict[Tile, tuple[int, int]] = {start: (0, 0)}
    prev: dict[Tile, Tile | None] = {start: None}
    heap = [(0, 0, start)]
    while heap:
        steps, dev, tile = heapq.heappop(heap)
        if tile == end:
            break
        if (steps, dev) > best[tile]:
            continue
        for dx, dy in _STEPS:
            nxt = (tile[0] + dx, tile[1] + dy)
            if nxt not in free:
                continue
            c = (steps + 1, dev + off(nxt))
            if c < best.get(nxt, (math.inf, math.inf)):
                best[nxt] = c
                prev[nxt] = tile
                heapq.heappush(heap, (*c, nxt))
    route = [end]
    while prev[route[-1]] is not None:
        route.append(prev[route[-1]])
    return key, route


def _lane(path: list[Tile], free: set[Tile]) -> tuple[set[Tile], int]:
    """
    Second lane of a 2-tile main path: *path* shifted one diagonal step to the
    side with the most free tiles. Lane pieces that touch the path only at a
    corner (cut off where the lane does not fit) are dropped. Returns the lane
    and the inner path tiles where it does not fit.
    """
    on_path = set(path)

    def shifted(v: Tile) -> set[Tile]:
        return {(x + v[0], y + v[1]) for x, y in path} & free

    v = max(_LANE_SHIFTS, key=lambda v: len(shifted(v) - on_path))
    lane = shifted(v) - on_path
    lane &= _reachable(on_path, on_path | lane)  # only pieces joined to the path
    narrowed = sum(
        1 for x, y in path[1:-1] if (x + v[0], y + v[1]) not in on_path | lane
    )
    return lane, narrowed


def plan_design(
    allowed: set[Tile],
    blocks: dict[str, Rect | list[Rect]],
    fixed: dict[str, Rect],
    decor_band: int = DEFAULT_DECOR_BAND,
    *,
    hubs: tuple[str, ...] = FARM_HUBS,
    keys: Collection[str] = KEY_BUILDINGS,
    path_style: str = "shortest",
    main_path_style: str | None = None,
    main_path_width: int = 1,
    obstacles: Collection[Rect] = (),
    walk_only: Collection[Tile] = (),
) -> Design:
    """
    Paths and decoration band on *allowed* tiles around the placed *blocks*.

    *blocks* maps each terminal to its rect(s). *fixed* holds every placed
    fixed building (obstacles); the ones in *keys* are also connected. The
    first of *hubs* that exists starts the network. The main path reaches the
    key buildings and the Storage block first (*main_path_style*, default
    *path_style*; *main_path_width* 1 or 2). *obstacles* are more occupied
    rects that are no terminal (reserved space); *walk_only* tiles carry paths
    but no decoration band.
    """
    main_path_style = main_path_style or path_style
    if decor_band < 0:
        raise ValueError("decor_band must not be negative")
    for style in (path_style, main_path_style):
        if style not in PATH_STYLES:
            raise ValueError(f"Unknown path_style {style!r}")
    if main_path_width not in (1, 2):
        raise ValueError("main_path_width must be 1 or 2")
    groups = {k: v if isinstance(v, list) else [v] for k, v in blocks.items()}
    taken = [r for rects in groups.values() for r in rects]
    taken += [*fixed.values(), *obstacles]
    occupied = set().union(*(_tiles(r) for r in taken))
    free = allowed - occupied
    terminals = dict(groups)
    terminals.update({k: [r] for k, r in fixed.items() if k in keys})
    design = Design(
        decor_band=decor_band,
        path_style=path_style,
        main_path_style=main_path_style,
        main_path_width=main_path_width,
    )
    if not terminals:
        return design

    def search(sources, targets, style):
        if style == "straight":
            return _cheapest(sources, targets, free, TURN_COST)
        if style == "stepped":
            return _stepped(sources, targets, free)
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
    # the main path: key buildings and the Storage block (barn, silo)
    main_keys = {
        k
        for k in borders
        if k in keys or k == STORAGE_BLOCK_ID or k.startswith(f"{STORAGE_BLOCK_ID}/")
    }
    stuck: list[str] = []
    lines: set[Tile] = set()
    first = True
    approach_done = False
    while borders:
        main_left = {k: b for k, b in borders.items() if k in main_keys}
        targets = {k: b for k, b in (main_left or borders).items() if b}
        style = main_path_style if main_left else path_style
        found = search(sources, targets, style) if targets else None
        if found is None:
            if not approach_done:
                # cut off key buildings: aim at the nearest reachable free tile
                approach_done = True
                component = _reachable(sources, free)
                for key in sorted(borders):
                    if key in fixed and component:
                        gap = min(_gap(t, fixed[key]) for t in component)
                        if gap > MAX_APPROACH_GAP:
                            continue
                        borders[key] = {
                            t for t in component if _gap(t, fixed[key]) == gap
                        }
                        design.approached[key] = gap
                continue
            if main_left:  # key buildings out of reach: go on with the blocks
                stuck.extend(main_left)
                for key in main_left:
                    del borders[key]
                continue
            break
        key, path = found
        if first:  # the hub's free side tiles were only candidates
            sources = set()
            first = False
        sources |= set(path)
        lines |= set(path)
        design.paths |= set(path)
        if main_left:
            design.main_paths |= set(path)
            if main_path_width == 2:
                lane, narrowed = _lane(path, free)
                design.lanes |= lane
                design.main_paths |= lane
                design.paths |= lane
                design.narrowed += narrowed
                sources |= lane
        design.walked += len(path) - 1
        design.direct += abs(path[0][0] - path[-1][0]) + abs(path[0][1] - path[-1][1])
        design.connected.append(key)
        del borders[key]
    design.lanes -= lines  # a lane tile a later path runs along is a centre line
    for key in [*stuck, *borders]:
        design.approached.pop(key, None)
    design.unreachable.extend(sorted([*stuck, *borders]))

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
