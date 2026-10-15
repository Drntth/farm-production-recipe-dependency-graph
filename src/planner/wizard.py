"""
Interactive profile wizard (option D of docs/player-profile.md).

Asks only about what is unlocked at the player's level and writes the sparse
profile of option B: a value is written only when it differs from the level
default, so Enter always keeps the default.

1. level (required), mastery system (``stars`` or ``workbench``), barn and
   silo capacity, fields owned, fishing spots (once the fishing lake is
   unlocked);
2. one line per unlocked location, with its level defaults in brackets:
   Enter keeps them, ``slots=5 stars=3`` changes some (``owned``, ``slots``,
   ``stars`` or ``workbench``, ``animals``, ``beehives``, as far as they
   apply), ``?`` shows the keys of that location.

An existing output file is checked before the first question, so no answers
are lost to a "do not overwrite".

The question and answer functions are injectable, so the dialogue is tested
without a terminal. ``python -m src wizard`` writes ``config/player.json``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from src.config import LocationProgress, MasterySystem, PlayerConfig
from src.loaders.json_loader import DataSet, load_data
from src.models import LocationType

from .examples import to_json
from .profile import resolve_profile

DEFAULT_OUTPUT = Path("config/player.json")
FISHING_LAKE = "fishing_lake"
# short key typed by the player -> LocationProgress field
KEYS = {
    "owned": "owned",
    "slots": "slots",
    "stars": "mastery_stars",
    "workbench": "workbench_level",
    "animals": "animals",
    "beehives": "beehives",
}

Ask = Callable[[str], str]
Say = Callable[[str], None]
logger = logging.getLogger("src.planner.wizard")


def _ask_int(
    ask: Ask, say: Say, prompt: str, *, required: bool = False, minimum: int = 0
) -> int | None:
    while True:
        answer = ask(prompt).strip()
        if not answer and not required:
            return None
        try:
            value = int(answer)
        except ValueError:
            say("Please type a whole number" + ("" if required else ", or Enter"))
            continue
        if value < minimum:
            say(f"Please type at least {minimum}")
            continue
        return value


def _keys_for(
    dataset: DataSet, loc_id: str, defaults: dict, mastery: str = "stars"
) -> list[str]:
    """The short keys that apply to a location (*mastery*: stars / workbench)."""
    loc = dataset.locations[loc_id]
    keys = [k for k, field in KEYS.items() if defaults.get(field) is not None]
    if "owned" not in keys:
        keys.insert(0, "owned")
    if loc.type == LocationType.PRODUCTION and mastery not in keys:
        keys.append(mastery)
    return keys


def _ask_mastery(ask: Ask, say: Say) -> MasterySystem:
    while True:
        answer = ask("Mastery system, stars or workbench [stars]: ").strip().lower()
        if not answer:
            return MasterySystem.STARS
        try:
            return MasterySystem(answer)
        except ValueError:
            say("Please type stars or workbench, or Enter")


def _parse(answer: str, keys: list[str]) -> dict[str, int]:
    """``slots=5 stars=3`` -> {"slots": 5, "mastery_stars": 3}; ValueError if bad."""
    values: dict[str, int] = {}
    for part in answer.replace(",", " ").split():
        key, sep, raw = part.partition("=")
        if not sep or key not in keys:
            raise ValueError(f"use {', '.join(f'{k}=N' for k in keys)}")
        try:
            values[KEYS[key]] = int(raw)
        except ValueError:
            raise ValueError(f"{key} needs a whole number") from None
    return values


def run_wizard(dataset: DataSet, ask: Ask, say: Say) -> PlayerConfig:
    """Ask the questions; return the sparse, validated profile."""
    level = _ask_int(ask, say, "Your level: ", required=True, minimum=1)
    data = dataset.filter_by_max_level(level)
    defaults = resolve_profile(PlayerConfig(level=level), data)
    say("Enter keeps the value in brackets.")
    profile: dict = {"level": level}
    system = _ask_mastery(ask, say)
    if system != MasterySystem.STARS:
        profile["mastery_system"] = system.value
    mastery = "stars" if system == MasterySystem.STARS else "workbench"
    unused = KEYS["workbench" if mastery == "stars" else "stars"]
    for name, text in (
        ("barn_capacity", "Barn capacity [unknown]: "),
        ("silo_capacity", "Silo capacity [unknown]: "),
    ):
        value = _ask_int(ask, say, text, minimum=1)
        if value is not None:
            profile[name] = value
    granted = (
        f"all {defaults.fields_available} granted"
        if defaults.fields_available is not None
        else "unknown"
    )
    fields = _ask_int(ask, say, f"Fields owned [{granted}]: ")
    if fields is not None:
        profile["fields_owned"] = fields
    if FISHING_LAKE in data.locations:  # asked only once the lake is open
        spots = _ask_int(ask, say, "Fishing spots unlocked [unknown]: ")
        if spots is not None:
            profile["fishing_spots_unlocked"] = spots

    say(
        "Buildings, shelters, trees: Enter keeps the defaults, "
        f"e.g. slots=5 {mastery}=3"
    )
    locations: dict[str, dict] = {}
    for loc_id, state in defaults.locations.items():
        given = {
            field: getattr(state, field)
            for field in KEYS.values()
            if getattr(state, field) is not None
        }
        given.pop(unused, None)  # only the chosen mastery system is asked
        if dataset.locations[loc_id].type != LocationType.PRODUCTION:
            given.pop(KEYS[mastery], None)
        keys = _keys_for(data, loc_id, given, mastery)
        shown = ", ".join(
            f"{k} {given.get(KEYS[k], '?')}" for k in keys
        )  # ? = recommended by the planner
        name = data.locations[loc_id].name
        while True:
            answer = ask(f"{name} [{shown}]: ").strip()
            if answer == "?":
                say(f"keys: {', '.join(keys)}; ? = the planner recommends it")
                continue
            try:
                values = _parse(answer, keys)
                LocationProgress(**values)
            except (ValueError, ValidationError) as exc:
                say(f"Not understood: {exc}")
                continue
            break
        changed = {k: v for k, v in values.items() if given.get(k) != v}
        if changed:
            locations[loc_id] = changed
    if locations:
        profile["locations"] = locations
    return PlayerConfig.model_validate(profile)


def sparse_json(player: PlayerConfig) -> str:
    """The profile without unset values, one line per location."""
    data = player.model_dump(mode="json", exclude_none=True)
    data["locations"] = {
        k: {f: v for f, v in p.items() if v is not None}
        for k, p in data.get("locations", {}).items()
    }
    return to_json(data)


def main(argv: list[str] | None = None, ask: Ask = input, say: Say = print) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Answer a few questions; writes a sparse player profile."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        dataset = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    try:
        # before the questions, so no answers are lost to a "no"
        if args.output.exists():
            sure = ask(f"{args.output} exists. Overwrite? [y/N]: ").strip().lower()
            if sure not in ("y", "yes"):
                say("Nothing written.")
                return 1
        player = run_wizard(dataset, ask, say)
    except (EOFError, KeyboardInterrupt):
        say("\nStopped; nothing written.")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sparse_json(player), encoding="utf-8")
    say(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
