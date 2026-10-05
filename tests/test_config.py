import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import EXAMPLE_CONFIG, MasterySystem, load_player_config


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
