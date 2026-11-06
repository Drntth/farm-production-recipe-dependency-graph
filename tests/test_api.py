"""Core API: the tools without file IO (src/api)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.api import (
    combined_plan,
    layout_plan,
    production_plan,
    relocation_plan,
    write_files,
)
from src.layout import cli as layout_cli
from src.loaders.json_loader import DataSet, load_data
from src.relocation.relocate import layout_part

DATA_DIR = Path("data")
pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="data/locations.json not found"
)
LEVEL = 20


def _json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def data() -> DataSet:
    return load_data(DATA_DIR)


@pytest.fixture(scope="module")
def player() -> dict:
    return _json("config/player.example.json") | {"level": LEVEL}


@pytest.fixture(scope="module")
def farm_map() -> dict:
    return _json("config/farm_map.example.json")


@pytest.fixture(scope="module")
def design() -> dict:
    return _json("config/design.example.json") | {"block_images": True}


@pytest.fixture(scope="module")
def layout_run(data: DataSet, player: dict, farm_map: dict, design: dict) -> dict:
    return layout_plan(data, player=player, farm_map=farm_map, design=design)


def test_layout_plan_files_and_result(layout_run: dict) -> None:
    files = layout_run["files"]
    assert {"layout.json", "layout.md", "layout.svg"} <= files.keys()
    assert any(name.startswith("blocks/") for name in files)
    assert "blocks/collage.svg" in files
    assert json.loads(files["layout.json"]) == layout_run["result"]
    assert layout_run["result"]["level"] == LEVEL


def test_layout_plan_needs_a_level(data: DataSet) -> None:
    with pytest.raises(ValueError, match="no level"):
        layout_plan(data)


def test_layout_plan_rejects_invalid_level(data: DataSet) -> None:
    with pytest.raises(ValueError):
        layout_plan(data, level=0)


def test_invalid_dict_inputs(data: DataSet) -> None:
    with pytest.raises(ValueError, match="level"):
        layout_plan(data, player={"level": "x"})
    with pytest.raises(ValueError, match="width"):
        layout_plan(data, level=LEVEL, farm_map={"width": -1})
    with pytest.raises(ValueError, match="unknown_setting"):
        layout_plan(data, level=LEVEL, design={"unknown_setting": 1})


def test_missing_template_is_an_error(data: DataSet, design: dict) -> None:
    assigned = design | {"templates": {"dairy_block": {"template": "garden"}}}
    with pytest.raises(ValueError, match="garden"):
        layout_plan(data, level=LEVEL, design=assigned)


def test_layout_cli_writes_the_api_files(
    tmp_path: Path, data: DataSet, design: dict
) -> None:
    config = tmp_path / "design.json"
    config.write_text(json.dumps(design), encoding="utf-8")
    out = tmp_path / "out"
    args = ["--level", str(LEVEL), "--design-config", str(config)]
    args += ["--player-config", "config/player.example.json"]
    args += ["--map", "config/farm_map.example.json", "--output-dir", str(out)]
    assert layout_cli.main(args) == 0
    run = layout_plan(
        data,
        player=_json("config/player.example.json"),
        level=LEVEL,
        farm_map=_json("config/farm_map.example.json"),
        design=design,
        output_dir=out,
    )
    for name, text in run["files"].items():
        assert (out / name).read_text(encoding="utf-8") == text, name


def test_production_plan(data: DataSet, player: dict) -> None:
    run = production_plan(data, player=player, planner={})
    assert set(run["files"]) == {"capacity.json", "schedule.json", "schedule.md"}
    assert json.loads(run["files"]["schedule.json"]) == run["result"]
    assert "settings" in run["result"]


def test_combined_plan(
    data: DataSet, player: dict, farm_map: dict, design: dict
) -> None:
    run = combined_plan(
        data, player=player, farm_map=farm_map, design=design, data_max_level=LEVEL
    )
    files = run["files"]
    assert {"combined.json", "combined.md", "combined.svg"} <= files.keys()
    assert "combined_blocks/collage.svg" in files
    assert json.loads(files["combined.json"]) == run["result"]
    assert set(run["result"]["settings"]) == {"design", "production", "combiner"}


def test_relocation_plan(data: DataSet, player: dict, design: dict) -> None:
    sized = {"width": 100, "height": 100}
    layout = layout_plan(data, player=player, farm_map=sized, design=design)["result"]
    current = sized | {"current": [{"id": "field", "count": 3}]}
    run = relocation_plan(data, layout=layout, farm_map=current)
    assert set(run["files"]) == {"relocation.json", "relocation.md"}
    assert json.loads(run["files"]["relocation.json"]) == run["result"]
    # a combined.json is accepted as well
    wrapped = {"layout": layout}
    again = relocation_plan(data, layout=wrapped, farm_map=current)
    assert again["result"] == run["result"]


def test_layout_part_rejects_other_json() -> None:
    with pytest.raises(ValueError, match="Not a layout.json"):
        layout_part({"schedule": []}, "x.json")


def test_write_files_replaces_old_block_images(tmp_path: Path) -> None:
    (tmp_path / "blocks").mkdir()
    (tmp_path / "blocks" / "gone.svg").write_text("<svg/>")
    (tmp_path / "keep.svg").write_text("<svg/>")
    paths = write_files(tmp_path, {"a.json": "{}", "blocks/b.svg": "<svg/>"})
    assert sorted(p.name for p in paths) == ["a.json", "b.svg"]
    assert not (tmp_path / "blocks" / "gone.svg").exists()
    assert (tmp_path / "keep.svg").exists()
    assert (tmp_path / "a.json").read_text(encoding="utf-8") == "{}"
