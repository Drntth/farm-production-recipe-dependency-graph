"""Tool settings: config/design*.json and config/planner*.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from src import settings as s
from src.layout.planner import STRATEGIES


def test_design_settings_fill_built_in_defaults() -> None:
    cfg = s.DesignSettings(gap=2, design_layer=True, strategy="flow")
    assert (cfg.gap, cfg.design_layer, cfg.strategy) == (2, True, "flow")
    assert cfg.reserve == s.DEFAULT_RESERVE  # not set: built-in


def test_design_settings_reject_bad_values() -> None:
    with pytest.raises(ValidationError):
        s.DesignSettings(gap=-1)
    with pytest.raises(ValidationError):
        s.DesignSettings(strategy="random")
    with pytest.raises(ValidationError):
        s.DesignSettings(unknown_key=1)  # extra keys are forbidden
    with pytest.raises(ValidationError):
        s.DesignSettings(field_pool=1.5)
    with pytest.raises(ValidationError, match="one flat object"):
        s.DesignSettings(default={"gap": 1})  # no sections any more


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
    assert design == s.DesignSettings()
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
    example.write_text(json.dumps({"gap": 2}))
    assert s.load_design_settings()[1] == example
    local = tmp_path / "design.json"
    local.write_text(json.dumps({"gap": 3}))
    cfg, source = s.load_design_settings()
    assert source == local and cfg.gap == 3
    # an explicit path must exist
    with pytest.raises(FileNotFoundError):
        s.load_planner_settings(tmp_path / "missing.json")


def test_design_options_of_v1() -> None:
    cfg = s.DesignSettings(
        path_style="straight", design_zones=False, item_gap=1, path_targets="buildings"
    )
    assert (cfg.path_style, cfg.item_gap, cfg.path_targets) == (
        "straight",
        1,
        "buildings",
    )
    assert cfg.design_zones is False
    with pytest.raises(ValidationError, match="item_gap"):
        s.DesignSettings(path_targets="buildings", design_layer=True)
    # without the design layer the paths do not matter: no error
    s.DesignSettings(path_targets="buildings")
    assert s.DesignSettings().block_images is True
    with pytest.raises(ValidationError):
        s.DesignSettings(path_style="curvy")
