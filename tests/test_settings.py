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
    for window in ({"logins": 0}, {"logins": 49}, {"start": "24:00"}, {"end": "7:00"}):
        with pytest.raises(ValidationError):
            s.PlannerSettings(production={"login_window": window})
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


def test_path_network_options_of_v1_4() -> None:
    cfg = s.DesignSettings()
    assert (cfg.main_path_width, cfg.main_path_style) == (1, None)
    cfg = s.DesignSettings(
        path_style="stepped", main_path_style="straight", main_path_width=2
    )
    assert (cfg.path_style, cfg.main_path_style, cfg.main_path_width) == (
        "stepped",
        "straight",
        2,
    )
    for bad in (
        {"main_path_width": 3},
        {"main_path_width": 0},
        {"main_path_style": "x"},
    ):
        with pytest.raises(ValidationError):
            s.DesignSettings(**bad)


def test_login_window_gaps_and_times() -> None:
    w = s.LoginWindow()  # 07:00-23:00
    assert w.window_hours() == 16
    assert w.gaps(5) == [4, 4, 4, 4, 8]  # the night is the long gap
    assert w.times(5) == ["07:00", "11:00", "15:00", "19:00", "23:00"]
    assert w.gaps(1) == [24] and w.times(1) == ["07:00"]
    assert sum(s.LoginWindow(start="08:30", end="21:10").gaps(4)) == pytest.approx(24)


def test_login_window_round_the_clock_and_past_midnight() -> None:
    whole = s.LoginWindow(start="00:00", end="00:00")
    assert whole.gaps(8) == [3] * 8  # the former even login interval
    late = s.LoginWindow(start="22:00", end="02:00")
    assert late.window_hours() == 4
    assert late.times(3) == ["22:00", "00:00", "02:00"]
    assert late.gaps(3) == [2, 2, 20]
    with pytest.raises(ValueError):
        late.gaps(0)


def test_planner_settings_map_the_old_login_interval(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # a file without schema_version is version 1: an interval that divides
    # the day becomes the same logins round the clock
    old = s.PlannerSettings.model_validate({"production": {"login_interval": 3}})
    assert old.production.login_window == s.LoginWindow(
        start="00:00", end="00:00", logins=8
    )
    assert old.production.login_window.gaps(8) == [3.0] * 8
    assert caplog.text == ""
    s.PlannerSettings.model_validate({"production": {"login_interval": None}})
    assert caplog.text == ""  # nothing set, nothing lost
    # an interval that does not divide the day is dropped with a warning
    odd = s.PlannerSettings.model_validate({"production": {"login_interval": 5}})
    assert odd.production.login_window == s.LoginWindow()
    assert "login_interval 5 is no longer used" in caplog.text
    caplog.clear()
    # a login window already set wins
    both = s.PlannerSettings.model_validate(
        {"production": {"login_interval": 3, "login_window": {"logins": 4}}}
    )
    assert both.production.login_window.logins == 4
    assert "login_interval 3 is no longer used" in caplog.text
    with pytest.raises(ValidationError):  # version 2 knows no login_interval
        s.PlannerSettings.model_validate(
            {"schema_version": 2, "production": {"login_interval": 3}}
        )
