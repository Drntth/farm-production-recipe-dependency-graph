"""
Layout Planner CLI (farm).

Usage
-----
    python -m src.layout                       # level from the player config
    python -m src.layout --level 30
    python -m src.layout --map config/farm_map.json
    python -m src.layout --design-config my_design.json

Gap, reserve, strategy and the design layer are set in config/design.json
(``src/settings.py``), not on the command line.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.api import layout_plan, write_files
from src.api.core import layout_stems
from src.config import load_player_config
from src.farm_profile import farm_profile_of
from src.loaders.json_loader import data_directory, load_data
from src.settings import load_design_settings

from .farm_map import load_farm_map
from .planner import STRATEGIES
from .templates import load_template_files

logger = logging.getLogger("src.layout")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan the farm layout: named blocks, footprints, isometric SVG."
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
        help="Design settings (default: config/design.json, else "
        "config/design.example.json, else built-in defaults)",
    )
    parser.add_argument(
        "--farm-profile",
        type=Path,
        default=None,
        help="Farm profile: player, map, settings and templates in one file "
        "(instead of the separate files)",
    )
    return parser.parse_args(argv)


# file sets an earlier run may have written: strategy "all", or the town /
# fishing lake layouts of old versions
_KNOWN_STEMS = {f"layout_{s}" for s in (*STRATEGIES, "town", "fishing_lake")}


def _remove_stale(out: Path, stems: list[str]) -> None:
    """Remove the known ``layout_*`` file sets this run did not write."""
    for stem in sorted(_KNOWN_STEMS - set(stems)):
        for suffix in (".json", ".md", ".svg"):
            (out / f"{stem}{suffix}").unlink(missing_ok=True)


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
        settings, source, player = profile.design, args.farm_profile, profile.player
    else:
        try:
            settings, source = load_design_settings(args.design_config)
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

    try:
        farm_map = (
            profile.farm_map(args.data_dir / "base_map.json")
            if profile is not None
            else load_farm_map(args.farm_map, args.data_dir / "base_map.json")
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid farm map: %s", exc)
        return 1
    bg_path = farm_map.background_path()
    if bg_path is not None and not bg_path.exists():
        logger.warning(
            "Map background not found: %s (the SVG shows a broken image)", bg_path
        )

    try:
        templates = (
            profile.templates
            if profile is not None
            else load_template_files(settings.templates)
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Invalid design template: %s", exc)
        return 1

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Design settings: %s (%s)",
        source or "built-in defaults",
        ", ".join(f"{k}={v}" for k, v in settings.model_dump().items()),
    )

    try:
        full = load_data(args.data_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    try:
        run = layout_plan(
            full,
            player=player,
            level=args.level,
            farm_map=farm_map,
            design=settings,
            templates=templates,
            output_dir=out,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 1
    files = run["files"]
    stems = [stem for stem, _ in layout_stems(settings)]
    write_files(out, files)
    _remove_stale(out, stems)  # only after a full run
    images = [name for name in files if name.startswith("blocks/")]
    if images:
        logger.info("Wrote %d block images → %s", len(images), out / "blocks")
    logger.info("Wrote %s (.json, .md, .svg) → %s", ", ".join(stems), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
