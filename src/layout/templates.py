"""
Design templates: a small grid pattern of buildings and decoration tiles.

A template is one file, ``config/templates/<name>.json`` (git-ignored), with
``<name>.example.json`` as the committed fallback, like the other config
files. Coordinates are tiles relative to the template's top corner, with the
same axes as the farm map (x ↘ = width, y ↙ = height)::

    {
      "width": 9,
      "height": 5,
      "buildings": [{"location_id": "dairy", "x": 0, "y": 0, "width": 4, "height": 4}],
      "decorations": [[4, 0, 1, 4], [0, 4, 9, 1]]
    }

``decorations`` are tile rectangles ``[x, y, width, height]`` that are only
"taken" (no decoration kind). ``templates`` in ``config/design.json`` assigns a
template to a block; the Layout Planner either keeps its area free
(``reserve``) or puts its buildings at their template positions
(``arrange``). Templates are never rotated or mirrored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schema import Versioned
from src.settings import CONFIG_DIR, TemplateAssignment, TemplateMode

from .farm_map import cells_to_tiles

TEMPLATE_DIR = CONFIG_DIR / "templates"


def _snake(v: str, what: str) -> str:
    if not v or not v.replace("_", "").isalnum() or v != v.lower():
        raise ValueError(f"{what} must be lower-case snake_case, got: {v!r}")
    return v


class TemplateBuilding(BaseModel):
    """One building of a template: a location id and its tile rectangle."""

    location_id: str
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., ge=1, description="Tiles along the ↘ edge")
    height: int = Field(..., ge=1, description="Tiles along the ↙ edge")

    model_config = {"extra": "forbid"}

    @field_validator("location_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        return _snake(v, "Template building id")

    def tiles(self) -> set[tuple[int, int]]:
        return cells_to_tiles([(self.x, self.y, self.width, self.height)])


class DesignTemplate(Versioned):
    schema_kind = "template"

    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    buildings: list[TemplateBuilding] = Field(default_factory=list)
    decorations: list[tuple[int, int, int, int]] = Field(
        default_factory=list, description="Taken tile rectangles [x, y, w, h]"
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_template(self) -> DesignTemplate:
        taken: set[tuple[int, int]] = set()
        for b in self.buildings:
            if b.x + b.width > self.width or b.y + b.height > self.height:
                raise ValueError(f"Template building {b.location_id} lies outside")
            tiles = b.tiles()
            if tiles & taken:
                raise ValueError(f"Template building {b.location_id} overlaps another")
            taken |= tiles
        for x, y, w, h in self.decorations:
            if x < 0 or y < 0 or w < 1 or h < 1:
                raise ValueError(f"Invalid decoration cell {[x, y, w, h]}")
            if x + w > self.width or y + h > self.height:
                raise ValueError(f"Decoration cell {[x, y, w, h]} lies outside")
        if self.decoration_tiles() & taken:
            raise ValueError("Template decorations overlap a building")
        return self

    def decoration_tiles(self) -> set[tuple[int, int]]:
        return cells_to_tiles(self.decorations)


@dataclass(frozen=True)
class BlockTemplate:
    """A loaded template assigned to one block."""

    name: str
    template: DesignTemplate
    mode: TemplateMode = "reserve"


def template_path(name: str, directory: Path | str = TEMPLATE_DIR) -> Path:
    """``<dir>/<name>.json``, else ``<dir>/<name>.example.json``."""
    d = Path(directory)
    local = d / f"{name}.json"
    example = d / f"{name}.example.json"
    if local.exists() or not example.exists():
        return local
    return example


def load_template(name: str, directory: Path | str = TEMPLATE_DIR) -> DesignTemplate:
    _snake(name, "Template name")
    p = template_path(name, directory)
    if not p.exists():
        raise FileNotFoundError(f"Design template not found: {p}")
    try:
        return DesignTemplate.model_validate(json.loads(p.read_text(encoding="utf-8")))
    except ValueError as exc:
        raise ValueError(f"Invalid design template {p}: {exc}") from exc


def load_templates(
    assignments: dict[str, TemplateAssignment],
    directory: Path | str = TEMPLATE_DIR,
) -> dict[str, BlockTemplate]:
    """Block id -> loaded template, from the ``templates`` design setting."""
    return resolve_templates(assignments, load_template_files(assignments, directory))


def load_template_files(
    assignments: dict[str, TemplateAssignment],
    directory: Path | str = TEMPLATE_DIR,
) -> dict[str, DesignTemplate]:
    """Template name -> template, for every template the assignments use."""
    return {
        name: load_template(name, directory)
        for name in dict.fromkeys(a.template for a in assignments.values())
    }


def resolve_templates(
    assignments: dict[str, TemplateAssignment],
    by_name: dict[str, DesignTemplate | dict[str, Any]],
) -> dict[str, BlockTemplate]:
    """
    Block id -> template, from the assignments and templates given by name.

    A template may be a parsed JSON object; a missing name is an error.
    """
    result: dict[str, BlockTemplate] = {}
    for block_id, a in assignments.items():
        if a.template not in by_name:
            raise ValueError(f"Design template not given: {a.template}")
        tpl = by_name[a.template]
        if not isinstance(tpl, DesignTemplate):
            try:
                tpl = DesignTemplate.model_validate(tpl)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid design template {a.template}: {exc}"
                ) from exc
        result[block_id] = BlockTemplate(a.template, tpl, a.mode)
    return result
