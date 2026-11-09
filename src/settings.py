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

from src.schema import Versioned

CONFIG_DIR = Path("config")

# built-in defaults; the tools take their defaults from here
DEFAULT_GAP = 1
DEFAULT_RESERVE = 0.2
DEFAULT_FIELD_POOL = 0.0
DEFAULT_STRATEGY = "auto"
DEFAULT_DECOR_BAND = 1
DEFAULT_STORAGE_SHARE = 0.5
DEFAULT_MIN_EFFICIENCY = 0.8
DEFAULT_LOGIN_START = "07:00"
DEFAULT_LOGIN_END = "23:00"
MAX_LOGINS_PER_DAY = 48
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
TemplateMode = Literal["reserve", "arrange"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateAssignment(_Strict):
    """One block's design template (``templates`` in config/design.json)."""

    template: str = Field(..., description="config/templates/<template>.json")
    mode: TemplateMode = Field(
        "reserve",
        description="reserve: keep the template area free; arrange: its "
        "buildings at their template positions",
    )


class DesignSettings(Versioned, _Strict):
    """config/design.json: Layout Planner and design layer of the farm."""

    schema_kind = "design"

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
    templates: dict[str, TemplateAssignment] = Field(
        default_factory=dict, description="Block id -> design template"
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


_CLOCK = r"^([01]\d|2[0-3]):[0-5]\d$"
_DAY_MINUTES = 24 * 60


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _clock(minutes: float) -> str:
    m = round(minutes) % _DAY_MINUTES
    return f"{m // 60:02d}:{m % 60:02d}"


class LoginWindow(_Strict):
    """
    The player's daily active hours and logins spread evenly in them.

    The first login is at ``start``, the last at ``end``; the night outside
    the window is one long gap. ``start == end`` means round the clock: the
    logins split the whole day evenly. A window may pass midnight (22:00-02:00).
    """

    start: str = Field(DEFAULT_LOGIN_START, pattern=_CLOCK, description="First login")
    end: str = Field(DEFAULT_LOGIN_END, pattern=_CLOCK, description="Last login")
    logins: int | None = Field(
        None,
        ge=1,
        le=MAX_LOGINS_PER_DAY,
        description="Logins per day; null = suggested",
    )

    def window_hours(self) -> float:
        """Hours from the first to the last login (0 = round the clock)."""
        return ((_minutes(self.end) - _minutes(self.start)) % _DAY_MINUTES) / 60

    def gaps(self, logins: int) -> list[float]:
        """Hours from each login to the next one, in order; the sum is 24."""
        if not 1 <= logins <= MAX_LOGINS_PER_DAY:
            raise ValueError(f"logins must be 1-{MAX_LOGINS_PER_DAY}, got {logins}")
        window = self.window_hours()
        if logins == 1 or window == 0:
            return [24 / logins] * logins
        return [window / (logins - 1)] * (logins - 1) + [24 - window]

    def times(self, logins: int) -> list[str]:
        """
        Clock times (``HH:MM``) of the logins of one day; rounded down to the
        minute, so logins less than a minute apart (a very short window with
        many logins) share a time.
        """
        at, out = float(_minutes(self.start)), []
        for gap in self.gaps(logins):
            out.append(_clock(at))
            at += gap * 60
        return out


class ProductionSettings(_Strict):
    login_window: LoginWindow = Field(default_factory=LoginWindow)
    storage_share: float = Field(
        DEFAULT_STORAGE_SHARE,
        gt=0,
        le=1,
        description="Share of barn and silo the goods of one login gap may fill",
    )
    min_efficiency: float = Field(
        DEFAULT_MIN_EFFICIENCY,
        gt=0,
        le=1,
        description="Suggested logins keep at least this share of the best",
    )


class CombinerSettings(_Strict):
    lookahead: int = Field(
        DEFAULT_LOOKAHEAD, ge=0, description="Levels ahead whose unlocks get space"
    )
    strategy: CombinerStrategy = Field(
        DEFAULT_COMBINER_STRATEGY,
        description="Block order of the combined layout (overrides design.json)",
    )


class PlannerSettings(Versioned, _Strict):
    schema_kind = "planner"

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
