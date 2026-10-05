"""
Player configuration.

Static, player-specific settings shared by the scraper and all planners.
A local ``config/player.json`` (git-ignored) takes precedence over the
committed ``config/player.example.json``.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

CONFIG_DIR = Path("config")
LOCAL_CONFIG = CONFIG_DIR / "player.json"
EXAMPLE_CONFIG = CONFIG_DIR / "player.example.json"


class MasterySystem(str, Enum):
    """Machine mastery mechanic active for the player (see README update checklist)."""

    STARS = "stars"  # classic 3-star mastery
    WORKBENCH = "workbench"  # Building Mastery / Workbench (v1.72+)


class PlayerConfig(BaseModel):
    level: int = Field(..., ge=1, description="Current player experience level")
    mastery_system: MasterySystem = MasterySystem.STARS

    model_config = {"extra": "forbid"}


def default_config_path() -> Path:
    return LOCAL_CONFIG if LOCAL_CONFIG.exists() else EXAMPLE_CONFIG


def load_player_config(path: Path | str | None = None) -> PlayerConfig:
    """Load and validate the player config from *path* or the default location."""
    p = Path(path) if path is not None else default_config_path()
    if not p.exists():
        raise FileNotFoundError(f"Player config not found: {p}")
    return PlayerConfig.model_validate(json.loads(p.read_text(encoding="utf-8")))
