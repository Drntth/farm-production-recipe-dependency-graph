"""
Level recommendations without file IO.

A level recommendation is the combined plan (production plan + farm layout
sized by it) of a player who bought nothing beyond the level: the
level-default profile of ``src/planner/examples.py``, the built-in design and
planner settings, laid out on the base map with only section ``base``
unlocked (the plot recommendation comes later). Blocks that do not fit there
are listed in ``blocks_not_placed``.

Files per run, paths relative to the output directory::

    level_<N>.json   {"schema_version", "level", "game_version",
                      "core_version", "blocks_not_placed", "combined"}
    level_<N>.svg    the layout drawn by the core (combined.svg)
    index.json       {"schema_version", "game_version", "core_version",
                      "levels": [{"level", "blocks", "blocks_not_placed",
                                  "logins_per_day"}, ...]}
    map.json         {"schema_version", "width", "height", "usable",
                      "usable_bounds", "farm_outline", "fixed"}: the map
                      every level is laid out on (the farm view of the site)
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from src.api.core import COMBINED_STEM, combined_plan
from src.layout.farm_map import (
    BaseMap,
    FarmMap,
    ProfileMap,
    Tile,
    merge_maps,
    outline_segments,
)
from src.loaders.json_loader import DataSet
from src.planner.examples import example_profile
from src.schema import stamp
from src.settings import DesignSettings, PlannerSettings

Json = dict[str, Any]

DEFAULT_LEVELS = tuple(range(1, 101))
INDEX = "index.json"
MAP = "map.json"


def _dump(payload: Json) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def base_farm_map(base: BaseMap) -> FarmMap:
    """The base map with an empty profile map: only section ``base`` unlocked."""
    return merge_maps(base, ProfileMap())


def tile_rects(tiles: set[Tile]) -> list[list[int]]:
    """
    *tiles* as ``[x, y, w, h]`` rectangles: runs along x, equal runs of
    consecutive rows merged. Deterministic; not the fewest rectangles.
    """
    runs: dict[int, list[tuple[int, int]]] = {}
    for y in sorted({y for _, y in tiles}):
        xs = sorted(x for x, ty in tiles if ty == y)
        start = prev = xs[0]
        for x in [*xs[1:], None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.setdefault(y, []).append((start, prev - start + 1))
            if x is not None:
                start = prev = x
    open_rects: dict[tuple[int, int], list[int]] = {}  # (x, w) -> rect
    rects: list[list[int]] = []
    for y in sorted(runs):
        current = set(runs[y])
        for key in list(open_rects):
            rect = open_rects[key]
            if key in current and rect[1] + rect[3] == y:
                rect[3] += 1
                current.discard(key)
            else:
                rects.append(open_rects.pop(key))
        for x, w in sorted(current):
            open_rects[x, w] = [x, y, w, 1]
    rects.extend(open_rects.values())
    return sorted(rects, key=lambda r: (r[1], r[0]))


def map_view(farm_map: FarmMap) -> Json:
    """
    The map every level recommendation is laid out on, for the farm view:
    usable tiles (section ``base``, buildable minus blocked zones) as
    rectangles and their bounds, the outline of every farm section (shown
    faint) and the fixed buildings.
    """
    usable = farm_map.usable_tiles() or set()
    bounds = None
    if usable:
        xs, ys = [x for x, _ in usable], [y for _, y in usable]
        bounds = [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]
    return stamp(
        "recommendation_map",
        {
            "width": farm_map.width,
            "height": farm_map.height,
            "usable": tile_rects(usable) if usable else [],
            "usable_bounds": bounds,
            "farm_outline": [
                [a[0], a[1], b[0], b[1]]
                for a, b in outline_segments(farm_map.farm_tiles())
            ],
            "fixed": [
                {"id": f.id, "name": f.label, "x": f.x, "y": f.y}
                | {"width": f.width, "height": f.height}
                for f in farm_map.placed_fixed
            ],
        },
    )


def level_name(level: int) -> str:
    return f"level_{level}"


def level_recommendation(
    data: DataSet,
    farm_map: FarmMap,
    level: int,
    *,
    game_version: str | None = None,
    core_version: str | None = None,
    data_max_level: int | None = None,
) -> Json:
    """``{"result": <level JSON>, "files": {"level_<N>.json", "level_<N>.svg"}}``."""
    run = combined_plan(
        data,
        player=example_profile(data, level),
        farm_map=farm_map,
        design=DesignSettings(block_images=False),
        planner=PlannerSettings(),
        templates={},
        data_max_level=data_max_level,
    )
    combined = run["result"]
    result = stamp(
        "recommendation",
        {
            "level": level,
            "game_version": game_version,
            "core_version": core_version,
            "blocks_not_placed": combined["summary"]["blocks_not_placed"],
            "combined": combined,
        },
    )
    name = level_name(level)
    return {
        "result": result,
        "files": {
            f"{name}.json": _dump(result),
            f"{name}.svg": run["files"][f"{COMBINED_STEM}.svg"],
        },
    }


def recommendations(
    data: DataSet,
    base: BaseMap,
    levels: Iterable[int] = DEFAULT_LEVELS,
    *,
    game_version: str | None = None,
    core_version: str | None = None,
    data_max_level: int | None = None,
) -> Json:
    """Every level of *levels* plus ``index.json``; same shape as one level."""
    farm_map = base_farm_map(base)
    files: dict[str, str] = {}
    rows = []
    for level in sorted(set(levels)):
        if data_max_level is not None and level > data_max_level:
            raise ValueError(f"Level {level} is above the data ({data_max_level})")
        one = level_recommendation(
            data,
            farm_map,
            level,
            game_version=game_version,
            core_version=core_version,
            data_max_level=data_max_level,
        )
        files |= one["files"]
        summary = one["result"]["combined"]["summary"]
        rows.append(
            {
                "level": level,
                "blocks": summary["blocks"],
                "blocks_not_placed": len(summary["blocks_not_placed"]),
                "logins_per_day": summary["logins_per_day"],
            }
        )
    index = stamp(
        "recommendation_index",
        {"game_version": game_version, "core_version": core_version, "levels": rows},
    )
    files[INDEX] = _dump(index)
    files[MAP] = _dump(map_view(farm_map))
    return {"result": index, "files": files}
