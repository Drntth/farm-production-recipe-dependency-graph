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
                                  "login_interval_hours"}, ...]}
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from src.api.core import COMBINED_STEM, combined_plan
from src.layout.farm_map import BaseMap, FarmMap, ProfileMap, merge_maps
from src.loaders.json_loader import DataSet
from src.planner.examples import example_profile
from src.schema import stamp
from src.settings import DesignSettings, PlannerSettings

Json = dict[str, Any]

DEFAULT_LEVELS = tuple(range(1, 101))
INDEX = "index.json"


def _dump(payload: Json) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def base_farm_map(base: BaseMap) -> FarmMap:
    """The base map with an empty profile map: only section ``base`` unlocked."""
    return merge_maps(base, ProfileMap())


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
                "login_interval_hours": summary["login_interval_hours"],
            }
        )
    index = stamp(
        "recommendation_index",
        {"game_version": game_version, "core_version": core_version, "levels": rows},
    )
    files[INDEX] = _dump(index)
    return {"result": index, "files": files}
