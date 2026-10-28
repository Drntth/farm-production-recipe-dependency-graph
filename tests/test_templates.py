"""Design templates: file format, validation and loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.layout.templates import (
    DesignTemplate,
    load_template,
    load_templates,
    template_path,
)
from src.settings import DesignSettings, TemplateAssignment

GARDEN = {
    "width": 9,
    "height": 5,
    "buildings": [
        {"location_id": "dairy", "x": 0, "y": 0, "width": 4, "height": 4},
        {"location_id": "cow_pasture", "x": 5, "y": 0, "width": 4, "height": 4},
    ],
    "decorations": [[4, 0, 1, 4], [0, 4, 9, 1]],
}


def test_template_model() -> None:
    t = DesignTemplate.model_validate(GARDEN)
    assert len(t.buildings) == 2
    assert len(t.decoration_tiles()) == 4 + 9


@pytest.mark.parametrize(
    "change",
    [
        {
            "buildings": [
                {"location_id": "dairy", "x": 6, "y": 0, "width": 4, "height": 4}
            ]
        },
        {
            "buildings": [
                {"location_id": "dairy", "x": 0, "y": 0, "width": 4, "height": 4},
                {"location_id": "bakery", "x": 2, "y": 0, "width": 3, "height": 3},
            ]
        },
        {"decorations": [[0, 0, 1, 1]]},  # on the dairy
        {"decorations": [[8, 4, 2, 1]]},  # outside
        {"decorations": [[4, 0, 0, 1]]},  # empty cell
        {
            "buildings": [
                {"location_id": "Dairy", "x": 0, "y": 0, "width": 4, "height": 4}
            ]
        },
        {"kind": "garden"},  # extra keys are forbidden
    ],
)
def test_template_model_rejects_bad_templates(change: dict) -> None:
    with pytest.raises(ValidationError):
        DesignTemplate.model_validate(GARDEN | change)


def test_load_template_prefers_the_local_file(tmp_path: Path) -> None:
    (tmp_path / "garden.example.json").write_text(json.dumps(GARDEN))
    assert template_path("garden", tmp_path).name == "garden.example.json"
    assert load_template("garden", tmp_path).width == 9
    (tmp_path / "garden.json").write_text(json.dumps(GARDEN | {"width": 10}))
    assert load_template("garden", tmp_path).width == 10

    with pytest.raises(FileNotFoundError):
        load_template("missing", tmp_path)
    (tmp_path / "broken.json").write_text(json.dumps(GARDEN | {"height": 2}))
    with pytest.raises(ValueError, match="broken.json"):
        load_template("broken", tmp_path)
    with pytest.raises(ValueError, match="snake_case"):
        load_template("../garden", tmp_path)


def test_load_templates_from_the_design_setting(tmp_path: Path) -> None:
    (tmp_path / "garden.json").write_text(json.dumps(GARDEN))
    cfg = DesignSettings(
        templates={"dairy_block": {"template": "garden", "mode": "arrange"}}
    )
    loaded = load_templates(cfg.templates, tmp_path)
    assert loaded["dairy_block"].name == "garden"
    assert loaded["dairy_block"].mode == "arrange"
    assert TemplateAssignment(template="garden").mode == "reserve"  # default
    with pytest.raises(ValidationError):
        DesignSettings(templates={"dairy_block": {"template": "g", "mode": "mirror"}})


def test_committed_example_template_is_valid() -> None:
    examples = sorted(Path("config/templates").glob("*.example.json"))
    assert examples
    for p in examples:
        DesignTemplate.model_validate(json.loads(p.read_text(encoding="utf-8")))
