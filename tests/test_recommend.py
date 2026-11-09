"""Level recommendations (src/recommend): one JSON and one SVG per level."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from src.layout.farm_map import cells_to_tiles, load_base_map
from src.loaders.json_loader import DataSet, load_data
from src.recommend import cli as recommend_cli
from src.recommend import level_recommendation, recommendations
from src.recommend.build import base_farm_map, tile_rects
from src.schema import CURRENT, KEY

DATA_DIR = Path("data")
pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="data/locations.json not found"
)
LEVELS = (1, 12)


@pytest.fixture(scope="module")
def data() -> DataSet:
    return load_data(DATA_DIR)


@pytest.fixture(scope="module")
def base():
    return load_base_map(DATA_DIR / "base_map.json")


@pytest.fixture(scope="module")
def run(data, base) -> dict:
    return recommendations(data, base, LEVELS, game_version="9.9", core_version="0.0.0")


def test_base_farm_map_unlocks_no_plot(base):
    # section base always counts as unlocked; no other plot is
    fm = base_farm_map(base)
    assert not [e.id for e in fm.expansions if e.unlocked]
    assert any(e.section == "base" for e in fm.expansions)


def test_files_per_level_and_index(run):
    names = set(run["files"])
    expected = {f"level_{n}.{ext}" for n in LEVELS for ext in ("json", "svg")}
    assert names == expected | {"index.json", "map.json"}
    for n in LEVELS:
        assert run["files"][f"level_{n}.svg"].lstrip().startswith("<svg")


def test_level_json_shape(run):
    for n in LEVELS:
        rec = json.loads(run["files"][f"level_{n}.json"])
        assert rec[KEY] == CURRENT["recommendation"]
        assert rec["level"] == n
        assert (rec["game_version"], rec["core_version"]) == ("9.9", "0.0.0")
        combined = rec["combined"]
        assert combined["level"] == n
        assert rec["blocks_not_placed"] == combined["summary"]["blocks_not_placed"]
        assert {"summary", "blocks", "layout", "schedule"} <= set(combined)
        # built-in settings, no block images on the site
        assert combined["settings"]["design"]["block_images"] is False


def test_index_rows_match_levels(run):
    index = json.loads(run["files"]["index.json"])
    assert index[KEY] == CURRENT["recommendation_index"]
    assert [row["level"] for row in index["levels"]] == list(LEVELS)
    for row in index["levels"]:
        rec = json.loads(run["files"][f"level_{row['level']}.json"])
        assert row["blocks"] == rec["combined"]["summary"]["blocks"]
        assert row["blocks_not_placed"] == len(rec["blocks_not_placed"])
        summary = rec["combined"]["summary"]
        assert row["logins_per_day"] == summary["logins_per_day"]
        assert len(summary["login_times"]) == summary["logins_per_day"]


def test_tile_rects_cover_the_tiles_once():
    tiles = {(0, 0), (1, 0), (0, 1), (1, 1), (3, 1), (0, 3), (1, 3)}
    rects = tile_rects(tiles)
    assert rects == [[0, 0, 2, 2], [3, 1, 1, 1], [0, 3, 2, 1]]
    assert sum(w * h for _, _, w, h in rects) == len(tiles)
    assert cells_to_tiles([tuple(r) for r in rects]) == tiles


def test_map_json_is_the_map_of_every_level(run, base):
    view = json.loads(run["files"]["map.json"])
    assert view[KEY] == CURRENT["recommendation_map"]
    fm = base_farm_map(base)
    assert (view["width"], view["height"]) == (fm.width, fm.height)
    usable = cells_to_tiles([tuple(r) for r in view["usable"]])
    assert usable == fm.usable_tiles()
    x, y, w, h = view["usable_bounds"]
    assert all(x <= tx < x + w and y <= ty < y + h for tx, ty in usable)
    assert {f["id"] for f in view["fixed"]} == {f.id for f in fm.placed_fixed}
    assert view["farm_outline"] and all(len(s) == 4 for s in view["farm_outline"])


def test_level_recommendation_is_deterministic(data, base):
    fm = base_farm_map(base)
    first = level_recommendation(data, fm, LEVELS[-1])["files"]
    assert level_recommendation(data, fm, LEVELS[-1])["files"] == first


def test_level_above_the_data_is_an_error(data, base):
    with pytest.raises(ValueError, match="above the data"):
        recommendations(data, base, (5,), data_max_level=4)


@pytest.mark.parametrize(
    ("text", "levels"),
    [("1-3", (1, 2, 3)), ("10,1", (1, 10)), ("1-2,5,2", (1, 2, 5))],
)
def test_parse_levels(text, levels):
    assert recommend_cli.parse_levels(text) == levels


@pytest.mark.parametrize(
    "text", ["", "a", "0-3", "5-1", "1,,2", "1-1000000000", "1001"]
)
def test_parse_levels_rejects(text):
    with pytest.raises(argparse.ArgumentTypeError):
        recommend_cli.parse_levels(text)


def test_cli_writes_files(tmp_path):
    out = tmp_path / "rec"
    assert recommend_cli.main(["--levels", "1", "--output-dir", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "index.json",
        "level_1.json",
        "level_1.svg",
        "map.json",
    ]
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["core_version"] == recommend_cli.core_version()


def test_cli_write_error_exits_1(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    out = blocker / "rec"  # a directory below a file cannot be created
    assert recommend_cli.main(["--levels", "1", "--output-dir", str(out)]) == 1
