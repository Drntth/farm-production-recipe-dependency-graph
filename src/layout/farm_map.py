"""
Farm map - the player's usable farm area and the fixed buildings on it.

Every farm has different expansions and a different spot for the farmhouse,
barn, silo, mine, …, so the map is player data in ``config/``. A local
``config/farm_map.json`` (git-ignored) takes precedence over the committed
``config/farm_map.example.json``.

Coordinates are tiles. ``x`` runs along the ↘ edge (footprint width) and ``y``
along the ↙ edge (footprint height), seen from the farm's top corner (0, 0).
``null`` means "not measured yet": a map without ``width`` / ``height`` is
unbounded, and a fixed item without a position is listed but not drawn.

The map editor (``tools/farm_map_editor.html``) writes this file from a
screenshot of the empty farm: ``background`` holds the image and its grid
calibration, ``expansions`` the farm plots drawn as tile rectangles. When any
drawn plot is marked ``unlocked``, the layout only uses unlocked plots; plots
without cells are ignored.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

CONFIG_DIR = Path("config")
LOCAL_MAP = CONFIG_DIR / "farm_map.json"
EXAMPLE_MAP = CONFIG_DIR / "farm_map.example.json"


class FixedItem(BaseModel):
    """A building the layout planner never moves (farmhouse, barn, mine, …)."""

    id: str = Field(..., description="Snake_case id; a location id if it is one")
    name: str | None = None
    x: int | None = Field(None, ge=0)
    y: int | None = Field(None, ge=0)
    width: int | None = Field(None, ge=1, description="Tiles along the ↘ edge")
    height: int | None = Field(None, ge=1, description="Tiles along the ↙ edge")

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(f"Fixed item id must be lower-case snake_case, got: {v!r}")
        return v

    @model_validator(mode="after")
    def position_is_complete(self) -> FixedItem:
        values = (self.x, self.y, self.width, self.height)
        if any(v is None for v in values) and any(v is not None for v in values):
            raise ValueError(
                f"Fixed item '{self.id}' must set x, y, width and height, or none of them"
            )
        return self

    @property
    def is_placed(self) -> bool:
        return self.x is not None

    @property
    def label(self) -> str:
        return self.name or self.id.replace("_", " ").capitalize()

    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class Background(BaseModel):
    """
    Screenshot of the empty farm and its grid calibration.

    Pixel of tile corner (x, y) = ``origin_px + x * x_axis_px + y * y_axis_px``.
    """

    image: str = Field(..., description="Image path, relative to the farm map file")
    image_width: int = Field(..., ge=1)
    image_height: int = Field(..., ge=1)
    origin_px: tuple[float, float] = Field(..., description="Top corner of tile (0, 0)")
    x_axis_px: tuple[float, float] = Field(..., description="Pixel step of one tile along x (↘)")
    y_axis_px: tuple[float, float] = Field(..., description="Pixel step of one tile along y (↙)")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def axes_independent(self) -> Background:
        (a, b), (c, d) = self.x_axis_px, self.y_axis_px
        if abs(a * d - b * c) < 1e-9:
            raise ValueError("Background calibration axes are parallel")
        return self


class Expansion(BaseModel):
    """A farm plot (wiki: Expansion/Farm), drawn as a union of tile rectangles."""

    id: str = Field(..., description="e.g. 'main_12'")
    section: str = Field(..., description="base, main, second, special, upper, lower, …")
    number: int | None = Field(None, ge=0, description="Plot number on the wiki map")
    unlocked: bool = False
    cells: list[tuple[int, int, int, int]] = Field(
        default_factory=list, description="Tile rectangles [x, y, width, height]"
    )

    model_config = {"extra": "forbid"}

    @field_validator("id", "section")
    @classmethod
    def must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(f"Expansion id / section must be lower-case snake_case, got: {v!r}")
        return v

    @field_validator("cells")
    @classmethod
    def cells_are_valid(cls, v: list[tuple[int, int, int, int]]) -> list:
        for x, y, w, h in v:
            if x < 0 or y < 0 or w < 1 or h < 1:
                raise ValueError(f"Invalid expansion cell {[x, y, w, h]}")
        return v

    def tiles(self) -> set[tuple[int, int]]:
        return {
            (x + i, y + j) for x, y, w, h in self.cells for i in range(w) for j in range(h)
        }


class FarmMap(BaseModel):
    width: int | None = Field(None, ge=1, description="Usable tiles along the ↘ edge")
    height: int | None = Field(None, ge=1, description="Usable tiles along the ↙ edge")
    background: Background | None = None
    fixed: list[FixedItem] = Field(default_factory=list)
    expansions: list[Expansion] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
    _base_dir: Path = PrivateAttr(default_factory=Path)

    @model_validator(mode="after")
    def check_map(self) -> FarmMap:
        if (self.width is None) != (self.height is None):
            raise ValueError("Farm map must set both width and height, or neither")
        ids = [f.id for f in self.fixed]
        if len(ids) != len(set(ids)):
            raise ValueError("Farm map contains duplicate fixed item ids")
        exp_ids = [e.id for e in self.expansions]
        if len(exp_ids) != len(set(exp_ids)):
            raise ValueError("Farm map contains duplicate expansion ids")
        if self.background is not None and not self.bounded:
            raise ValueError("A farm map with a background must set width and height")
        if self.bounded:
            for f in self.placed_fixed:
                if f.x + f.width > self.width or f.y + f.height > self.height:
                    raise ValueError(f"Fixed item '{f.id}' lies outside the farm map")
            for e in self.expansions:
                for x, y, w, h in e.cells:
                    if x + w > self.width or y + h > self.height:
                        raise ValueError(f"Expansion '{e.id}' lies outside the farm map")
        return self

    def usable_tiles(self) -> set[tuple[int, int]] | None:
        """Tiles of the unlocked plots, or None if no drawn plot is marked unlocked."""
        # an unlocked plot without cells (not drawn yet) must not block the whole map
        unlocked = [e for e in self.expansions if e.unlocked and e.cells]
        if not unlocked:
            return None
        return set().union(*(e.tiles() for e in unlocked))

    def background_path(self) -> Path | None:
        if self.background is None:
            return None
        return (self._base_dir / self.background.image).resolve()

    @property
    def bounded(self) -> bool:
        return self.width is not None

    @property
    def placed_fixed(self) -> list[FixedItem]:
        return [f for f in self.fixed if f.is_placed]


def default_map_path() -> Path:
    return LOCAL_MAP if LOCAL_MAP.exists() else EXAMPLE_MAP


def load_farm_map(path: Path | str | None = None) -> FarmMap:
    """Load the farm map from *path* or the default location; empty map if none."""
    p = Path(path) if path is not None else default_map_path()
    if not p.exists():
        if path is not None:
            raise FileNotFoundError(f"Farm map not found: {p}")
        return FarmMap()
    farm_map = FarmMap.model_validate(json.loads(p.read_text(encoding="utf-8")))
    farm_map._base_dir = p.parent
    return farm_map
