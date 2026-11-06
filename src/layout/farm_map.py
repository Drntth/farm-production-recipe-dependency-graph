"""
Farm map - the player's usable area and the fixed buildings on it.

Every farm has different expansions and a different spot for the farmhouse,
barn, silo, mine, …, so the map is player data in ``config/``. A local
``config/farm_map.json`` (git-ignored) takes precedence over the committed
``config/farm_map.example.json``. ``fixed`` holds only buildings the game
never moves; the barn, the silo and every other movable item are placed by the
planner.

Coordinates are tiles. ``x`` runs along the ↘ edge (footprint width) and ``y``
along the ↙ edge (footprint height), seen from the farm's top corner (0, 0).
``null`` means "not measured yet": a map without ``width`` / ``height`` is
unbounded, and a fixed item without a position is listed but not drawn.

The map editor (``tools/farm_map_editor.html``) writes this file from a
screenshot of the empty farm: ``background`` holds the image and its grid
calibration, ``expansions`` the farm plots drawn as tile rectangles. When any
drawn plot is marked ``unlocked``, the layout only uses unlocked plots; plots
without cells are ignored, plots of section ``base`` count as unlocked.
``zones`` mark tiles by hand: ``buildable`` zones (the farm sections) limit the
layout to them, ``blocked`` zones (water, road, forest, …) are never used,
``design`` zones (existing decorations) are kept free of blocks
(``design_zones``, on by default).
``current`` lists where the player's movable items stand now (the start of a
relocation plan, ``src/relocation``); the Layout Planner ignores it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from src.schema import Versioned, stamp

CONFIG_DIR = Path("config")
LOCAL_PROFILE_MAP = CONFIG_DIR / "profile_map.json"
LOCAL_MAP = CONFIG_DIR / "farm_map.json"  # one-file map before v2.0
EXAMPLE_MAP = CONFIG_DIR / "farm_map.example.json"
DEFAULT_BASE_MAP = Path("data") / "base_map.json"
# keys only a one-file map has (its geometry)
ONE_FILE_KEYS = frozenset({"width", "height", "fixed", "expansions"})

logger = logging.getLogger(__name__)


Tile = tuple[int, int]
Segment = tuple[Tile, Tile]


def cells_to_tiles(cells: list[tuple[int, int, int, int]]) -> set[Tile]:
    return {(x + i, y + j) for x, y, w, h in cells for i in range(w) for j in range(h)}


def outline_segments(tiles: set[Tile]) -> list[Segment]:
    """
    Border of a tile set as tile-corner segments, collinear neighbours merged.

    Inner edges between two tiles of the set are left out, so touching
    rectangles of one plot are drawn as a single shape.
    """
    edges: dict[tuple[str, int, int], list[int]] = {}
    for x, y in tiles:
        if (x, y - 1) not in tiles:
            edges.setdefault(("h", y, -1), []).append(x)
        if (x, y + 1) not in tiles:
            edges.setdefault(("h", y + 1, 1), []).append(x)
        if (x - 1, y) not in tiles:
            edges.setdefault(("v", x, -1), []).append(y)
        if (x + 1, y) not in tiles:
            edges.setdefault(("v", x + 1, 1), []).append(y)
    segments: list[Segment] = []
    for (axis, line, _side), starts in sorted(edges.items()):
        starts.sort()
        run_start = prev = starts[0]
        for s in starts[1:] + [None]:
            if s is not None and s == prev + 1:
                prev = s
                continue
            a, b = run_start, prev + 1
            segments.append(
                ((a, line), (b, line)) if axis == "h" else ((line, a), (line, b))
            )
            if s is not None:
                run_start = prev = s
    return segments


class FixedItem(BaseModel):
    """A building the game never moves (farmhouse, mine, truck, …)."""

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


class CurrentItem(BaseModel):
    """
    A movable item of the current farm: one copy at its position, or (fields,
    trees, bushes) ``count`` copies without a position.
    """

    id: str = Field(..., description="Location id")
    x: int | None = Field(None, ge=0)
    y: int | None = Field(None, ge=0)
    width: int | None = Field(None, ge=1, description="Tiles along the ↘ edge")
    height: int | None = Field(None, ge=1, description="Tiles along the ↙ edge")
    count: int = Field(1, ge=1, description="Copies; above 1 only without a position")

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"Current item id must be lower-case snake_case, got: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def position_is_complete(self) -> CurrentItem:
        values = (self.x, self.y, self.width, self.height)
        if any(v is None for v in values) and any(v is not None for v in values):
            raise ValueError(
                f"Current item '{self.id}' must set x, y, width and height, or none of them"
            )
        if self.is_placed and self.count != 1:
            raise ValueError(f"Current item '{self.id}' with a position is one copy")
        return self

    @property
    def is_placed(self) -> bool:
        return self.x is not None


class Background(BaseModel):
    """
    Screenshot of the empty farm and its grid calibration.

    Pixel of tile corner (x, y) = ``origin_px + x * x_axis_px + y * y_axis_px``.
    """

    image: str = Field(..., description="Image path, relative to the farm map file")
    image_width: int = Field(..., ge=1)
    image_height: int = Field(..., ge=1)
    origin_px: tuple[float, float] = Field(..., description="Top corner of tile (0, 0)")
    x_axis_px: tuple[float, float] = Field(
        ..., description="Pixel step of one tile along x (↘)"
    )
    y_axis_px: tuple[float, float] = Field(
        ..., description="Pixel step of one tile along y (↙)"
    )

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
    section: str = Field(
        ..., description="base, main, second, special, upper, lower, …"
    )
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
            raise ValueError(
                f"Expansion id / section must be lower-case snake_case, got: {v!r}"
            )
        return v

    @field_validator("cells")
    @classmethod
    def cells_are_valid(cls, v: list[tuple[int, int, int, int]]) -> list:
        for x, y, w, h in v:
            if x < 0 or y < 0 or w < 1 or h < 1:
                raise ValueError(f"Invalid expansion cell {[x, y, w, h]}")
        return v

    def tiles(self) -> set[tuple[int, int]]:
        return cells_to_tiles(self.cells)

    @property
    def is_unlocked(self) -> bool:
        """The starting land (section ``base``) is always owned."""
        return self.unlocked or self.section == "base"


class Zone(BaseModel):
    """
    Hand-marked tiles: ``buildable`` (a farm section), ``blocked`` (water, road,
    …) or ``design`` (existing decorations: no block, but paths may cross it).
    """

    id: str = Field(..., description="e.g. 'main_section', 'pond'")
    kind: Literal["buildable", "blocked", "design"]
    cells: list[tuple[int, int, int, int]] = Field(
        default_factory=list, description="Tile rectangles [x, y, width, height]"
    )

    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(f"Zone id must be lower-case snake_case, got: {v!r}")
        return v

    @field_validator("cells")
    @classmethod
    def cells_are_valid(cls, v: list[tuple[int, int, int, int]]) -> list:
        for x, y, w, h in v:
            if x < 0 or y < 0 or w < 1 or h < 1:
                raise ValueError(f"Invalid zone cell {[x, y, w, h]}")
        return v

    def tiles(self) -> set[tuple[int, int]]:
        return cells_to_tiles(self.cells)


class FarmMap(Versioned):
    schema_kind = "farm_map"

    width: int | None = Field(None, ge=1, description="Usable tiles along the ↘ edge")
    height: int | None = Field(None, ge=1, description="Usable tiles along the ↙ edge")
    background: Background | None = None
    fixed: list[FixedItem] = Field(default_factory=list)
    expansions: list[Expansion] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    current: list[CurrentItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
    _base_dir: Path = PrivateAttr(default_factory=Path)

    @model_validator(mode="before")
    @classmethod
    def drop_legacy_area(cls, data):
        # older editor versions wrote "area"; only farm maps are laid out
        if isinstance(data, dict) and "area" in data:
            data = dict(data)
            area = data.pop("area")
            if area != "farm":
                raise ValueError(
                    f"Only farm maps are supported (area {area!r} is not laid out)"
                )
        # before v1.3, barn and silo sat in "fixed" with a "movable" flag
        if isinstance(data, dict) and any(
            isinstance(f, dict) and "movable" in f for f in data.get("fixed") or []
        ):
            raise ValueError(
                "Farm map from an older editor: the 'movable' flag was removed and "
                "'fixed' holds only buildings the game never moves. Open the file in "
                "tools/farm_map_editor.html and save it again"
            )
        return data

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
        zone_ids = [z.id for z in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("Farm map contains duplicate zone ids")
        in_both = sorted({c.id for c in self.current} & set(ids))
        if in_both:
            raise ValueError(
                f"Fixed buildings cannot be current items: {', '.join(in_both)}"
            )
        counted = [c.id for c in self.current if not c.is_placed]
        if len(counted) != len(set(counted)):
            raise ValueError("Farm map counts a current item without position twice")
        if self.background is not None and not self.bounded:
            raise ValueError("A farm map with a background must set width and height")
        if self.bounded:
            for f in (f for f in self.fixed if f.is_placed):
                if f.x + f.width > self.width or f.y + f.height > self.height:
                    raise ValueError(f"Fixed item '{f.id}' lies outside the farm map")
            for e in self.expansions:
                for x, y, w, h in e.cells:
                    if x + w > self.width or y + h > self.height:
                        raise ValueError(
                            f"Expansion '{e.id}' lies outside the farm map"
                        )
            for z in self.zones:
                for x, y, w, h in z.cells:
                    if x + w > self.width or y + h > self.height:
                        raise ValueError(f"Zone '{z.id}' lies outside the farm map")
            for c in (c for c in self.current if c.is_placed):
                if c.x + c.width > self.width or c.y + c.height > self.height:
                    raise ValueError(f"Current item '{c.id}' lies outside the farm map")
        return self

    def usable_tiles(self, design_zones: bool = False) -> set[tuple[int, int]] | None:
        """
        Tiles the layout may use, or None if nothing limits it.

        Start from the unlocked plots (if any drawn plot is unlocked), keep only
        the buildable zones (if any), then remove the blocked zones and, with
        *design_zones*, the design zones. Without plots and buildable zones the
        whole bounded map is the start.
        """
        # an unlocked plot without cells (not drawn yet) must not block the whole map
        unlocked = [e for e in self.expansions if e.is_unlocked and e.cells]
        buildable = [z for z in self.zones if z.kind == "buildable" and z.cells]
        blocked = [z for z in self.zones if z.kind == "blocked" and z.cells]
        if design_zones:
            blocked += [z for z in self.zones if z.kind == "design" and z.cells]
        area = set().union(*(e.tiles() for e in unlocked)) if unlocked else None
        if buildable:
            zone_tiles = set().union(*(z.tiles() for z in buildable))
            area = zone_tiles if area is None else area & zone_tiles
        if blocked:
            if area is None and self.bounded:
                area = {(x, y) for x in range(self.width) for y in range(self.height)}
            if area is not None:
                area -= set().union(*(z.tiles() for z in blocked))
        return area

    def design_tiles(self) -> set[Tile]:
        """Tiles of the design zones (existing decorations)."""
        return set().union(*(z.tiles() for z in self.zones if z.kind == "design"))

    def farm_tiles(self) -> set[Tile]:
        """Every tile of the farm sections: all plots plus the buildable zones."""
        tiles: set[Tile] = set()
        for e in self.expansions:
            tiles |= e.tiles()
        for z in self.zones:
            if z.kind == "buildable":
                tiles |= z.tiles()
        return tiles

    def background_path(self) -> Path | None:
        if self.background is None:
            return None
        return (self._base_dir / self.background.image).resolve()

    @property
    def bounded(self) -> bool:
        return self.width is not None

    @property
    def placed_fixed(self) -> list[FixedItem]:
        """Placed fixed buildings (obstacles)."""
        return [f for f in self.fixed if f.is_placed]


class BaseMap(Versioned):
    """
    The farm's geometry, the same for every player (``data/base_map.json``).

    Map size, fixed buildings, every farm plot (without ``unlocked``) and the
    ``buildable`` / ``blocked`` zones. What a player owns or built goes into
    the :class:`ProfileMap`.
    """

    schema_kind = "base_map"

    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)
    fixed: list[FixedItem] = Field(default_factory=list)
    expansions: list[Expansion] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def no_player_data(cls, data):
        if isinstance(data, dict):
            for e in data.get("expansions") or []:
                if isinstance(e, dict) and "unlocked" in e:
                    raise ValueError(
                        f"Base map plot '{e.get('id')}' sets 'unlocked': "
                        "unlocked plots belong to the profile map"
                    )
        return data

    @field_validator("zones")
    @classmethod
    def no_design_zones(cls, v: list[Zone]) -> list[Zone]:
        design = [z.id for z in v if z.kind == "design"]
        if design:
            raise ValueError(
                f"Design zones belong to the profile map: {', '.join(design)}"
            )
        return v


class ProfileMap(Versioned):
    """
    One player's part of the farm map (``config/profile_map.json``).

    The unlocked plots (ids of the base map), the ``design`` zones (existing
    decoration), the current farm and, kept locally, the calibrated
    screenshot (``background``).
    """

    schema_kind = "profile_map"

    background: Background | None = None
    unlocked: list[str] = Field(default_factory=list, description="Plot ids")
    zones: list[Zone] = Field(default_factory=list)
    current: list[CurrentItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("zones")
    @classmethod
    def only_design_zones(cls, v: list[Zone]) -> list[Zone]:
        other = [z.id for z in v if z.kind != "design"]
        if other:
            raise ValueError(
                f"Only design zones belong to the profile map: {', '.join(other)} "
                "(a one-file farm map from before v2.0? split it with "
                "`python -m src migrate-map`)"
            )
        return v


def merge_maps(base: BaseMap, profile: ProfileMap) -> FarmMap:
    """The farm map of one player: *base* geometry plus *profile* data."""
    plot_ids = {e.id for e in base.expansions}
    unknown = sorted(set(profile.unlocked) - plot_ids)
    if unknown:
        raise ValueError(f"Unlocked plots not in the base map: {', '.join(unknown)}")
    unlocked = set(profile.unlocked)
    return FarmMap(
        width=base.width,
        height=base.height,
        background=profile.background,
        fixed=base.fixed,
        expansions=[
            e.model_copy(update={"unlocked": e.id in unlocked}) for e in base.expansions
        ],
        zones=[*base.zones, *profile.zones],
        current=profile.current,
    )


def split_map(farm_map: FarmMap) -> tuple[BaseMap, ProfileMap]:
    """A one-file farm map (before v2.0) as base map and profile map."""
    base = BaseMap(
        width=farm_map.width,
        height=farm_map.height,
        fixed=farm_map.fixed,
        expansions=[
            e.model_copy(update={"unlocked": False}) for e in farm_map.expansions
        ],
        zones=[z for z in farm_map.zones if z.kind != "design"],
    )
    profile = ProfileMap(
        background=farm_map.background,
        unlocked=[e.id for e in farm_map.expansions if e.unlocked],
        zones=[z for z in farm_map.zones if z.kind == "design"],
        current=farm_map.current,
    )
    return base, profile


def base_map_json(base: BaseMap) -> dict:
    """The JSON object of ``data/base_map.json`` (plots without ``unlocked``)."""
    data = base.model_dump(
        mode="json", exclude={"expansions": {"__all__": {"unlocked"}}}
    )
    return stamp("base_map", data)


def profile_map_json(profile: ProfileMap) -> dict:
    """The JSON object of ``config/profile_map.json``."""
    data = profile.model_dump(mode="json", exclude_none=True)
    return stamp("profile_map", data)


def is_one_file_map(data: dict) -> bool:
    """A farm map before v2.0: geometry and player data in one file."""
    return bool(ONE_FILE_KEYS & data.keys())


def default_map_path() -> Path:
    """config/profile_map.json, else config/farm_map.json, else the example."""
    for path in (LOCAL_PROFILE_MAP, LOCAL_MAP):
        if path.exists():
            return path
    return EXAMPLE_MAP


def load_base_map(path: Path | str = DEFAULT_BASE_MAP) -> BaseMap:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Base map not found: {p}")
    return BaseMap.model_validate(json.loads(p.read_text(encoding="utf-8")))


def load_farm_map(
    path: Path | str | None = None, base_map: Path | str | None = None
) -> FarmMap:
    """
    Load the farm map from *path* or the default location; empty if none.

    A profile map is merged with the base map (*base_map*, default
    ``data/base_map.json``). A one-file map from before v2.0 is read as it is,
    with a warning to split it (``python -m src migrate-map``); the committed
    example stays a one-file map without a warning.
    """
    p = Path(path) if path is not None else default_map_path()
    if not p.exists():
        if path is not None:
            raise FileNotFoundError(f"Farm map not found: {p}")
        return FarmMap()
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and not is_one_file_map(data):
        base = load_base_map(base_map if base_map is not None else DEFAULT_BASE_MAP)
        farm_map = merge_maps(base, ProfileMap.model_validate(data))
    else:  # a one-file map; anything else fails its validation
        if p.resolve() != EXAMPLE_MAP.resolve():
            logger.warning(
                "%s is a one-file farm map from before v2.0; "
                "split it with `python -m src migrate-map`",
                p,
            )
        farm_map = FarmMap.model_validate(data)
    farm_map._base_dir = p.parent
    return farm_map
