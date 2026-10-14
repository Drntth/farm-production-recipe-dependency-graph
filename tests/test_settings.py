"""Tool settings: config/design*.json and config/planner*.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from src import settings as s
from src.layout.planner import STRATEGIES
from src.models import Area


def test_design_sections_merge_default_then_area() -> None:
    cfg = s.DesignSettings(
        default={"gap": 2, "design_layer": True},
        town={"gap": 0},
        farm={"strategy": "flow"},
    )
    farm = cfg.for_area(Area.FARM)
    assert (farm.gap, farm.design_layer, farm.strategy) == (2, True, "flow")
    assert farm.reserve == s.DEFAULT_RESERVE  # not set anywhere: built-in
    town = cfg.for_area(Area.TOWN)
    assert (town.gap, town.design_layer) == (0, True)
    assert "strategy" not in town.used(Area.TOWN)
    assert "strategy" in farm.used(Area.FARM)


def test_design_settings_reject_bad_values() -> None:
    with pytest.raises(ValidationError, match="farm-only"):
        s.DesignSettings(fishing_lake={"field_pool": 0.1})
    with pytest.raises(ValidationError):
        s.DesignSettings(default={"gap": -1})
    with pytest.raises(ValidationError):
        s.DesignSettings(farm={"strategy": "random"})
    with pytest.raises(ValidationError):
        s.DesignSettings(default={"unknown_key": 1})  # extra keys are forbidden
    with pytest.raises(ValidationError):
        s.DesignSettings(farm={"field_pool": 1.5})


def test_planner_settings_reject_bad_values() -> None:
    with pytest.raises(ValidationError):
        s.PlannerSettings(production={"login_interval": 0})
    with pytest.raises(ValidationError):
        s.PlannerSettings(production={"storage_share": 1.2})
    with pytest.raises(ValidationError):
        s.PlannerSettings(combiner={"lookahead": -1})
    with pytest.raises(ValidationError):
        s.PlannerSettings(combiner={"strategy": "all"})  # one layout only


def test_example_files_hold_the_built_in_defaults() -> None:
    design, _ = s.load_design_settings("config/design.example.json")
    for area in Area:
        assert design.for_area(area) == s.AreaDesign()
    planner, _ = s.load_planner_settings("config/planner.example.json")
    assert planner == s.PlannerSettings()


def test_strategies_match_the_layout_planner() -> None:
    assert set(get_args(s.Strategy)) == {*STRATEGIES, "all"}
    assert set(get_args(s.CombinerStrategy)) == set(STRATEGIES)


def test_load_settings_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # no file at all: built-in defaults
    monkeypatch.setattr(s, "CONFIG_DIR", tmp_path)
    assert s.load_design_settings() == (s.DesignSettings(), None)
    assert s.load_planner_settings() == (s.PlannerSettings(), None)
    # the example, then the local file
    example = tmp_path / "design.example.json"
    example.write_text(json.dumps({"default": {"gap": 2}}))
    assert s.load_design_settings()[1] == example
    local = tmp_path / "design.json"
    local.write_text(json.dumps({"default": {"gap": 3}}))
    cfg, source = s.load_design_settings()
    assert source == local and cfg.for_area(Area.FARM).gap == 3
    # an explicit path must exist
    with pytest.raises(FileNotFoundError):
        s.load_planner_settings(tmp_path / "missing.json")


def test_design_options_of_v1() -> None:
    cfg = s.DesignSettings(
        default={"path_style": "straight", "design_zones": False},
        farm={"item_gap": 1, "path_targets": "buildings"},
    )
    farm = cfg.for_area(Area.FARM)
    assert (farm.path_style, farm.item_gap, farm.path_targets) == (
        "straight",
        1,
        "buildings",
    )
    town = cfg.for_area(Area.TOWN)
    assert town.path_style == "straight" and town.design_zones is False
    assert "item_gap" not in town.used(Area.TOWN)
    with pytest.raises(ValidationError, match="item_gap"):
        s.DesignSettings(farm={"path_targets": "buildings", "design_layer": True})
    # without the design layer the paths do not matter: no error
    s.DesignSettings(farm={"path_targets": "buildings"})
    # farm-only keys of the default section apply to the farm only
    shared = s.DesignSettings(
        default={"path_targets": "buildings", "design_layer": True, "item_gap": 2}
    )
    town = shared.for_area(Area.TOWN)
    assert town.path_targets == "blocks" and town.item_gap == 0
    assert shared.for_area(Area.FARM).item_gap == 2
    with pytest.raises(ValidationError, match="farm-only"):
        s.DesignSettings(town={"item_gap": 1})
    with pytest.raises(ValidationError):
        s.DesignSettings(default={"path_style": "curvy"})
