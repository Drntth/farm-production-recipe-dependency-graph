"""
Layout Planner CLI (farm).

Usage
-----
    python -m src.layout                       # level from the player config
    python -m src.layout --level 30
    python -m src.layout --farm-map config/farm_map.json --reserve 0.3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import load_player_config, validate_player_config
from src.loaders.json_loader import load_data

from .describe import layout_to_dict, layout_to_markdown
from .farm_map import load_farm_map
from .planner import (
    DEFAULT_FIELD_POOL,
    DEFAULT_GAP,
    DEFAULT_RESERVE_RATIO,
    STRATEGIES,
    plan_layout,
)
from .render_svg import render_svg

logger = logging.getLogger("src.layout")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan the farm layout: named blocks, footprints, isometric SVG."
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
        type=Path,
        default=None,
        help="Farm map (default: config/farm_map.json, else config/farm_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
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
        "--field-pool",
        type=float,
        default=DEFAULT_FIELD_POOL,
        help="Share of the fields kept in a separate shared block (default: 0)",
    )
    parser.add_argument(
        "--strategy",
        choices=(*STRATEGIES, "all"),
        default="auto",
        help="Block order: coupling (related blocks close), size (largest first), auto "
        "(coupling, then size if a block does not fit) or all (auto as layout.*, plus "
        "layout_coupling.* and layout_size.*). Default: auto",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    if args.reserve < 0 or args.gap < 0 or not 0 <= args.field_pool <= 1:
        logger.error("--reserve and --gap must not be negative; --field-pool is 0..1")
        return 1
    if args.level is not None and args.level < 1:
        logger.error("--level must be at least 1")
        return 1

    try:
        player = load_player_config(args.player_config)
    except FileNotFoundError:
        if args.level is None:
            logger.error("No player config found and no --level given")
            return 1
        player = None
    except ValueError as exc:
        logger.error("Invalid player config: %s", exc)
        return 1

    try:
        farm_map = load_farm_map(args.farm_map)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm map: %s", exc)
        return 1
    bg_path = farm_map.background_path()
    if bg_path is not None and not bg_path.exists():
        logger.warning(
            "Farm map background not found: %s (the SVG shows a broken image)", bg_path
        )

    level = args.level if args.level is not None else player.level
    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    if player is not None:
        for problem in validate_player_config(player, full):
            logger.warning("Player config: %s", problem)

    # (output file stem, strategy); "all" adds one file set per fixed strategy
    runs = [("layout", "auto" if args.strategy == "all" else args.strategy)]
    if args.strategy == "all":
        runs += [(f"layout_{s}", s) for s in STRATEGIES if s != "auto"]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    data = full.filter_by_max_level(level)
    for stem, strategy in runs:
        layout = plan_layout(
            data,
            level=level,
            player=player,
            farm_map=farm_map,
            reserve_ratio=args.reserve,
            gap=args.gap,
            field_pool=args.field_pool,
            strategy=strategy,
        )
        (out / f"{stem}.json").write_text(
            json.dumps(layout_to_dict(layout), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out / f"{stem}.md").write_text(layout_to_markdown(layout), encoding="utf-8")
        render_svg(layout, out / f"{stem}.svg")
        logger.info(
            "%s: strategy %s (used: %s), reserve %.0f%%, %d blocks not placed",
            stem,
            strategy,
            layout.strategy,
            layout.reserve_ratio * 100,
            len(layout.unplaced_blocks),
        )

    ext = layout.extent()
    logger.info(
        "Level %d: %d blocks on %d x %d tiles", level, len(layout.blocks), ext.w, ext.h
    )
    for pb in layout.blocks:
        logger.info("  %s: %s", pb.block.name, ", ".join(pb.block.locations))
    logger.info(
        "Wrote %s (.json, .md, .svg) → %s", ", ".join(stem for stem, _ in runs), out
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
