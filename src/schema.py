"""
Input file versions: ``schema_version`` and the migrations between versions.

Every input JSON (player profile, settings, design template, farm maps, farm
profile, data bundle) may carry ``"schema_version": N``. A file without it is
version 1, the format of v1.6. On load, :func:`upgrade` runs the migrations
from the file's version to the current one and drops the key, so the models
never see it and the tool outputs do not change. Writers put it back with
:func:`stamp`.

A format change bumps ``CURRENT[kind]`` and registers one function in
``MIGRATIONS[kind][old_version]`` that turns the old JSON object into the next
version.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

Json = dict[str, Any]
Migration = Callable[[Json], Json]

KEY = "schema_version"
# kind -> current version
CURRENT: dict[str, int] = {
    "player": 1,
    "design": 1,
    "planner": 2,
    "template": 1,
    "farm_map": 1,
    "base_map": 1,
    "profile_map": 1,
    "farm_profile": 1,
    "data_bundle": 1,
    # outputs read by the web site (python -m src recommend)
    "recommendation": 2,  # v2.3: login times instead of the login interval
    "recommendation_index": 2,  # v2.3: logins_per_day instead of the interval
    "recommendation_map": 1,
}


def _planner_1_to_2(data: Json) -> Json:
    """
    v2.3: ``production.login_window`` replaces ``production.login_interval``.

    An interval that divides the day becomes the same logins round the clock
    (``00:00``-``00:00``, ``24 / interval`` logins); otherwise, or when a login
    window is already set, it is dropped with a warning.
    """
    production = data.get("production")
    if not isinstance(production, dict) or "login_interval" not in production:
        return data
    rest = {k: v for k, v in production.items() if k != "login_interval"}
    interval = production["login_interval"]
    if interval is None:
        return data | {"production": rest}
    logins = 24 / interval if isinstance(interval, (int, float)) and interval > 0 else 0
    # 48: MAX_LOGINS_PER_DAY of src/settings.py (which imports this module)
    if "login_window" not in rest and logins.is_integer() and 1 <= logins <= 48:
        window = {"start": "00:00", "end": "00:00", "logins": int(logins)}
        return data | {"production": rest | {"login_window": window}}
    logger.warning(
        "Planner settings: login_interval %s is no longer used; set "
        "production.login_window (start, end, logins) instead",
        interval,
    )
    return data | {"production": rest}


# kind -> {version: migration to version + 1}
MIGRATIONS: dict[str, dict[int, Migration]] = {"planner": {1: _planner_1_to_2}}


def upgrade(
    kind: str,
    data: Json,
    *,
    current: dict[str, int] = CURRENT,
    migrations: dict[str, dict[int, Migration]] = MIGRATIONS,
) -> Json:
    """*data* migrated to the current version of *kind*, without the key."""
    target = current[kind]
    rest = {k: v for k, v in data.items() if k != KEY}
    version = data.get(KEY, 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError(f"{KEY} must be a positive integer, got {version!r}")
    if version > target:
        raise ValueError(
            f"{kind} file has {KEY} {version}, this version reads up to {target}; "
            "update the tools"
        )
    steps = migrations.get(kind, {})
    while version < target:
        if version not in steps:
            raise ValueError(f"No migration for {kind} from {KEY} {version}")
        rest = steps[version](rest)
        version += 1
    return rest


def stamp(kind: str, data: Json) -> Json:
    """*data* with the current ``schema_version`` of *kind* as its first key."""
    return {KEY: CURRENT[kind]} | {k: v for k, v in data.items() if k != KEY}


class Versioned(BaseModel):
    """A model read from an input file: accepts and upgrades ``schema_version``."""

    schema_kind: ClassVar[str]  # a key of CURRENT

    @model_validator(mode="before")
    @classmethod
    def _upgrade(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return upgrade(cls.schema_kind, data)
        return data
