"""
Layout Planner CLI (farm).

Usage
-----
    python -m src.layout                       # level from the player config
    python -m src.layout --level 30
    python -m src.layout --farm-map config/farm_map.json --reserve 0.3
    python -m src.layout --design              # plus paths and decoration band
    python -m src.layout --area town --design  # town from config/town_map.json
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

from .area import plan_area_layout
from .describe import layout_to_dict, layout_to_markdown
from .design import DEFAULT_DECOR_BAND
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
        help="Block order: coupling (related blocks close), size (largest first), "
        "flow (upstream blocks first, then size if a block does not fit), auto "
        "(coupling, then size if a block does not fit) or all (auto as layout.*, plus "
        "layout_coupling.*, layout_size.* and layout_flow.*). Default: auto",
    )
    parser.add_argument(
        "--design",
        action="store_true",
        help="Add the design layer: paths between blocks and key buildings, and a "
        "decoration band along them (gap is at least 1)",
    )
    parser.add_argument(
        "--decor-band",
        type=int,
        default=DEFAULT_DECOR_BAND,
        help="Decoration band width in tiles next to the paths (default: 1)",
    )
    return parser.parse_args(argv)


def _write(layout, out: Path, stem: str) -> None:
    (out / f"{stem}.json").write_text(
        json.dumps(layout_to_dict(layout), ensure_ascii=False, indent=2),
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
    if args.reserve < 0 or args.gap < 0 or not 0 <= args.field_pool <= 1:
        logger.error("--reserve and --gap must not be negative; --field-pool is 0..1")
        return 1
    if args.decor_band < 0:
        logger.error("--decor-band must not be negative")
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
    if area != Area.FARM:
        ignored = [
            name
            for name, value, default in (
                ("--strategy", args.strategy, "auto"),
                ("--reserve", args.reserve, DEFAULT_RESERVE_RATIO),
                ("--field-pool", args.field_pool, DEFAULT_FIELD_POOL),
            )
            if value != default
        ]
        if ignored:
            logger.warning(
                "Farm-only options ignored for %s: %s", area.value, ", ".join(ignored)
            )
        layout = plan_area_layout(
            farm_map,
            level=level,
            gap=args.gap,
            design=args.design,
            decor_band=args.decor_band,
        )
        stem = f"layout_{area.value}"
        _write(layout, out, stem)
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
    runs = [("layout", "auto" if args.strategy == "all" else args.strategy)]
    if args.strategy == "all":
        runs += [(f"layout_{s}", s) for s in STRATEGIES if s != "auto"]

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
            design=args.design,
            decor_band=args.decor_band,
        )
        _write(layout, out, stem)
        logger.info(
            "%s: strategy %s (used: %s), reserve %.0f%%, %d blocks not placed",
            stem,
            strategy,
            layout.strategy,
            layout.reserve_ratio * 100,
            len(layout.unplaced_blocks),
        )

    _log_summary(layout, [stem for stem, _ in runs], out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
