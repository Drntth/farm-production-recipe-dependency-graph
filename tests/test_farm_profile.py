"""Farm profile: every player-side input in one file (src/farm_profile.py)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import get_args

import pytest

from src import cli
from src.combiner import cli as combiner_cli
from src.config import LocationProgress, PlayerConfig
from src.farm_profile import FarmProfile, load_farm_profile
from src.farm_profile import main as farm_profile_main
from src.layout import cli as layout_cli
from src.planner import cli as planner_cli
from src.schema import CURRENT, KEY

DATA_DIR = Path("data")
pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="data/locations.json not found"
)
LEVEL = 20
PLAYER = Path("config/player.example.json")
PROFILE_MAP = Path("config/profile_map.example.json")
PLANNER = Path("config/planner.example.json")


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Separate input files and the farm profile assembled from them."""
    tmp = tmp_path_factory.mktemp("fp")
    design = json.loads(Path("config/design.example.json").read_text()) | {
        "templates": {"dairy_block": {"template": "dairy_garden"}}
    }
    separate = {
        "player": PLAYER,
        "map": PROFILE_MAP,
        "design": _write(tmp / "design.json", design),
        "planner": PLANNER,
    }
    profile = tmp / "farm_profile.json"
    args = ["--player-config", str(separate["player"]), "--map", str(PROFILE_MAP)]
    args += ["--design-config", str(separate["design"])]
    args += ["--planner-config", str(PLANNER), "--name", "Test farm"]
    assert farm_profile_main([*args, "--output", str(profile)]) == 0
    return separate | {"profile": profile, "tmp": tmp}


def _outputs(out: Path) -> dict[str, str]:
    return {
        p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }


def test_assembled_profile_holds_every_part(files: dict[str, Path]) -> None:
    data = json.loads(files["profile"].read_text(encoding="utf-8"))
    assert data[KEY] == 1 and data["name"] == "Test farm"
    for part in ("player", "profile_map", "design", "planner"):
        assert data[part][KEY] == CURRENT[part], part
    assert data["templates"]["dairy_garden"][KEY] == 1
    profile = load_farm_profile(files["profile"])
    assert profile.player.level == json.loads(PLAYER.read_text())["level"]
    assert set(profile.templates) == {"dairy_garden"}
    assert KEY not in profile.model_dump()


@pytest.mark.parametrize(
    "tool, options",
    [
        (layout_cli, ("player", "map", "design")),
        (planner_cli, ("player", "planner")),
        (combiner_cli, ("player", "map", "design", "planner")),
    ],
)
def test_tools_give_the_same_outputs(files: dict[str, Path], tool, options) -> None:
    flag = {
        "player": "--player-config",
        "map": "--map",
        "design": "--design-config",
        "planner": "--planner-config",
    }
    name = tool.__name__.split(".")[1]
    sep, one = files["tmp"] / f"{name}_sep", files["tmp"] / f"{name}_one"
    args = ["--level", str(LEVEL)]
    separate = [x for o in options for x in (flag[o], str(files[o]))]
    assert tool.main([*args, *separate, "--output-dir", str(sep)]) == 0
    profile = ["--farm-profile", str(files["profile"])]
    assert tool.main([*args, *profile, "--output-dir", str(one)]) == 0
    assert _outputs(sep) and _outputs(one) == _outputs(sep)


def test_farm_profile_replaces_the_separate_files(
    files: dict[str, Path], caplog: pytest.LogCaptureFixture
) -> None:
    args = ["--farm-profile", str(files["profile"]), "--player-config", str(PLAYER)]
    with caplog.at_level(logging.ERROR):
        assert planner_cli.main(args) == 1
    assert "--farm-profile replaces --player-config" in caplog.text
    missing = ["--farm-profile", str(files["tmp"] / "missing.json")]
    assert layout_cli.main(missing) == 1


def test_player_part_keeps_the_player_file(files: dict[str, Path]) -> None:
    data = json.loads(files["profile"].read_text(encoding="utf-8"))
    source = json.loads(PLAYER.read_text(encoding="utf-8"))
    assert PlayerConfig.model_validate(data["player"]).model_dump() == (
        PlayerConfig.model_validate(source).model_dump()
    )


@pytest.mark.parametrize("model", [PlayerConfig, LocationProgress])
def test_nullable_player_fields_default_to_null(model) -> None:
    """The farm profile drops nulls; that is lossless only with null defaults."""
    nullable = {
        name: f
        for name, f in model.model_fields.items()
        if type(None) in get_args(f.annotation)
    }
    assert nullable and all(f.default is None for f in nullable.values())


def test_existing_output_needs_force(files: dict[str, Path]) -> None:
    out = ["--player-config", str(PLAYER), "--output", str(files["profile"])]
    assert farm_profile_main(out) == 1


def test_background_follows_the_profile(tmp_path: Path) -> None:
    profile_map = {"background": {"image": "shot.png", "image_width": 10}}
    profile_map["background"] |= {"image_height": 10, "origin_px": [5, 0]}
    profile_map["background"] |= {"x_axis_px": [1, 1], "y_axis_px": [-1, 1]}
    source = _write(tmp_path / "cfg" / "profile_map.json", profile_map)
    out = tmp_path / "farms" / "mine.json"
    args = ["--player-config", str(PLAYER), "--map", str(source)]
    assert farm_profile_main([*args, "--output", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["profile_map"]["background"]["image"] == "../cfg/shot.png"
    farm_map = load_farm_profile(out).farm_map(DATA_DIR / "base_map.json")
    assert farm_map.background_path() == (tmp_path / "cfg" / "shot.png").resolve()


def test_nested_parts_are_upgraded() -> None:
    data = {KEY: 1, "player": {KEY: 1, "level": 5}, "design": {KEY: 1}}
    assert FarmProfile.model_validate(data).player.level == 5
    with pytest.raises(ValueError, match="update the tools"):
        FarmProfile.model_validate({"player": {KEY: 99, "level": 5}})


def test_all_forwards_the_farm_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake(command):
        return lambda argv: calls.append((command, argv))

    monkeypatch.setattr(cli, "_tool", fake)
    assert cli.main(["all", "--farm-profile", "fp.json"]) == 0
    assert [c for c, _ in calls] == ["graph", "layout", "plan", "combine"]
    assert all(argv == ["--farm-profile", "fp.json"] for _, argv in calls)
