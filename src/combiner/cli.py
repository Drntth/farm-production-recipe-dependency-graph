"""
Combiner CLI (farm): production plan + layout sized by it, one report.

Usage
-----
    python -m src.combiner                     # level from the player config
    python -m src.combiner --level 30 --lookahead 3
    python -m src.combiner --design            # plus paths and decoration band
    python -m src.combiner --login-interval 4 --strategy auto
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import PlayerConfig, load_player_config, validate_player_config
from src.layout.design import DEFAULT_DECOR_BAND
from src.layout.farm_map import load_farm_map
from src.layout.planner import DEFAULT_GAP, DEFAULT_RESERVE_RATIO, STRATEGIES
from src.layout.render_svg import render_svg
from src.loaders.json_loader import load_data
from src.models import Area
from src.planner.quantities import DEFAULT_STORAGE_SHARE
from src.planner.schedule import DEFAULT_MIN_EFFICIENCY

from .combine import DEFAULT_LOOKAHEAD, DEFAULT_STRATEGY, combine
from .report import combined_to_dict, combined_to_markdown

logger = logging.getLogger("src.combiner")
STEM = "combined"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine the production plan and the farm layout: blocks "
        "sized by the plan, placed in processing order, one report."
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
    parser.add_argument(
        "--farm-map",
        "--map",
        dest="farm_map",
        type=Path,
        default=None,
        help="Farm map (default: config/farm_map.json, else config/farm_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--login-interval",
        type=float,
        default=None,
        help="Hours between logins (default: suggested from the candidates)",
    )
    parser.add_argument(
        "--storage-share",
        type=float,
        default=DEFAULT_STORAGE_SHARE,
        help="Share of barn and silo the goods of one interval may fill (default: 0.5)",
    )
    parser.add_argument(
        "--min-efficiency",
        type=float,
        default=DEFAULT_MIN_EFFICIENCY,
        help="Suggested interval: longest one with at least this share of the "
        "best production time (default: 0.8)",
    )
    parser.add_argument(
        "--reserve",
        type=float,
        default=DEFAULT_RESERVE_RATIO,
        help="Extra free area per block for later unlocks (default: 0.2 = 20%%)",
    )
    parser.add_argument(
        "--gap",
        type=int,
        default=DEFAULT_GAP,
        help="Free tiles between blocks (default: 1)",
    )
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=DEFAULT_STRATEGY,
        help="Block order (default: flow = upstream blocks first, then size if a "
        "block does not fit)",
    )
    parser.add_argument(
        "--lookahead",
        type=int,
        default=DEFAULT_LOOKAHEAD,
        help="Levels ahead whose unlocks get space now (default: 5; 0 = none)",
    )
    parser.add_argument(
        "--design",
        action="store_true",
        help="Add the design layer: paths and a decoration band (gap is at least 1)",
    )
    parser.add_argument(
        "--decor-band",
        type=int,
        default=DEFAULT_DECOR_BAND,
        help="Decoration band width in tiles next to the paths (default: 1)",
    )
    return parser.parse_args(argv)


def _check_args(args: argparse.Namespace) -> str | None:
    if args.level is not None and args.level < 1:
        return "--level must be at least 1"
    if args.login_interval is not None and args.login_interval <= 0:
        return "--login-interval must be positive"
    if not 0 < args.storage_share <= 1 or not 0 < args.min_efficiency <= 1:
        return "--storage-share and --min-efficiency must be in (0, 1]"
    if min(args.reserve, args.gap, args.lookahead, args.decor_band) < 0:
        return "--reserve, --gap, --lookahead and --decor-band must not be negative"
    return None


def _data_max_level(data_dir: Path) -> int | None:
    try:
        meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    level = meta.get("max_level")
    return level if isinstance(level, int) else None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    problem = _check_args(args)
    if problem:
        logger.error(problem)
        return 1

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
        farm_map = load_farm_map(args.farm_map, Area.FARM)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm map: %s", exc)
        return 1
    if farm_map.area != Area.FARM:
        logger.error("The map is for area %s, not farm", farm_map.area.value)
        return 1

    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    for issue in validate_player_config(player, full):
        logger.warning("Player config: %s", issue)
    max_level = _data_max_level(args.data_dir)
    if max_level is not None and player.level + args.lookahead > max_level:
        logger.info(
            "The data covers levels up to %d; unlocks above it are not known yet",
            max_level,
        )

    try:
        combined = combine(
            full,
            player,
            farm_map,
            lookahead=args.lookahead,
            login_interval=args.login_interval,
            storage_share=args.storage_share,
            min_efficiency=args.min_efficiency,
            reserve_ratio=args.reserve,
            gap=args.gap,
            strategy=args.strategy,
            design=args.design,
            decor_band=args.decor_band,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    for name in combined.run.profile.missing():
        logger.warning("Player config: %s is not set; storage limits are unknown", name)
    for warning in combined.warnings:
        logger.warning("%s", warning)

    data = combined.dataset
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{STEM}.json").write_text(
        json.dumps(combined_to_dict(combined, data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / f"{STEM}.md").write_text(
        combined_to_markdown(combined, data), encoding="utf-8"
    )
    render_svg(combined.layout, out / f"{STEM}.svg")

    layout, plan = combined.layout, combined.run.chosen
    logger.info(
        "Level %d: login every %g h, %d blocks (%d not placed), strategy %s, "
        "reserve %.0f%%",
        combined.level,
        plan.interval_hours,
        len(layout.blocks),
        len(layout.unplaced_blocks),
        layout.strategy,
        layout.reserve_ratio * 100,
    )
    if combined.flow_links:
        top = combined.flow_links[0]
        logger.info(
            "Heaviest flow: %s → %s, %.1f goods/h, %s tiles apart",
            top.source,
            top.target,
            top.per_hour,
            "-" if top.distance is None else top.distance,
        )
    logger.info("Wrote %s (.json, .md, .svg) → %s", STEM, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
