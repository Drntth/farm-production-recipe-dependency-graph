import json
from pathlib import Path

import pytest

from src.loaders.json_loader import load_data
from src.models import Area


def test_load_data():
    dataset = load_data(Path("data"))

    assert len(dataset.locations) > 0
    assert len(dataset.resources) > 0
    assert len(dataset.recipes) > 0


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    _write(
        tmp_path / "locations.json",
        [
            {"id": "cow_pasture", "name": "Cow Pasture", "type": "animal", "unlock_level": 6},
            {"id": "dairy", "name": "Dairy", "type": "production", "unlock_level": 6},
        ],
    )
    _write(
        tmp_path / "resources.json",
        [
            {
                "id": "milk",
                "name": "Milk",
                "type": "animal_product",
                "unlock_level": 6,
                "source_location_id": "cow_pasture",
            },
            {"id": "cream", "name": "Cream", "type": "processed_material", "unlock_level": 6},
        ],
    )
    _write(
        tmp_path / "recipes.json",
        [
            {
                "id": "cream",
                "name": "Cream",
                "location_id": "dairy",
                "unlock_level": 6,
                "inputs": [{"resource_id": "milk", "amount": 1}],
                "output": {"resource_id": "cream", "amount": 1},
            }
        ],
    )
    return tmp_path


def test_overrides_patch_and_add(data_dir: Path) -> None:
    _write(
        data_dir / "overrides" / "locations.json",
        [
            {"id": "cow_pasture", "footprint_width": 4, "footprint_height": 4},
            {
                "id": "lobster_pool",
                "name": "Lobster Pool",
                "type": "animal",
                "unlock_level": 44,
                "area": "fishing_lake",
            },
        ],
    )
    ds = load_data(data_dir)

    pasture = ds.locations["cow_pasture"]
    assert (pasture.footprint_width, pasture.footprint_height) == (4, 4)
    assert pasture.name == "Cow Pasture"  # untouched fields are kept
    assert ds.locations["lobster_pool"].area == Area.FISHING_LAKE

    raw = load_data(data_dir, apply_data_overrides=False)
    assert "lobster_pool" not in raw.locations


def test_override_null_values_are_skipped(data_dir: Path) -> None:
    _write(
        data_dir / "overrides" / "locations.json",
        [
            {"id": "cow_pasture", "name": None, "footprint_width": None, "footprint_height": None},
            {"id": "dairy", "footprint_width": 4, "footprint_height": 4, "animal_capacity": None},
        ],
    )
    ds = load_data(data_dir)

    assert ds.locations["cow_pasture"].name == "Cow Pasture"
    assert ds.locations["cow_pasture"].footprint_width is None
    assert ds.locations["dairy"].footprint_width == 4


def test_override_without_id_rejected(data_dir: Path) -> None:
    _write(data_dir / "overrides" / "recipes.json", [{"name": "No id"}])
    with pytest.raises(ValueError, match="no 'id'"):
        load_data(data_dir)


def test_level_limits_loaded_and_filtered(data_dir: Path) -> None:
    _write(
        data_dir / "level_limits.json",
        {
            "field_grants": [{"level": 1, "count": 6}, {"level": 7, "count": 3}],
            "location_instances": [
                {"location_id": "cow_pasture", "instance": 1, "unlock_level": 6},
                {"location_id": "cow_pasture", "instance": 2, "unlock_level": 15},
            ],
        },
    )
    ds = load_data(data_dir)
    assert ds.level_limits is not None
    assert ds.level_limits.instances_at("cow_pasture", 20) == 2

    low = load_data(data_dir, max_level=6)
    assert low.level_limits.fields_at(6) == 6
    assert len(low.level_limits.location_instances) == 1


def test_level_limits_unknown_location_rejected(data_dir: Path) -> None:
    _write(
        data_dir / "level_limits.json",
        {"location_instances": [{"location_id": "bakery", "instance": 1, "unlock_level": 4}]},
    )
    with pytest.raises(ValueError, match="unknown location_id 'bakery'"):
        load_data(data_dir)


def test_level_limits_optional(data_dir: Path) -> None:
    assert load_data(data_dir).level_limits is None


def test_external_inputs_logged_once(data_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    recipes = json.loads((data_dir / "recipes.json").read_text())
    recipes[0]["inputs"].append({"resource_id": "voucher", "amount": 2})
    _write(data_dir / "recipes.json", recipes)

    with caplog.at_level("INFO", logger="src.loaders.json_loader"):
        ds = load_data(data_dir)
        ds.filter_by_max_level(10)

    assert ds.external_inputs() == {"voucher": ["cream"]}
    lines = [r for r in caplog.records if "External recipe inputs" in r.getMessage()]
    assert len(lines) == 1 and "voucher (1)" in lines[0].getMessage()
    assert not [r for r in caplog.records if r.levelname == "WARNING"]
