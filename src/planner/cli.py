"""
Production Planner CLI (farm).

Usage
-----
    python -m src.planner                       # level from the player config
    python -m src.planner --level 30
    python -m src.planner --planner-config my_planner.json

Login interval, storage share and minimum efficiency are set in
config/planner.json (``src/settings.py``), not on the command line.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.api import production_plan, write_files
from src.config import PlayerConfig, load_player_config
from src.farm_profile import farm_profile_of
from src.loaders.json_loader import data_directory, load_data
from src.settings import load_planner_settings

logger = logging.getLogger("src.planner")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan farm production: capacity, quantities, login schedule."
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
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--planner-config",
        type=Path,
        default=None,
        help="Planner settings (default: config/planner.json, else "
        "config/planner.example.json, else built-in defaults)",
    )
    parser.add_argument(
        "--farm-profile",
        type=Path,
        default=None,
        help="Farm profile: player, map, settings and templates in one file "
        "(instead of the separate files)",
    )
    return parser.parse_args(argv)


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
        settings, source = profile.planner, args.farm_profile
    else:
        try:
            settings, source = load_planner_settings(args.planner_config)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Invalid planner settings: %s", exc)
            return 1
    production = settings.production
    logger.info(
        "Planner settings: %s (%s)",
        source or "built-in defaults",
        ", ".join(f"{k}={v}" for k, v in production.model_dump().items()),
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
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    try:
        run = production_plan(full, player=player, planner=settings)
    except (RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    out = args.output_dir
    write_files(out, run["files"])
    logger.info("Wrote capacity.json, schedule.json, schedule.md → %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
