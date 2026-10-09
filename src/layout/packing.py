"""
Greedy rectangle packing on the tile grid.

The same placer arranges the items inside a block and the blocks on the farm:

1. The box with the strongest total coupling goes first.
2. Next comes the unplaced box most strongly coupled to what is already
   placed (fixed obstacles count as placed). With ``order="size"`` the
   largest box goes next instead, which fills an irregular area better.
3. Candidate positions touch a side of a placed box or obstacle (with a
   ``gap``). Each candidate costs the coupling-weighted distance to the placed
   boxes plus a compactness term (half perimeter of the bounding box) and,
   with an ``area``, a small pull toward the middle of the area.
4. A rotatable box also tries its transposed orientation (width ↔ height).
5. With an ``area`` (a set of usable tiles, e.g. the unlocked farm plots) a
   box must lie fully on usable tiles.

A box can hold several unit footprints (a patch of fields, a whole block);
transposing the box transposes every unit, which is a valid placement only
if each unit may rotate - the caller decides through ``Box.rotatable``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

COMPACTNESS = 0.5
CENTRING = 0.25  # pull toward the middle of the usable area, so free space stays balanced


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def overlaps(self, other: Rect, gap: int = 0) -> bool:
        return not (
            self.x + self.w + gap <= other.x
            or other.x + other.w + gap <= self.x
            or self.y + self.h + gap <= other.y
            or other.y + other.h + gap <= self.y
        )

    def transposed(self) -> Rect:
        return Rect(self.y, self.x, self.h, self.w)


@dataclass
class Box:
    """Something to place: a size plus the unit rects it is made of (relative)."""

    key: str
    w: int
    h: int
    rotatable: bool = False
    units: list[Rect] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.units:
            self.units = [Rect(0, 0, self.w, self.h)]

    def transposed(self) -> Box:
        return Box(self.key, self.h, self.w, self.rotatable, [u.transposed() for u in self.units])


@dataclass(frozen=True)
class Placement:
    key: str
    rect: Rect
    rotated: bool


def patch(key: str, unit_w: int, unit_h: int, count: int, rotatable: bool) -> Box:
    """A near-square patch of *count* equal units laid out in rows."""
    cols = max(1, math.ceil(math.sqrt(count * unit_h / unit_w)))
    rows = math.ceil(count / cols)
    units = [
        Rect((i % cols) * unit_w, (i // cols) * unit_h, unit_w, unit_h) for i in range(count)
    ]
    return Box(key, cols * unit_w, rows * unit_h, rotatable, units)


def pack(
    boxes: list[Box],
    weights: dict[tuple[str, str], float],
    *,
    gap: int = 0,
    obstacles: dict[str, Rect] | None = None,
    bounds: tuple[int, int] | None = None,
    area: set[tuple[int, int]] | None = None,
    order: str = "coupling",
) -> tuple[dict[str, Placement], list[str]]:
    """
    Place *boxes*; return ``(placements, unplaced_keys)``.

    *weights* maps sorted key pairs to coupling; keys may also name obstacles.
    *bounds* ``(width, height)`` limits the grid to ``0 <= x < width``; without
    it the grid is unbounded and coordinates may be negative.
    """
    obstacles = dict(obstacles or {})

    def wt(a: str, b: str) -> float:
        return weights.get((a, b) if a < b else (b, a), 0.0)

    placed: dict[str, Placement] = {}
    unplaced: list[str] = []
    todo = {b.key: b for b in boxes}
    centre = _centroid(area)

    while todo:
        anchors = {k: p.rect for k, p in placed.items()} | obstacles
        if order == "size":
            key = max(
                todo,
                key=lambda k: (todo[k].w * todo[k].h, sum(wt(k, a) for a in anchors), neg_key(k)),
            )
        elif placed:
            key = max(
                todo,
                key=lambda k: (
                    sum(wt(k, a) for a in anchors),
                    todo[k].w * todo[k].h,
                    neg_key(k),
                ),
            )
        else:
            key = max(
                todo,
                key=lambda k: (
                    sum(wt(k, a) for a in anchors),
                    sum(wt(k, o) for o in todo),
                    todo[k].w * todo[k].h,
                    neg_key(k),
                ),
            )
        box = todo.pop(key)
        best = _best_position(box, anchors, placed, wt, gap, bounds, area, centre)
        if best is None:
            unplaced.append(key)
        else:
            placed[key] = best
    return placed, unplaced


def oriented_units(box: Box, placement: Placement) -> list[Rect]:
    """Absolute unit rects of *box* at *placement*."""
    units = [u.transposed() for u in box.units] if placement.rotated else box.units
    return [Rect(placement.rect.x + u.x, placement.rect.y + u.y, u.w, u.h) for u in units]


def bounding_rect(rects: list[Rect]) -> Rect:
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.x + r.w for r in rects)
    y1 = max(r.y + r.h for r in rects)
    return Rect(x0, y0, x1 - x0, y1 - y0)


def _on_area(r: Rect, area: set[tuple[int, int]] | None) -> bool:
    if area is None:
        return True
    corners = ((r.x, r.y), (r.x + r.w - 1, r.y), (r.x, r.y + r.h - 1), (r.x + r.w - 1, r.y + r.h - 1))
    if any(c not in area for c in corners):
        return False
    return all((r.x + i, r.y + j) in area for i in range(r.w) for j in range(r.h))


def _centroid(area: set[tuple[int, int]] | None) -> tuple[float, float] | None:
    if not area:
        return None
    return (
        sum(t[0] for t in area) / len(area) + 0.5,
        sum(t[1] for t in area) / len(area) + 0.5,
    )


def _best_position(
    box, anchors, placed, wt, gap, bounds, area=None, centre=None
) -> Placement | None:
    orientations = [(box.w, box.h, False)]
    if box.rotatable and box.w != box.h:
        orientations.append((box.h, box.w, True))

    placed_rects = [p.rect for p in placed.values()]
    blocking = list(anchors.values())
    best: tuple[float, Placement] | None = None

    for w, h, rotated in orientations:
        for x, y in _candidates(w, h, anchors, gap, bounds):
            r = Rect(x, y, w, h)
            if bounds is not None and (x < 0 or y < 0 or x + w > bounds[0] or y + h > bounds[1]):
                continue
            if any(r.overlaps(o, gap) for o in blocking) or not _on_area(r, area):
                continue
            cost = _cost(box.key, r, anchors, placed_rects, wt, centre)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, Placement(box.key, r, rotated))
        scan = _scan_range(bounds, area)
        if best is None and scan is not None:
            (x0, x1), (y0, y1) = scan
            for x in range(x0, x1 - w + 1):
                for y in range(y0, y1 - h + 1):
                    r = Rect(x, y, w, h)
                    if any(r.overlaps(o, gap) for o in blocking) or not _on_area(r, area):
                        continue
                    cost = _cost(box.key, r, anchors, placed_rects, wt, centre)
                    if best is None or cost < best[0] - 1e-9:
                        best = (cost, Placement(box.key, r, rotated))
    return best[1] if best else None


def _scan_range(bounds, area):
    """x and y ranges for the exhaustive fallback scan, or None if unbounded."""
    if area:
        xs = [t[0] for t in area]
        ys = [t[1] for t in area]
        return (min(xs), max(xs) + 1), (min(ys), max(ys) + 1)
    if bounds is not None:
        return (0, bounds[0]), (0, bounds[1])
    return None


def _candidates(w, h, anchors, gap, bounds):
    if not anchors:
        if bounds is None:
            yield (0, 0)
        else:
            yield ((bounds[0] - w) // 2, (bounds[1] - h) // 2)
        return
    for a in anchors.values():
        ys = {a.y, a.y + a.h - h, a.y + (a.h - h) // 2}
        xs = {a.x, a.x + a.w - w, a.x + (a.w - w) // 2}
        for y in ys:
            yield (a.x + a.w + gap, y)
            yield (a.x - w - gap, y)
        for x in xs:
            yield (x, a.y + a.h + gap)
            yield (x, a.y - h - gap)


def _cost(key, r, anchors, placed_rects, wt, centre=None) -> float:
    cx, cy = r.center
    total_w = 0.0
    pull = 0.0
    for k, a in anchors.items():
        w = wt(key, k)
        if w <= 0:
            continue
        ax, ay = a.center
        pull += w * (abs(cx - ax) + abs(cy - ay))
        total_w += w
    pull = pull / total_w if total_w else 0.0
    bb = bounding_rect(placed_rects + [r])
    cost = pull + COMPACTNESS * (bb.w + bb.h)
    if centre is not None:
        cost += CENTRING * (abs(cx - centre[0]) + abs(cy - centre[1]))
    return cost


def neg_key(s: str) -> tuple[int, ...]:
    """
    Deterministic tie-break key for max(): prefers the alphabetically first id.

    Exception: when one id is a prefix of the other ("ab" vs "abc"), the
    longer one wins. Only determinism matters here, not the exact order.
    """
    return tuple(-ord(c) for c in s)
