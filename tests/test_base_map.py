"""Base map + profile map: the split farm map and its migration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.layout import farm_map as fm_module
from src.layout.farm_map import (
    BaseMap,
    FarmMap,
    ProfileMap,
    base_map_json,
    default_map_path,
    load_base_map,
    load_farm_map,
    merge_maps,
    profile_map_json,
    split_map,
)
from src.layout.migrate_map import main as migrate_main
from src.layout.migrate_map import map_json_text

ROOT = Path(__file__).resolve().parent.parent

ONE_FILE = {
    "width": 20,
    "height": 10,
    "background": {
        "image": "shot.png",
        "image_width": 100,
        "image_height": 50,
        "origin_px": [50, 0],
        "x_axis_px": [2, 1],
        "y_axis_px": [-2, 1],
    },
    "fixed": [{"id": "farmhouse", "x": 1, "y": 1, "width": 4, "height": 3}],
    "expansions": [
        {"id": "base_1", "section": "base", "cells": [[0, 0, 10, 10]]},
        {"id": "main_1", "section": "main", "unlocked": True, "cells": [[10, 0, 5, 5]]},
        {"id": "main_2", "section": "main", "cells": [[15, 0, 5, 5]]},
    ],
    "zones": [
        {"id": "pond", "kind": "blocked", "cells": [[0, 8, 2, 2]]},
        {"id": "garden", "kind": "design", "cells": [[5, 5, 1, 1]]},
    ],
    "current": [{"id": "field", "count": 4}],
}
ONE_MAP = FarmMap.model_validate(ONE_FILE)


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_split_then_merge_is_the_one_file_map() -> None:
    one = FarmMap.model_validate(ONE_FILE)
    base, profile = split_map(one)
    assert profile.unlocked == ["main_1"]
    assert [z.id for z in base.zones] == ["pond"]
    assert [z.id for z in profile.zones] == ["garden"]
    assert merge_maps(base, profile) == one
    # through the JSON files as well
    base2 = BaseMap.model_validate(base_map_json(base))
    profile2 = ProfileMap.model_validate(profile_map_json(profile))
    assert merge_maps(base2, profile2) == one


def test_base_map_json_has_no_player_data() -> None:
    base, _ = split_map(FarmMap.model_validate(ONE_FILE))
    data = base_map_json(base)
    assert data["schema_version"] == 1
    assert all("unlocked" not in e for e in data["expansions"])
    assert "background" not in data and "current" not in data


def test_base_map_rejects_player_data() -> None:
    with pytest.raises(ValidationError, match="profile map"):
        BaseMap.model_validate({"expansions": [ONE_FILE["expansions"][1]]})
    with pytest.raises(ValidationError, match="profile map"):
        BaseMap.model_validate({"zones": [ONE_FILE["zones"][1]]})


def test_profile_map_takes_only_design_zones() -> None:
    with pytest.raises(ValidationError, match="Only design zones"):
        ProfileMap.model_validate({"zones": [ONE_FILE["zones"][0]]})


def test_unknown_unlocked_plot_is_an_error() -> None:
    base, _ = split_map(FarmMap.model_validate(ONE_FILE))
    with pytest.raises(ValueError, match="main_9"):
        merge_maps(base, ProfileMap(unlocked=["main_9"]))


def test_load_profile_map_merges_the_base_map(tmp_path: Path) -> None:
    base, profile = split_map(FarmMap.model_validate(ONE_FILE))
    base_path = _write(tmp_path / "base_map.json", base_map_json(base))
    (tmp_path / "cfg").mkdir()
    profile_path = _write(tmp_path / "cfg" / "profile.json", profile_map_json(profile))
    loaded = load_farm_map(profile_path, base_path)
    assert loaded.model_dump() == ONE_MAP.model_dump()
    # the background is found next to the profile map
    assert loaded.background_path() == (tmp_path / "cfg" / "shot.png").resolve()
    with pytest.raises(FileNotFoundError, match="Base map"):
        load_farm_map(profile_path, tmp_path / "missing.json")


def test_one_file_map_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = _write(tmp_path / "farm_map.json", ONE_FILE)
    with caplog.at_level(logging.WARNING):
        assert load_farm_map(path).model_dump() == ONE_MAP.model_dump()
    assert "migrate-map" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        load_farm_map(ROOT / "config" / "farm_map.example.json")
    assert caplog.text == ""


def test_default_map_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    assert default_map_path() == fm_module.EXAMPLE_MAP
    _write(tmp_path / fm_module.LOCAL_MAP, {})
    assert default_map_path() == fm_module.LOCAL_MAP
    _write(tmp_path / fm_module.LOCAL_PROFILE_MAP, {})
    assert default_map_path() == fm_module.LOCAL_PROFILE_MAP


def test_committed_maps_are_valid() -> None:
    base = load_base_map(ROOT / "data" / "base_map.json")
    assert base.width and base.height and base.expansions
    farm_map = load_farm_map(
        ROOT / "config" / "profile_map.example.json", ROOT / "data" / "base_map.json"
    )
    assert any(e.unlocked for e in farm_map.expansions)
    # the committed file is written by the migration's formatter
    text = (ROOT / "data" / "base_map.json").read_text(encoding="utf-8")
    assert text == map_json_text(base_map_json(base))


def test_migrate_map_command(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "config").mkdir()
    source = _write(tmp_path / "config" / "farm_map.json", ONE_FILE)
    out = tmp_path / "local" / "profile_map.json"
    base_out = tmp_path / "data" / "base_map.json"
    args = ["--map", str(source), "--output", str(out)]
    assert migrate_main([*args, "--base-output", str(base_out)]) == 0
    migrated = load_farm_map(out, base_out)
    no_bg = {"background"}
    assert migrated.model_dump(exclude=no_bg) == ONE_MAP.model_dump(exclude=no_bg)
    assert migrated.background_path() == (source.parent / "shot.png").resolve()
    # the background path still points at the screenshot
    assert json.loads(out.read_text())["background"]["image"] == "../config/shot.png"
    # an existing profile map is kept unless --force
    assert migrate_main(args) == 1
    # without --base-output the geometry is checked against the data directory
    other = dict(ONE_FILE, width=30)
    _write(source, other)
    data_args = ["--data-dir", str(tmp_path / "data"), "--force"]
    with caplog.at_level(logging.WARNING):
        assert migrate_main([*args, *data_args]) == 0
    assert "differs" in caplog.text
    # not a one-file map
    assert migrate_main(["--map", str(out), "--output", str(tmp_path / "x.json")]) == 1
