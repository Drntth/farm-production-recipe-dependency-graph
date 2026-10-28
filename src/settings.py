"""
Tool settings: how the layout looks and how production is planned.

Settings live only in config files, never in CLI options (the CLI says what
to run: level, file paths). Two file pairs, like the player profile: a
committed ``*.example.json`` and a local, git-ignored copy that wins:

- ``config/design.json``: Layout Planner and design layer, one flat object;
  a missing key means its built-in default.
- ``config/planner.json``: Production Planner (``production``) and Combiner
  (``combiner``).

A missing file means the built-in defaults below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIG_DIR = Path("config")

# built-in defaults; the tools take their defaults from here
DEFAULT_GAP = 1
DEFAULT_RESERVE = 0.2
DEFAULT_FIELD_POOL = 0.0
DEFAULT_STRATEGY = "auto"
DEFAULT_DECOR_BAND = 1
DEFAULT_STORAGE_SHARE = 0.5
DEFAULT_MIN_EFFICIENCY = 0.8
DEFAULT_LOOKAHEAD = 5
DEFAULT_COMBINER_STRATEGY = "flow"
DEFAULT_PATH_STYLE = "shortest"
DEFAULT_MAIN_PATH_WIDTH = 1
DEFAULT_PATH_TARGETS = "blocks"
DEFAULT_ITEM_GAP = 0

Strategy = Literal["auto", "coupling", "size", "flow", "all"]
CombinerStrategy = Literal["auto", "coupling", "size", "flow"]
PathStyle = Literal["shortest", "straight", "stepped"]
PathTargets = Literal["blocks", "buildings"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DesignSettings(_Strict):
    """config/design.json: Layout Planner and design layer of the farm."""

    gap: int = Field(DEFAULT_GAP, ge=0, description="Free tiles between blocks")
    design_layer: bool = Field(
        False, description="Paths and decoration band (gap is then at least 1)"
    )
    decor_band: int = Field(
        DEFAULT_DECOR_BAND,
        ge=0,
        description="Decoration band width in tiles next to the paths",
    )
    reserve: float = Field(
        DEFAULT_RESERVE, ge=0, description="Extra free area per block for later unlocks"
    )
    strategy: Strategy = Field(
        DEFAULT_STRATEGY, description="Block order; all = one output set per order"
    )
    field_pool: float = Field(
        DEFAULT_FIELD_POOL, ge=0, le=1, description="Share of fields in a shared block"
    )
    item_gap: int = Field(
        DEFAULT_ITEM_GAP,
        ge=0,
        description="Free tiles between the buildings of a block",
    )
    path_style: PathStyle = Field(
        DEFAULT_PATH_STYLE,
        description="shortest, straight (fewer corners and detours) or stepped "
        "(staircase along the straight line)",
    )
    main_path_style: PathStyle | None = Field(
        None, description="Style of the main path; null = path_style"
    )
    main_path_width: int = Field(
        DEFAULT_MAIN_PATH_WIDTH,
        ge=1,
        le=2,
        description="Main path width; narrows to 1 where 2 does not fit",
    )
    path_targets: PathTargets = Field(
        DEFAULT_PATH_TARGETS,
        description="Paths to blocks and key buildings, or to every building "
        "(needs item_gap >= 1)",
    )
    design_zones: bool = Field(
        True, description="Keep the map's design zones free of blocks"
    )
    block_images: bool = Field(
        True, description="One SVG per block and a collage of every block"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_area_sections(cls, data):
        # older design.json files had default / farm / town / fishing_lake sections
        if isinstance(data, dict):
            old = sorted({"default", "farm", "town", "fishing_lake"} & data.keys())
            if old:
                raise ValueError(
                    f"design settings are one flat object now: move the keys of "
                    f"{', '.join(old)} to the top level (town and fishing lake "
                    "are no longer laid out)"
                )
        return data

    @model_validator(mode="after")
    def buildings_need_room(self) -> DesignSettings:
        # same rule as plan_layout: it matters only with the design layer on
        if self.design_layer and self.path_targets == "buildings" and self.item_gap < 1:
            raise ValueError("path_targets 'buildings' needs item_gap >= 1")
        return self


class ProductionSettings(_Strict):
    login_interval: float | None = Field(
        None, gt=0, description="Hours between logins; null = suggested"
    )
    storage_share: float = Field(
        DEFAULT_STORAGE_SHARE,
        gt=0,
        le=1,
        description="Share of barn and silo the goods of one interval may fill",
    )
    min_efficiency: float = Field(
        DEFAULT_MIN_EFFICIENCY,
        gt=0,
        le=1,
        description="Suggested interval keeps at least this share of the best",
    )


class CombinerSettings(_Strict):
    lookahead: int = Field(
        DEFAULT_LOOKAHEAD, ge=0, description="Levels ahead whose unlocks get space"
    )
    strategy: CombinerStrategy = Field(
        DEFAULT_COMBINER_STRATEGY,
        description="Block order of the combined layout (overrides design.json)",
    )


class PlannerSettings(_Strict):
    production: ProductionSettings = Field(default_factory=ProductionSettings)
    combiner: CombinerSettings = Field(default_factory=CombinerSettings)


def settings_path(name: str) -> Path | None:
    """``config/<name>.json``, else ``config/<name>.example.json``, else None."""
    for candidate in (CONFIG_DIR / f"{name}.json", CONFIG_DIR / f"{name}.example.json"):
        if candidate.exists():
            return candidate
    return None


def _load(model: type[BaseModel], name: str, path: Path | str | None):
    p = Path(path) if path is not None else settings_path(name)
    if p is None:
        return model(), None
    if not p.exists():
        raise FileNotFoundError(f"Settings file not found: {p}")
    return model.model_validate(json.loads(p.read_text(encoding="utf-8"))), p


def load_design_settings(
    path: Path | str | None = None,
) -> tuple[DesignSettings, Path | None]:
    """Design settings and the file they came from (None = built-in defaults)."""
    return _load(DesignSettings, "design", path)


def load_planner_settings(
    path: Path | str | None = None,
) -> tuple[PlannerSettings, Path | None]:
    """Planner settings and the file they came from (None = built-in defaults)."""
    return _load(PlannerSettings, "planner", path)
