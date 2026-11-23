"""
Browser glue: the Core API calls the web worker (Pyodide) makes.

Both functions take the data bundle as a parsed object and return plain
dicts, so the worker only moves JSON strings across the Python / JS border.
"""

from __future__ import annotations

import logging
from typing import Any

from src.api.core import production_plan
from src.farm_profile import FarmProfile
from src.loaders.json_loader import dataset_from_bundle
from src.planner.examples import example_profile

Json = dict[str, Any]


class _Collector(logging.Handler):
    """Collects the warnings of the ``src.*`` loggers as ``"logger: message"``."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.warnings: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.warnings.append(f"{record.name}: {record.getMessage()}")


def plan_farm_profile(bundle: Json, profile: Json) -> Json:
    """
    Production plan of a farm profile JSON object.

    Returns ``{"result", "files", "warnings"}``: the ``production_plan``
    result and a list of the warnings logged while planning. Raises
    ``ValueError`` (including pydantic's) for an invalid profile and
    ``RuntimeError`` when the plan cannot be solved.
    """
    farm = FarmProfile.model_validate(profile)
    collector = _Collector()
    root = logging.getLogger("src")
    root.addHandler(collector)
    try:
        out = production_plan(bundle, player=farm.player, planner=farm.planner)
    finally:
        root.removeHandler(collector)
    return out | {"warnings": collector.warnings}


def level_defaults(bundle: Json, level: int) -> Json:
    """
    Form defaults of *level*: ``{"level", "profile", "locations"}``.

    ``profile`` is the level-default player profile (``example_profile``);
    ``locations`` maps each location in it to its display ``name`` and ``type``.
    """
    data = dataset_from_bundle(bundle)
    profile = example_profile(data, level)
    locations = {
        loc_id: {
            "name": data.locations[loc_id].name,
            "type": data.locations[loc_id].type.value,
        }
        for loc_id in profile["locations"]
    }
    return {"level": level, "profile": profile, "locations": locations}
