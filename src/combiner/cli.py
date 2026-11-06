"""
Combiner CLI (farm): production plan + layout sized by it, one report.

Usage
-----
    python -m src.combiner                     # level from the player config
    python -m src.combiner --level 30
    python -m src.combiner --design-config my_design.json --planner-config my_planner.json

Settings come from config/design.json (gap, reserve, design layer) and
config/planner.json (production, combiner: lookahead, strategy).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.api import combined_plan, write_files
from src.api.core import COMBINED_STEM as STEM
from src.config import PlayerConfig, load_player_config
from src.farm_profile import farm_profile_of
from src.layout.farm_map import load_farm_map
from src.layout.templates import load_template_files
from src.loaders.json_loader import data_directory, load_data
from src.settings import load_design_settings, load_planner_settings

logger = logging.getLogger("src.combiner")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine the production plan and the farm layout: blocks "
        "sized by the plan, placed in processing order, one report."
    )
    parser.add_argument("--data-dir", type=data_directory, default=Path("data"))
    parser.add_argument(
        "--level",
        type=int,
        default=None,
        help="Player level (default: level from the player config)",
    )
    parser.add_argument(
        "--player-config",
        type=Path,
        default=None,
        help="Player config (default: config/player.json, else config/player.example.json)",
    )
    parser.add_argument(
        "--farm-map",
        "--map",
        dest="farm_map",
        type=Path,
        default=None,
        help="Farm map "
        "(default: config/profile_map.json with <data-dir>/base_map.json, else the "
        "one-file config/farm_map.json, else config/farm_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--design-config",
        type=Path,
        default=None,
        help="Design settings (default: config/design.json, else the example)",
    )
    parser.add_argument(
        "--planner-config",
        type=Path,
        default=None,
        help="Planner settings (default: config/planner.json, else the example)",
    )
    parser.add_argument(
        "--farm-profile",
        type=Path,
        default=None,
        help="Farm profile: player, map, settings and templates in one file "
        "(instead of the separate files)",
    )
    return parser.parse_args(argv)


def _data_max_level(data_dir: Path) -> int | None:
    try:
        meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    level = meta.get("max_level")
    return level if isinstance(level, int) else None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    if args.level is not None and args.level < 1:
        logger.error("--level must be at least 1")
        return 1
    try:
        profile = farm_profile_of(args)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm profile: %s", exc)
        return 1
    if profile is not None:
        design, planner_settings = profile.design, profile.planner
        design_source = planner_source = args.farm_profile
    else:
        try:
            design, design_source = load_design_settings(args.design_config)
            planner_settings, planner_source = load_planner_settings(
                args.planner_config
            )
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Invalid settings: %s", exc)
            return 1
    logger.info(
        "Settings: design %s, planner %s",
        design_source or "built-in defaults",
        planner_source or "built-in defaults",
    )

    if profile is not None:
        player = profile.player
    else:
        try:
            player = load_player_config(args.player_config)
        except FileNotFoundError:
            if args.level is None:
                logger.error("No player config found and no --level given")
                return 1
            player = PlayerConfig(level=args.level)
        except ValueError as exc:
            logger.error("Invalid player config: %s", exc)
            return 1
    if args.level is not None:
        player = player.model_copy(update={"level": args.level})

    try:
        farm_map = (
            profile.farm_map(args.data_dir / "base_map.json")
            if profile is not None
            else load_farm_map(args.farm_map, args.data_dir / "base_map.json")
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm map: %s", exc)
        return 1

    try:
        templates = (
            profile.templates
            if profile is not None
            else load_template_files(design.templates)
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid design template: %s", exc)
        return 1

    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    out = args.output_dir
    try:
        run = combined_plan(
            full,
            player=player,
            farm_map=farm_map,
            design=design,
            planner=planner_settings,
            templates=templates,
            data_max_level=_data_max_level(args.data_dir),
            output_dir=out,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    files = run["files"]
    write_files(out, files)
    images = [name for name in files if name.startswith(f"{STEM}_blocks/")]
    if images:
        logger.info("Wrote %d block images → %s", len(images), out / f"{STEM}_blocks")
    logger.info("Wrote %s (.json, .md, .svg) → %s", STEM, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
