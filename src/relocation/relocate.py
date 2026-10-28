"""
Relocation plan: from the current farm to a planned layout.

The layout is read as the Layout Planner or the Combiner wrote it
(``output/layout.json`` or the ``layout`` part of ``output/combined.json``,
schema: ``layout_to_dict``); the current farm is the ``current`` list of the
farm map. Layout Edit Mode can store every movable item, so no move order is
needed: keep what already stands exactly at a target, store everything else,
then place the remaining targets block by block.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.layout.farm_map import CurrentItem, FarmMap
from src.loaders.json_loader import DataSet
from src.models import Area

RectT = tuple[int, int, int, int]


@dataclass(frozen=True)
class Target:
    """One item of the layout: where a copy of *location_id* should stand."""

    block_id: str
    block_name: str
    location_id: str
    rect: RectT
    rotated: bool = False
    reserved: bool = False


@dataclass
class RelocationPlan:
    level: int | None
    keep: list[Target]
    store: list[CurrentItem]
    place: list[Target]
    reserved: list[Target]
    surplus: dict[str, int]  # current copies the layout has no place for
    missing: dict[str, int]  # layout copies the current farm does not have
    current_copies: int
    blocks: list[tuple[str, str]] = field(default_factory=list)  # (id, name) order

    @property
    def stored_placed(self) -> int:
        """Stored items that stand on the farm now (one action each)."""
        return sum(1 for c in self.store if c.is_placed)

    @property
    def new_slot_simpler(self) -> bool:
        """
        A new layout slot starts empty: every target is placed, nothing stored.
        Editing the current layout stores the moved items first, so the new slot
        needs fewer actions when fewer items stay than have to be stored.
        """
        return len(self.keep) < self.stored_placed


def load_layout(path: Path | str) -> dict[str, Any]:
    """The layout part of a ``layout.json`` or ``combined.json`` file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}  # a list or a value: reported as not a layout below
    layout = data.get("layout") if isinstance(data.get("layout"), dict) else data
    if not isinstance(layout.get("blocks"), list) or "map" not in layout:
        raise ValueError(f"Not a layout.json or combined.json file: {path}")
    return layout


def check_layout_map(layout: dict[str, Any], farm_map: FarmMap) -> list[str]:
    """Problems when the layout was not planned on this farm map."""
    m = layout["map"]
    again = "plan again with this farm map"
    if not m.get("bounded"):
        return [f"The layout was planned without a farm map; {again}"]
    if not farm_map.bounded:
        return [
            (
                "The farm map has no size (width / height); measure it in "
                "tools/farm_map_editor.html"
            )
        ]
    if (m.get("width"), m.get("height")) != (farm_map.width, farm_map.height):
        size = f"{m.get('width')}x{m.get('height')}"
        here_size = f"{farm_map.width}x{farm_map.height}"
        return [
            f"The layout was planned on a {size} map, this one is {here_size}; {again}"
        ]
    here = {f.id: (f.x, f.y, f.width, f.height) for f in farm_map.placed_fixed}
    moved = [
        f["id"]
        for f in layout.get("fixed", [])
        if f.get("x") is not None
        and f["id"] in here
        and here[f["id"]] != (f["x"], f["y"], f["width"], f["height"])
    ]
    if moved:
        return [f"Fixed buildings stand elsewhere on the farm map: {', '.join(moved)}"]
    return []


def check_current(farm_map: FarmMap, dataset: DataSet) -> list[str]:
    """Unknown ids, items that are not movable farm items, wrong sizes."""
    problems: list[str] = []
    for c in farm_map.current:
        loc = dataset.locations.get(c.id)
        if loc is None:
            problems.append(f"Unknown current item id '{c.id}'")
            continue
        if loc.area != Area.FARM or not loc.movable:
            problems.append(f"Current item '{c.id}' is not a movable farm item")
            continue
        if not c.is_placed or loc.footprint_width is None:
            continue
        size, foot = (c.width, c.height), (loc.footprint_width, loc.footprint_height)
        if size == foot or (loc.rotatable and size == foot[::-1]):
            continue
        turn = " (or rotated)" if loc.rotatable else ""
        problems.append(
            f"Current item '{c.id}' at ({c.x}, {c.y}) is {size[0]}x{size[1]}, "
            f"its footprint is {foot[0]}x{foot[1]}{turn}"
        )
    return problems


def layout_targets(layout: dict[str, Any]) -> list[Target]:
    return [
        Target(
            block_id=b["id"],
            block_name=b.get("name") or b["id"],
            location_id=i["location_id"],
            rect=(i["x"], i["y"], i["width"], i["height"]),
            rotated=bool(i.get("rotated")),
            reserved=bool(i.get("reserved")),
        )
        for b in layout["blocks"]
        for i in b.get("items", [])
    ]


def plan_relocation(
    layout: dict[str, Any], farm_map: FarmMap, dataset: DataSet
) -> RelocationPlan:
    """
    Keep / store / place lists that turn the current farm into *layout*.

    Raises ValueError when the layout belongs to another map or a current item
    is unknown, not movable or of the wrong size.
    """
    problems = check_layout_map(layout, farm_map) + check_current(farm_map, dataset)
    if problems:
        raise ValueError("; ".join(problems))

    targets = layout_targets(layout)
    owned = [t for t in targets if not t.reserved]
    # keep: a current copy at exactly the place of a target of the same id
    free: dict[tuple[str, RectT], list[Target]] = defaultdict(list)
    for t in owned:
        free[(t.location_id, t.rect)].append(t)
    keep: list[Target] = []
    store: list[CurrentItem] = []
    for c in farm_map.current:
        slot = free.get((c.id, (c.x, c.y, c.width, c.height))) if c.is_placed else None
        if slot:
            keep.append(slot.pop(0))
        else:
            store.append(c)
    kept = {id(t) for t in keep}
    place = [t for t in owned if id(t) not in kept]

    have: Counter[str] = Counter()
    for c in farm_map.current:
        have[c.id] += c.count
    want = Counter(t.location_id for t in owned)
    return RelocationPlan(
        level=layout.get("level"),
        keep=keep,
        store=sorted(store, key=lambda c: (c.id, c.x is None, c.x or 0, c.y or 0)),
        place=place,
        reserved=[t for t in targets if t.reserved],
        surplus=dict(sorted((have - want).items())),
        missing=dict(sorted((want - have).items())),
        current_copies=have.total(),
        blocks=[(b["id"], b.get("name") or b["id"]) for b in layout["blocks"]],
    )
