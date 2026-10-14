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
import json
import logging
import sys
from pathlib import Path

from src.config import PlayerConfig, load_player_config, validate_player_config
from src.loaders.json_loader import load_data
from src.settings import load_planner_settings

from .run import run_planner
from .schedule import schedule_to_markdown

logger = logging.getLogger("src.planner")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan farm production: capacity, quantities, login schedule."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
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
    for problem in validate_player_config(player, full):
        logger.warning("Player config: %s", problem)

    data = full.filter_by_max_level(player.level)
    try:
        run = run_planner(
            player,
            data,
            login_interval=production.login_interval,
            storage_share=production.storage_share,
            min_efficiency=production.min_efficiency,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    for name in run.profile.missing():
        logger.warning("Player config: %s is not set; storage limits are unknown", name)
    capacity, chosen, schedule = run.capacity, run.chosen, run.schedule
    for warning in chosen.warnings:
        logger.warning("Plan: %s", warning)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "capacity.json").write_text(
        json.dumps(capacity.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "schedule.json").write_text(
        json.dumps(
            schedule | {"settings": production.model_dump()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "schedule.md").write_text(
        schedule_to_markdown(schedule, data), encoding="utf-8"
    )

    logger.info(
        "Level %d: barn %s, silo %s, %s fields (%s)",
        capacity.level,
        capacity.barn_capacity,
        capacity.silo_capacity,
        capacity.fields,
        capacity.fields_source,
    )
    logger.info(
        "Login every %g h: %.1f production hours per hour, %.2f spare per good "
        "and day, %d of %s fields used",
        chosen.interval_hours,
        chosen.busy_hours_per_hour,
        chosen.balance_per_hour * 24,
        round(chosen.fields_used),
        capacity.fields,
    )
    rec = schedule["recommendations"]["trees_and_bushes"]
    recommended = {k: v["plants"] for k, v in rec.items() if v["source"] != "profile"}
    if recommended:
        logger.info("Recommended trees / bushes: %s", recommended)
    if chosen.external_per_hour:
        logger.info(
            "Needed from outside the plan: %s",
            ", ".join(sorted(chosen.external_per_hour)),
        )
    logger.info("Wrote capacity.json, schedule.json, schedule.md → %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
