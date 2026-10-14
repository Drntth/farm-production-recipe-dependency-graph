"""
Tool settings: how the layout looks and how production is planned.

Settings live only in config files, never in CLI options (the CLI says what
to run: area, level, file paths). Two file pairs, like the player profile: a
committed ``*.example.json`` and a local, git-ignored copy that wins:

- ``config/design.json``: Layout Planner and design layer, a ``default``
  section plus optional ``farm`` / ``town`` / ``fishing_lake`` sections that
  set only what differs. Farm-only keys (``reserve``, ``strategy``,
  ``field_pool``) are not allowed in the town and fishing lake sections.
- ``config/planner.json``: Production Planner (``production``) and Combiner
  (``combiner``), farm only.

A missing file means the built-in defaults below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models import Area

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
DEFAULT_PATH_TARGETS = "blocks"
DEFAULT_ITEM_GAP = 0

Strategy = Literal["auto", "coupling", "size", "flow", "all"]
CombinerStrategy = Literal["auto", "coupling", "size", "flow"]
PathStyle = Literal["shortest", "straight"]
PathTargets = Literal["blocks", "buildings"]
FARM_ONLY = ("reserve", "strategy", "field_pool", "item_gap", "path_targets")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DesignSection(_Strict):
    """One section of design.json; ``None`` = not set here."""

    gap: int | None = Field(None, ge=0, description="Free tiles between blocks")
    design_layer: bool | None = Field(
        None, description="Paths and decoration band (gap is then at least 1)"
    )
    decor_band: int | None = Field(
        None, ge=0, description="Decoration band width in tiles next to the paths"
    )
    reserve: float | None = Field(
        None, ge=0, description="Farm: extra free area per block for later unlocks"
    )
    strategy: Strategy | None = Field(
        None,
        description="Farm: block order; all = one output set per order",
    )
    field_pool: float | None = Field(
        None, ge=0, le=1, description="Farm: share of fields in a shared block"
    )
    item_gap: int | None = Field(
        None, ge=0, description="Farm: free tiles between the buildings of a block"
    )
    path_style: PathStyle | None = Field(
        None, description="shortest, or straight (fewer corners and detours)"
    )
    path_targets: PathTargets | None = Field(
        None,
        description="Farm: paths to blocks and key buildings, or to every "
        "building (needs item_gap >= 1)",
    )
    design_zones: bool | None = Field(
        None, description="Keep the map's design zones free of blocks"
    )


class AreaDesign(_Strict):
    """Resolved design settings of one area."""

    gap: int = DEFAULT_GAP
    design_layer: bool = False
    decor_band: int = DEFAULT_DECOR_BAND
    reserve: float = DEFAULT_RESERVE
    strategy: Strategy = DEFAULT_STRATEGY
    field_pool: float = DEFAULT_FIELD_POOL
    item_gap: int = DEFAULT_ITEM_GAP
    path_style: PathStyle = DEFAULT_PATH_STYLE
    path_targets: PathTargets = DEFAULT_PATH_TARGETS
    design_zones: bool = True

    @model_validator(mode="after")
    def buildings_need_room(self) -> AreaDesign:
        # same rule as plan_layout: it matters only with the design layer on
        if self.design_layer and self.path_targets == "buildings" and self.item_gap < 1:
            raise ValueError("path_targets 'buildings' needs item_gap >= 1")
        return self

    def used(self, area: Area) -> dict:
        """The settings that apply to *area* (farm-only keys only on the farm)."""
        values = self.model_dump()
        if area != Area.FARM:
            values = {k: v for k, v in values.items() if k not in FARM_ONLY}
        return values


class DesignSettings(_Strict):
    default: DesignSection = Field(default_factory=DesignSection)
    farm: DesignSection = Field(default_factory=DesignSection)
    town: DesignSection = Field(default_factory=DesignSection)
    fishing_lake: DesignSection = Field(default_factory=DesignSection)

    @model_validator(mode="after")
    def farm_only_keys(self) -> DesignSettings:
        for area in ("town", "fishing_lake"):
            section = getattr(self, area)
            used = [k for k in FARM_ONLY if getattr(section, k) is not None]
            if used:
                raise ValueError(f"{area}: farm-only settings {', '.join(used)}")
        self.for_area(Area.FARM)  # cross-key rules of the resolved farm settings
        return self

    def for_area(self, area: Area) -> AreaDesign:
        """
        Built-in defaults, then ``default``, then the area's own section.

        Farm-only keys of ``default`` apply to the farm only.
        """
        values: dict = {}
        for section in (self.default, getattr(self, area.value)):
            values |= section.model_dump(exclude_none=True)
        if area != Area.FARM:
            values = {k: v for k, v in values.items() if k not in FARM_ONLY}
        return AreaDesign(**values)


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
