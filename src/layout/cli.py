"""
Layout Planner CLI (farm).

Usage
-----
    python -m src.layout                       # level from the player config
    python -m src.layout --level 30
    python -m src.layout --map config/farm_map.json
    python -m src.layout --area town           # town from config/town_map.json
    python -m src.layout --design-config my_design.json

Gap, reserve, strategy and the design layer are set in config/design.json
(``src/settings.py``), not on the command line.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import load_player_config, validate_player_config
from src.loaders.json_loader import load_data
from src.models import Area
from src.settings import AreaDesign, load_design_settings

from .area import plan_area_layout
from .describe import layout_to_dict, layout_to_markdown
from .farm_map import load_farm_map
from .planner import STRATEGIES, plan_layout
from .render_svg import render_svg
from .visuals import write_block_images

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
        "--area",
        choices=[a.value for a in Area],
        default=Area.FARM.value,
        help="Game area (default: farm). town / fishing_lake use only the measured "
        "map; their outputs are layout_<area>.*",
    )
    parser.add_argument(
        "--farm-map",
        "--map",
        dest="farm_map",
        type=Path,
        default=None,
        help="Area map (default: config/<area>_map.json, else "
        "config/<area>_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--design-config",
        type=Path,
        default=None,
        help="Design settings (default: config/design.json, else "
        "config/design.example.json, else built-in defaults)",
    )
    return parser.parse_args(argv)


def _write(layout, out: Path, stem: str, settings: AreaDesign) -> None:
    payload = layout_to_dict(layout) | {"settings": settings.used(layout.farm_map.area)}
    (out / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / f"{stem}.md").write_text(layout_to_markdown(layout), encoding="utf-8")
    render_svg(layout, out / f"{stem}.svg")


def _log_summary(layout, stems: list[str], out: Path) -> None:
    if layout.design is not None:
        d = layout.design
        logger.info(
            "Design: %d path tiles, %d decoration tiles%s%s",
            len(d.paths),
            len(d.decorations),
            f"; to connection point: {', '.join(sorted(d.approached))}"
            if d.approached
            else "",
            f"; not reachable: {', '.join(d.unreachable)}" if d.unreachable else "",
        )
    ext = layout.extent()
    logger.info(
        "%s level %d: %d blocks on %d x %d tiles",
        layout.farm_map.area.value,
        layout.level,
        len(layout.blocks),
        ext.w,
        ext.h,
    )
    for pb in layout.blocks:
        logger.info("  %s: %s", pb.block.name, ", ".join(pb.block.locations))
    logger.info("Wrote %s (.json, .md, .svg) → %s", ", ".join(stems), out)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    if args.level is not None and args.level < 1:
        logger.error("--level must be at least 1")
        return 1
    try:
        design_settings, source = load_design_settings(args.design_config)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid design settings: %s", exc)
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

    area = Area(args.area)
    try:
        farm_map = load_farm_map(args.farm_map, area)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid %s map: %s", area.value, exc)
        return 1
    if farm_map.area != area:
        logger.error("The map is for area %s, not %s", farm_map.area.value, area.value)
        return 1
    bg_path = farm_map.background_path()
    if bg_path is not None and not bg_path.exists():
        logger.warning(
            "Map background not found: %s (the SVG shows a broken image)", bg_path
        )

    level = args.level if args.level is not None else player.level
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    settings = design_settings.for_area(area)
    logger.info(
        "Design settings: %s (%s)",
        source or "built-in defaults",
        ", ".join(f"{k}={v}" for k, v in settings.used(area).items()),
    )
    if area != Area.FARM:
        layout = plan_area_layout(
            farm_map,
            level=level,
            gap=settings.gap,
            design=settings.design_layer,
            decor_band=settings.decor_band,
            path_style=settings.path_style,
            design_zones=settings.design_zones,
        )
        stem = f"layout_{area.value}"
        _write(layout, out, stem, settings)
        _log_summary(layout, [stem], out)
        return 0

    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    if player is not None:
        for problem in validate_player_config(player, full):
            logger.warning("Player config: %s", problem)

    # (output file stem, strategy); "all" adds one file set per fixed strategy
    runs = [("layout", "auto" if settings.strategy == "all" else settings.strategy)]
    if settings.strategy == "all":
        runs += [(f"layout_{s}", s) for s in STRATEGIES if s != "auto"]

    data = full.filter_by_max_level(level)
    for stem, strategy in runs:
        layout = plan_layout(
            data,
            level=level,
            player=player,
            farm_map=farm_map,
            reserve_ratio=settings.reserve,
            gap=settings.gap,
            field_pool=settings.field_pool,
            strategy=strategy,
            design=settings.design_layer,
            decor_band=settings.decor_band,
            item_gap=settings.item_gap,
            path_style=settings.path_style,
            path_targets=settings.path_targets,
            design_zones=settings.design_zones,
        )
        _write(layout, out, stem, settings)
        if stem == "layout":
            main_layout = layout
        logger.info(
            "%s: strategy %s (used: %s), reserve %.0f%%, %d blocks not placed",
            stem,
            strategy,
            layout.strategy,
            layout.reserve_ratio * 100,
            len(layout.unplaced_blocks),
        )

    if settings.block_images:  # of the main layout
        images = write_block_images(main_layout, out / "blocks")
        logger.info("Wrote %d block images → %s", len(images), out / "blocks")
    _log_summary(layout, [stem for stem, _ in runs], out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
