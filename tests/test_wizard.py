"""Interactive profile wizard, driven by scripted answers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import PlayerConfig, validate_player_config
from src.loaders.json_loader import DataSet, load_data
from src.planner import wizard

pytestmark = pytest.mark.skipif(
    not Path("data/locations.json").exists(), reason="no real data"
)
LEVEL = 20  # a test level; the code never hard-codes one


@pytest.fixture(scope="module")
def full() -> DataSet:
    return load_data("data")


class Script:
    """Answers questions from a list; Enter (empty) once the list runs out."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []
        self.said: list[str] = []

    def ask(self, prompt: str) -> str:
        self.asked.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def say(self, text: str) -> None:
        self.said.append(text)


def test_enter_everywhere_gives_the_bare_level(full: DataSet) -> None:
    script = Script([str(LEVEL)])
    player = wizard.run_wizard(full, script.ask, script.say)
    assert player == PlayerConfig(level=LEVEL)
    # only what is unlocked at the level is asked
    data = full.filter_by_max_level(LEVEL)
    names = {p.split(" [")[0] for p in script.asked}
    assert all(
        loc.name in names
        for loc in data.location_list
        if loc.type.value not in ("field", "storage")
    )
    assert not any(p.startswith("Fishing spots") for p in script.asked) or (
        "fishing_lake" in data.locations
    )


def test_changed_values_only_and_retries(full: DataSet) -> None:
    data = full.filter_by_max_level(LEVEL)
    # "x": not a number, asked again; "" = stars mastery
    head = ["x", str(LEVEL), "", "675", "", "30"]
    if "fishing_lake" in data.locations:
        head.append("")
    answers = []
    for loc_id in wizard.resolve_profile(PlayerConfig(level=LEVEL), data).locations:
        if loc_id == "feed_mill":
            answers.append("stars=3 slots=6")  # slots 6 = the default: not written
        elif loc_id == "chicken_coop":
            answers += ["stars=1", "animals=9"]  # a shelter has no stars: retry
        else:
            answers.append("")
    script = Script(head + answers)
    player = wizard.run_wizard(full, script.ask, script.say)

    assert script.asked.count("Your level: ") == 2
    assert player.barn_capacity == 675 and player.silo_capacity is None
    assert player.fields_owned == 30
    assert player.locations["feed_mill"].mastery_stars == 3
    assert player.locations["feed_mill"].slots is None
    assert player.locations["chicken_coop"].animals == 9
    assert set(player.locations) == {"feed_mill", "chicken_coop"}
    assert any("Not understood" in line for line in script.said)
    assert validate_player_config(player, full) == []


def test_parse() -> None:
    keys = ["owned", "slots", "stars"]
    assert wizard._parse("slots=5, stars=3", keys) == {"slots": 5, "mastery_stars": 3}
    assert wizard._parse("", keys) == {}
    with pytest.raises(ValueError):
        wizard._parse("animals=4", keys)
    with pytest.raises(ValueError):
        wizard._parse("slots=many", keys)


def test_main_writes_and_asks_before_overwriting(full: DataSet, tmp_path: Path) -> None:
    out = tmp_path / "player.json"
    script = Script([str(LEVEL), "", "500"])
    assert wizard.main(["--output", str(out)], script.ask, script.say) == 0
    data = json.loads(out.read_text())
    assert data["level"] == LEVEL and data["barn_capacity"] == 500
    assert data["locations"] == {}
    # an existing file is kept unless the answer is yes, asked before anything else
    keep = Script(["n"])
    assert wizard.main(["--output", str(out)], keep.ask, keep.say) == 1
    assert keep.asked == [f"{out} exists. Overwrite? [y/N]: "]
    assert json.loads(out.read_text())["barn_capacity"] == 500
    again = Script(["y", str(LEVEL), "", "600"])
    assert wizard.main(["--output", str(out)], again.ask, again.say) == 0
    assert json.loads(out.read_text())["barn_capacity"] == 600

    def stop(prompt: str) -> str:
        raise EOFError

    assert wizard.main(["--output", str(tmp_path / "x.json")], stop, print) == 1
    assert not (tmp_path / "x.json").exists()


def test_workbench_mastery(full: DataSet) -> None:
    data = full.filter_by_max_level(LEVEL)
    order = list(wizard.resolve_profile(PlayerConfig(level=LEVEL), data).locations)
    answers = ["workbench=2" if loc == "feed_mill" else "" for loc in order]
    head = [str(LEVEL), "chess", "workbench", "", "", ""]  # "chess": asked again
    if "fishing_lake" in data.locations:
        head.append("")
    script = Script(head + answers)
    player = wizard.run_wizard(full, script.ask, script.say)
    assert player.mastery_system.value == "workbench"
    assert player.locations["feed_mill"].workbench_level == 2
    assert not any("stars" in p for p in script.asked if p.startswith("Feed mill"))
    assert any("Please type stars or workbench" in line for line in script.said)


def test_fields_prompt_without_level_limits(full: DataSet) -> None:
    bare = DataSet(full.location_list, full.resource_list, full.recipe_list)
    script = Script([str(LEVEL)])
    wizard.run_wizard(bare, script.ask, script.say)
    assert "Fields owned [unknown]: " in script.asked
