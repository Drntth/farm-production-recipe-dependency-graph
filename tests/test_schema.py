"""schema_version and migrations of the input files (src/schema.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import PlayerConfig, load_player_config
from src.layout.farm_map import FarmMap
from src.layout.templates import DesignTemplate
from src.schema import CURRENT, KEY, stamp, upgrade
from src.settings import DesignSettings, PlannerSettings


def test_missing_version_is_version_one() -> None:
    assert upgrade("player", {"level": 3}) == {"level": 3}


def test_key_is_dropped() -> None:
    assert upgrade("design", {KEY: 1, "gap": 2}) == {"gap": 2}


@pytest.mark.parametrize("bad", [0, -1, "1", 1.0, True, None])
def test_invalid_version(bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        upgrade("player", {KEY: bad})


def test_newer_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="update the tools"):
        upgrade("player", {KEY: CURRENT["player"] + 1})


def test_migrations_run_in_order() -> None:
    current = {"thing": 3}
    migrations = {
        "thing": {
            1: lambda d: d | {"steps": [*d.get("steps", []), 1]},
            2: lambda d: d | {"steps": [*d["steps"], 2]},
        }
    }
    up = upgrade("thing", {"a": 1}, current=current, migrations=migrations)
    assert up == {"a": 1, "steps": [1, 2]}
    up = upgrade("thing", {KEY: 2, "steps": []}, current=current, migrations=migrations)
    assert up == {"steps": [2]}


def test_missing_migration_is_an_error() -> None:
    with pytest.raises(ValueError, match="No migration"):
        upgrade("thing", {}, current={"thing": 2}, migrations={})


def test_stamp_puts_the_version_first() -> None:
    assert list(stamp("player", {"level": 1, KEY: 9})) == [KEY, "level"]
    assert stamp("player", {})[KEY] == CURRENT["player"]


@pytest.mark.parametrize(
    "model, data",
    [
        (PlayerConfig, {"level": 5}),
        (DesignSettings, {}),
        (PlannerSettings, {}),
        (DesignTemplate, {"width": 1, "height": 1}),
        (FarmMap, {}),
    ],
)
def test_models_accept_and_hide_the_version(model, data: dict) -> None:
    obj = model.model_validate({KEY: 1, **data})
    assert KEY not in obj.model_dump()
    assert obj == model.model_validate(data)
    with pytest.raises(ValidationError, match="update the tools"):
        model.model_validate({KEY: 99, **data})


def test_example_files_are_versioned() -> None:
    for kind, path in [
        ("player", "config/player.example.json"),
        ("design", "config/design.example.json"),
        ("planner", "config/planner.example.json"),
        ("template", "config/templates/dairy_garden.example.json"),
    ]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data[KEY] == CURRENT[kind], path


def test_loader_reads_a_versioned_file(tmp_path: Path) -> None:
    path = tmp_path / "player.json"
    path.write_text(json.dumps({KEY: 1, "level": 7}), encoding="utf-8")
    assert load_player_config(path).level == 7
