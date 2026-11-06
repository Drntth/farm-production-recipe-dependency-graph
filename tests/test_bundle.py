"""Data bundle: every shared data file in one JSON object (src/loaders/bundle.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import main as graph_cli
from src.api import production_plan
from src.combiner import cli as combiner_cli
from src.layout import cli as layout_cli
from src.loaders.bundle import build_bundle
from src.loaders.bundle import main as bundle_main
from src.loaders.json_loader import DataSet, dataset_from_bundle, load_data
from src.planner import cli as planner_cli
from src.schema import KEY

DATA_DIR = Path("data")
pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="data/locations.json not found"
)


def _dump(data: DataSet) -> dict:
    return {
        "locations": [x.model_dump() for x in data.location_list],
        "resources": [x.model_dump() for x in data.resource_list],
        "recipes": [x.model_dump() for x in data.recipe_list],
        "level_limits": data.level_limits and data.level_limits.model_dump(),
        "mastery_bonuses": [x.model_dump() for x in data.mastery_bonuses],
    }


@pytest.fixture(scope="module")
def bundle_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("bundle") / "data_bundle.json"
    assert bundle_main(["--output", str(out)]) == 0
    return out


def test_bundle_holds_every_data_file(bundle_file: Path) -> None:
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    assert list(bundle) == [
        KEY,
        "meta",
        "locations",
        "resources",
        "recipes",
        "level_limits",
        "mastery_bonuses",
        "base_map",
    ]
    assert bundle[KEY] == 1
    assert bundle["meta"] == json.loads((DATA_DIR / "meta.json").read_text())
    assert bundle["base_map"] == json.loads((DATA_DIR / "base_map.json").read_text())


def test_bundle_gives_the_same_dataset(bundle_file: Path) -> None:
    from_files = _dump(load_data(DATA_DIR))
    assert _dump(load_data(bundle_file)) == from_files
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    assert _dump(dataset_from_bundle(bundle)) == from_files


def test_bundle_has_the_overrides_merged() -> None:
    bundle = build_bundle(DATA_DIR)
    plain = load_data(DATA_DIR, apply_data_overrides=False)
    assert _dump(dataset_from_bundle(bundle)) != _dump(plain)


def test_invalid_bundles(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="update the tools"):
        dataset_from_bundle({KEY: 99})
    with pytest.raises(ValueError, match="JSON object"):
        dataset_from_bundle([])
    with pytest.raises(ValueError, match="needs locations, resources, recipes"):
        dataset_from_bundle({KEY: 1})
    with pytest.raises(ValueError, match="Not a list in the data bundle: locations"):
        dataset_from_bundle({"locations": {}, "resources": [], "recipes": []})
    with pytest.raises(ValueError, match="mastery_bonuses"):
        dataset_from_bundle(
            {
                "locations": [],
                "resources": [],
                "recipes": [],
                "mastery_bonuses": {"a": 1},
            }
        )
    (tmp_path / "locations.json").write_text("{}", encoding="utf-8")
    assert (
        bundle_main(["--data-dir", str(tmp_path), "--output", str(tmp_path / "x.json")])
        == 1
    )


@pytest.mark.parametrize("tool", [layout_cli, planner_cli, combiner_cli, graph_cli])
def test_cli_data_dir_is_a_directory(bundle_file: Path, tool) -> None:
    with pytest.raises(SystemExit) as exc:
        tool.main(["--data-dir", str(bundle_file), "--level", "20"])
    assert exc.value.code == 2


def test_core_api_takes_a_bundle(bundle_file: Path) -> None:
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    player = {"level": 20}
    from_bundle = production_plan(bundle, player=player)
    assert from_bundle == production_plan(load_data(DATA_DIR), player=player)
