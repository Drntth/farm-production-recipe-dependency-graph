import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import (
    EXAMPLE_CONFIG,
    MasterySystem,
    PlayerConfig,
    load_player_config,
    validate_player_config,
)
from src.loaders.json_loader import DataSet, load_data
from src.models import FieldGrant, LevelLimits, Location, LocationInstance


def test_example_config_is_valid() -> None:
    cfg = load_player_config(EXAMPLE_CONFIG)
    assert cfg.level >= 1
    assert cfg.mastery_system == MasterySystem.STARS


def test_custom_config(tmp_path: Path) -> None:
    p = tmp_path / "player.json"
    p.write_text(json.dumps({"level": 30, "mastery_system": "workbench"}))
    cfg = load_player_config(p)
    assert cfg.level == 30
    assert cfg.mastery_system == MasterySystem.WORKBENCH


def test_unknown_field_rejected(tmp_path: Path) -> None:
    p = tmp_path / "player.json"
    p.write_text(json.dumps({"level": 30, "stars": 3}))
    with pytest.raises(ValidationError):
        load_player_config(p)


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_player_config(tmp_path / "nope.json")


def test_location_progress_ranges() -> None:
    with pytest.raises(ValidationError):
        PlayerConfig(level=10, locations={"dairy": {"mastery_stars": 4}})
    with pytest.raises(ValidationError):
        PlayerConfig(level=10, locations={"dairy": {"color": "red"}})
    with pytest.raises(ValidationError):
        PlayerConfig(level=40, locations={"beehive_tree": {"beehives": 5}})
    cfg = PlayerConfig(level=10, locations={"dairy": {"slots": 4, "owned": None}})
    assert cfg.locations["dairy"].slots == 4


def _dataset() -> DataSet:
    return DataSet(
        [
            Location(id="field", name="Field", type="field", unlock_level=1),
            Location(
                id="chicken_coop", name="Chicken Coop", type="animal",
                unlock_level=1, animal_capacity=6,
            ),
            Location(id="dairy", name="Dairy", type="production", unlock_level=6),
            Location(id="sushi_bar", name="Sushi Bar", type="production", unlock_level=56),
        ],
        [],
        [],
        LevelLimits(
            field_grants=[FieldGrant(level=1, count=6)],
            location_instances=[
                LocationInstance(location_id="chicken_coop", instance=1, unlock_level=1),
                LocationInstance(location_id="chicken_coop", instance=2, unlock_level=12),
            ],
        ),
    )


def test_validate_player_config_ok() -> None:
    cfg = PlayerConfig(
        level=20,
        fields_owned=6,
        locations={"chicken_coop": {"owned": 2, "animals": 12}, "dairy": {"slots": 3}},
    )
    assert validate_player_config(cfg, _dataset()) == []


def test_animals_default_to_unlocked_copies() -> None:
    # owned not given: 2 coops unlocked at level 20 → up to 12 chickens
    ok = PlayerConfig(level=20, locations={"chicken_coop": {"animals": 12}})
    too_many = PlayerConfig(level=20, locations={"chicken_coop": {"animals": 13}})
    assert validate_player_config(ok, _dataset()) == []
    assert "animals=13 exceeds 2 x 6" in validate_player_config(too_many, _dataset())[0]


def test_validate_player_config_problems() -> None:
    cfg = PlayerConfig(
        level=10,
        fields_owned=9,
        locations={
            "chicken_coop": {"owned": 2, "animals": 13},
            "field": {"slots": 2},
            "dairy": {"workbench_level": 2, "animals": 1},
            "sushi_bar": {"owned": 1},
            "unicorn_barn": {"owned": 1},
        },
    )
    problems = "\n".join(validate_player_config(cfg, _dataset()))

    assert "fields_owned=9" in problems
    assert "chicken_coop: owned=2 exceeds the 1 copies" in problems
    assert "chicken_coop: animals=13 exceeds 2 x 6" in problems
    assert "field: slots do not apply" in problems
    assert "dairy: animals only apply" in problems
    assert "sushi_bar: unlocks at level 56" in problems
    assert "unicorn_barn: unknown location id" in problems
    assert "dairy: workbench_level set" in problems


def test_example_config_matches_data() -> None:
    """The committed example must stay valid against the scraped data."""
    if not Path("data/locations.json").exists():
        pytest.skip("no real data")
    cfg = load_player_config(EXAMPLE_CONFIG)
    assert validate_player_config(cfg, load_data(Path("data"))) == []
