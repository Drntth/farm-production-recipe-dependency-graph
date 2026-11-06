"""
Relocation plan CLI (farm).

Usage
-----
    python -m src.relocation                   # output/combined.json, else output/layout.json
    python -m src.relocation --layout output/layout.json
    python -m src.relocation --map config/farm_map.json

Measure the current farm (``current`` in the farm map) in the map editor first.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.api import relocation_plan, write_files
from src.farm_profile import farm_profile_of
from src.layout.farm_map import load_farm_map
from src.loaders.json_loader import data_directory, load_data

logger = logging.getLogger("src.relocation")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relocation plan: keep / store / place lists from the current "
        "farm to the planned layout."
    )
    parser.add_argument("--data-dir", type=data_directory, default=Path("data"))
    parser.add_argument(
        "--layout",
        type=Path,
        default=None,
        help="Layout to reach (default: OUTPUT_DIR/combined.json, else "
        "OUTPUT_DIR/layout.json)",
    )
    parser.add_argument(
        "--farm-map",
        "--map",
        dest="farm_map",
        type=Path,
        default=None,
        help="Farm map with the current farm "
        "(default: config/profile_map.json with <data-dir>/base_map.json, else the "
        "one-file config/farm_map.json, else config/farm_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--farm-profile",
        type=Path,
        default=None,
        help="Farm profile: player, map, settings and templates in one file "
        "(instead of the separate files)",
    )
    return parser.parse_args(argv)


def default_layout(out: Path) -> Path | None:
    """``combined.json``, else ``layout.json``; warns when the other one is newer."""
    combined, layout = out / "combined.json", out / "layout.json"
    if not combined.exists():
        return layout if layout.exists() else None
    if layout.exists() and layout.stat().st_mtime > combined.stat().st_mtime:
        logger.warning(
            "%s is newer than %s; run python -m src combine again, or pass --layout %s",
            layout,
            combined,
            layout,
        )
    return combined


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    out = args.output_dir
    path = args.layout or default_layout(out)
    if path is None:
        logger.error(
            "No layout found in %s; run python -m src combine (or layout) first", out
        )
        return 1
    try:
        layout = json.loads(path.read_text(encoding="utf-8"))
        profile = farm_profile_of(args)
        farm_map = (
            profile.farm_map(args.data_dir / "base_map.json")
            if profile is not None
            else load_farm_map(args.farm_map, args.data_dir / "base_map.json")
        )
        data = load_data(args.data_dir)
    except (OSError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    try:
        run = relocation_plan(
            data, layout=layout, farm_map=farm_map, layout_name=path.as_posix()
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 1
    write_files(out, run["files"])
    logger.info("Wrote relocation (.json, .md) → %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
