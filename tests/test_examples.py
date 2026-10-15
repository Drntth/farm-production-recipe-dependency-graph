"""Level-default player profiles in config/examples/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import PlayerConfig, validate_player_config
from src.loaders.json_loader import DataSet, load_data
from src.models import LocationType
from src.planner import examples

pytestmark = pytest.mark.skipif(
    not Path("data/locations.json").exists(), reason="no real data"
)


@pytest.fixture(scope="module")
def full() -> DataSet:
    return load_data("data")


def test_committed_examples_are_up_to_date(full: DataSet) -> None:
    """After a re-scrape: python -m src examples."""
    for level in examples.EXAMPLE_LEVELS:
        path = examples.example_path(level)
        assert path.exists(), path
        expected = examples.to_json(examples.example_profile(full, level))
        assert path.read_text(encoding="utf-8") == expected, path


def test_examples_hold_level_defaults_only(full: DataSet) -> None:
    for level in examples.EXAMPLE_LEVELS:
        profile = examples.example_profile(full, level)
        player = PlayerConfig.model_validate(profile)
        assert validate_player_config(player, full) == []
        assert player.barn_capacity is None and player.silo_capacity is None
        assert player.fields_owned == full.level_limits.fields_at(level)
        for loc_id, progress in player.locations.items():
            loc = full.locations[loc_id]
            assert loc.unlock_level <= level
            if loc.type in (LocationType.TREE, LocationType.BUSH):
                assert progress.owned is None  # recommended by the planner
            if loc.type != LocationType.PRODUCTION:
                assert progress.mastery_stars is None
            elif progress.mastery_stars is not None:
                assert progress.mastery_stars == 0


def test_write_examples(full: DataSet, tmp_path: Path) -> None:
    paths = examples.write_examples(full, tmp_path, levels=(10,))
    assert paths == [tmp_path / "player_level_10.json"]
    assert json.loads(paths[0].read_text())["level"] == 10
    assert examples.main(["--output-dir", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("player_level_*.json"))) == len(
        examples.EXAMPLE_LEVELS
    )
