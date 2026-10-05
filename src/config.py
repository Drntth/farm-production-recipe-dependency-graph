"""
Player configuration (player profile).

Static, player-specific settings shared by the scraper and all planners:
everything the player buys, upgrades or earns rather than unlocks by level.
A local ``config/player.json`` (git-ignored) takes precedence over the
committed ``config/player.example.json``.

Every progress field is optional; ``null`` means "unknown, use the default
derived from the level and the shared data" (see docs/player-profile.md).
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.models import LocationType

if TYPE_CHECKING:
    from src.loaders.json_loader import DataSet

CONFIG_DIR = Path("config")
LOCAL_CONFIG = CONFIG_DIR / "player.json"
EXAMPLE_CONFIG = CONFIG_DIR / "player.example.json"


class MasterySystem(str, Enum):
    """Machine mastery mechanic active for the player (see README update checklist)."""

    STARS = "stars"  # classic 3-star mastery
    WORKBENCH = "workbench"  # Building Mastery / Workbench (v1.72+)


class LocationProgress(BaseModel):
    """
    The player's state of one location type (all fields optional).

    Counts are totals over all copies: two feed mills with 6 slots each are
    ``slots: 12``; three full chicken coops are ``animals: 18``. Mastery is
    per building type, because copies share their production hours (wiki).
    """

    owned: int | None = Field(
        None, ge=0, description="Copies placed (default: all copies unlocked at the level)"
    )
    slots: int | None = Field(
        None, ge=1, description="Production slots unlocked, summed over all copies"
    )
    mastery_stars: int | None = Field(None, ge=0, le=3, description="3-star mastery")
    workbench_level: int | None = Field(None, ge=0, description="Workbench mastery")
    animals: int | None = Field(
        None, ge=0, description="Animals in all shelters of this type"
    )
    beehives: int | None = Field(
        None, ge=1, le=4, description="Beehives on the beehive tree (wiki: 1-4)"
    )

    model_config = {"extra": "forbid"}


class PlayerConfig(BaseModel):
    level: int = Field(..., ge=1, description="Current player experience level")
    mastery_system: MasterySystem = MasterySystem.STARS
    # Upgraded with supplies, not by level, so they are player progress.
    barn_capacity: int | None = Field(None, ge=1)
    silo_capacity: int | None = Field(None, ge=1)
    fields_owned: int | None = Field(
        None, ge=0, description="Fields placed (default / null: planner recommends)"
    )
    fishing_spots_unlocked: int | None = Field(None, ge=0)
    locations: dict[str, LocationProgress] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


_NO_SLOT_TYPES = {LocationType.FIELD, LocationType.TREE, LocationType.BUSH}


def default_config_path() -> Path:
    return LOCAL_CONFIG if LOCAL_CONFIG.exists() else EXAMPLE_CONFIG


def load_player_config(path: Path | str | None = None) -> PlayerConfig:
    """Load and validate the player config from *path* or the default location."""
    p = Path(path) if path is not None else default_config_path()
    if not p.exists():
        raise FileNotFoundError(f"Player config not found: {p}")
    return PlayerConfig.model_validate(json.loads(p.read_text(encoding="utf-8")))


def validate_player_config(cfg: PlayerConfig, dataset: DataSet) -> list[str]:
    """
    Check the profile against the shared data; return human-readable problems.

    *dataset* should be the full (unfiltered) data so that locations unlocked
    above the player level are reported as such rather than as unknown.
    """
    problems: list[str] = []
    limits = dataset.level_limits

    if limits is not None and cfg.fields_owned is not None:
        granted = limits.fields_at(cfg.level)
        if cfg.fields_owned > granted:
            problems.append(
                f"fields_owned={cfg.fields_owned} exceeds the {granted} fields "
                f"available at level {cfg.level}"
            )

    for loc_id, progress in cfg.locations.items():
        loc = dataset.locations.get(loc_id)
        if loc is None:
            problems.append(f"locations.{loc_id}: unknown location id")
            continue
        if loc.unlock_level > cfg.level:
            problems.append(
                f"locations.{loc_id}: unlocks at level {loc.unlock_level}, "
                f"player is level {cfg.level}"
            )
        has_rows = limits is not None and any(
            i.location_id == loc_id for i in limits.location_instances
        )
        available = limits.instances_at(loc_id, cfg.level) if has_rows else None
        if progress.owned is not None and available is not None:
            if progress.owned > available:
                problems.append(
                    f"locations.{loc_id}: owned={progress.owned} exceeds the "
                    f"{available} copies available at level {cfg.level}"
                )
        if progress.slots is not None and loc.type in _NO_SLOT_TYPES:
            problems.append(f"locations.{loc_id}: slots do not apply to {loc.type.value}")
        if progress.animals is not None:
            copies = progress.owned if progress.owned is not None else available
            if loc.animal_capacity is None:
                problems.append(
                    f"locations.{loc_id}: animals only apply to shelters with a "
                    "known animal_capacity"
                )
            elif copies is not None and progress.animals > copies * loc.animal_capacity:
                problems.append(
                    f"locations.{loc_id}: animals={progress.animals} exceeds "
                    f"{copies} x {loc.animal_capacity} places"
                )
        if progress.mastery_stars is not None and cfg.mastery_system != MasterySystem.STARS:
            problems.append(
                f"locations.{loc_id}: mastery_stars set but mastery_system is "
                f"{cfg.mastery_system.value}"
            )
        if (
            progress.workbench_level is not None
            and cfg.mastery_system != MasterySystem.WORKBENCH
        ):
            problems.append(
                f"locations.{loc_id}: workbench_level set but mastery_system is "
                f"{cfg.mastery_system.value}"
            )
    return problems
