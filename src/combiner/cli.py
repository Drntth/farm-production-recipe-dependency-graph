"""
Combiner CLI (farm): production plan + layout sized by it, one report.

Usage
-----
    python -m src.combiner                     # level from the player config
    python -m src.combiner --level 30
    python -m src.combiner --design-config my_design.json --planner-config my_planner.json

Settings come from config/design.json (farm section: gap, reserve, design
layer) and config/planner.json (production, combiner: lookahead, strategy).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import PlayerConfig, load_player_config, validate_player_config
from src.layout.farm_map import load_farm_map
from src.layout.render_svg import render_svg
from src.layout.templates import load_templates
from src.layout.visuals import write_block_images
from src.loaders.json_loader import load_data
from src.settings import load_design_settings, load_planner_settings

from .combine import combine
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
        design, design_source = load_design_settings(args.design_config)
        planner_settings, planner_source = load_planner_settings(args.planner_config)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid settings: %s", exc)
        return 1
    production, combiner = planner_settings.production, planner_settings.combiner
    logger.info(
        "Settings: design %s, planner %s",
        design_source or "built-in defaults",
        planner_source or "built-in defaults",
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
        farm_map = load_farm_map(args.farm_map)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm map: %s", exc)
        return 1

    try:
        templates = load_templates(design.templates)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid design template: %s", exc)
        return 1

    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    for issue in validate_player_config(player, full):
        logger.warning("Player config: %s", issue)
    max_level = _data_max_level(args.data_dir)
    if max_level is not None and player.level + combiner.lookahead > max_level:
        logger.info(
            "The data covers levels up to %d; unlocks above it are not known yet",
            max_level,
        )

    try:
        combined = combine(
            full,
            player,
            farm_map,
            lookahead=combiner.lookahead,
            login_interval=production.login_interval,
            storage_share=production.storage_share,
            min_efficiency=production.min_efficiency,
            reserve_ratio=design.reserve,
            gap=design.gap,
            strategy=combiner.strategy,
            design=design.design_layer,
            decor_band=design.decor_band,
            item_gap=design.item_gap,
            path_style=design.path_style,
            path_targets=design.path_targets,
            design_zones=design.design_zones,
            main_path_style=design.main_path_style,
            main_path_width=design.main_path_width,
            templates=templates,
        )
    except (RuntimeError, ValueError) as exc:
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
        json.dumps(
            combined_to_dict(combined, data)
            | {
                "settings": {
                    "design": design.model_dump(),
                    "production": production.model_dump(),
                    "combiner": combiner.model_dump(),
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / f"{STEM}.md").write_text(
        combined_to_markdown(combined, data), encoding="utf-8"
    )
    render_svg(combined.layout, out / f"{STEM}.svg")
    if design.block_images:
        images = write_block_images(combined.layout, out / f"{STEM}_blocks")
        logger.info("Wrote %d block images → %s", len(images), out / f"{STEM}_blocks")

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
