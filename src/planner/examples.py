"""
Ready-to-use player profiles for common levels (``config/examples/``).

Each example is the profile of a player who bought nothing beyond the level:
every value is the level default of ``resolve_profile`` written out, so the
player only edits what differs. No purchase is invented:

- ``fields_owned``: every field granted up to the level;
- per location: every unlocked copy, base slots, 0 mastery stars (production
  buildings only), full shelters, one beehive; trees and bushes ``owned: null`` (the planner
  recommends a count);
- ``barn_capacity`` / ``silo_capacity`` / ``fishing_spots_unlocked``: ``null``,
  because they are upgraded with supplies, not by level.

Regenerate after a re-scrape: ``python -m src examples``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import PlayerConfig
from src.loaders.json_loader import DataSet, load_data
from src.models import LocationType

from .profile import resolve_profile

EXAMPLE_LEVELS = (10, 20, 30, 40, 50)
EXAMPLE_DIR = Path("config/examples")
_FIELDS = ("owned", "slots", "mastery_stars", "animals", "beehives")

logger = logging.getLogger("src.planner.examples")


def example_profile(dataset: DataSet, level: int) -> dict:
    """The level-default profile of *level* as a JSON-ready dict."""
    data = dataset.filter_by_max_level(level)
    resolved = resolve_profile(PlayerConfig(level=level), data)
    locations = {}
    for loc_id, state in resolved.locations.items():
        values = {name: getattr(state, name) for name in _FIELDS}
        if data.locations[loc_id].type != LocationType.PRODUCTION:
            values["mastery_stars"] = None  # mastery is for production buildings
        # keep owned: null (to be recommended), drop what does not apply
        locations[loc_id] = {
            k: v for k, v in values.items() if v is not None or k == "owned"
        }
    return {
        "level": level,
        "mastery_system": resolved.mastery_system.value,
        "barn_capacity": None,
        "silo_capacity": None,
        "fields_owned": resolved.fields_available,
        "fishing_spots_unlocked": None,
        "locations": locations,
    }


def to_json(profile: dict) -> str:
    """Like config/player.example.json: one line per location."""
    head = {k: v for k, v in profile.items() if k != "locations"}
    lines = ["{"]
    lines += [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    lines.append('  "locations": {')
    items = list(profile["locations"].items())
    for i, (loc_id, values) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {json.dumps(loc_id)}: {json.dumps(values)}{comma}")
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def example_path(level: int, directory: Path = EXAMPLE_DIR) -> Path:
    return directory / f"player_level_{level}.json"


def write_examples(
    dataset: DataSet,
    directory: Path = EXAMPLE_DIR,
    levels: tuple[int, ...] = EXAMPLE_LEVELS,
) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for level in levels:
        path = example_path(level, directory)
        path.write_text(to_json(example_profile(dataset, level)), encoding="utf-8")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Write level-default player profiles to config/examples/."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=EXAMPLE_DIR)
    args = parser.parse_args(argv)
    try:
        dataset = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    for path in write_examples(dataset, args.output_dir):
        logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
