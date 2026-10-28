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

from src.layout.farm_map import load_farm_map
from src.loaders.json_loader import load_data

from .relocate import load_layout, plan_relocation
from .report import new_slot_note, relocation_to_dict, relocation_to_markdown

logger = logging.getLogger("src.relocation")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relocation plan: keep / store / place lists from the current "
        "farm to the planned layout."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
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
        help="Farm map with the current farm (default: config/farm_map.json, else "
        "config/farm_map.example.json)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
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
        layout = load_layout(path)
        farm_map = load_farm_map(args.farm_map)
        data = load_data(args.data_dir)
    except (OSError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    if not farm_map.current:
        logger.warning(
            "The farm map has no current farm: measure it in tools/farm_map_editor.html"
        )
    try:
        plan = plan_relocation(layout, farm_map, data)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    name = path.as_posix()
    (out / "relocation.json").write_text(
        json.dumps(relocation_to_dict(plan, name), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "relocation.md").write_text(
        relocation_to_markdown(plan, name), encoding="utf-8"
    )
    logger.info(
        "Relocation to %s: keep %d, store %d, place %d, reserved %d",
        name,
        len(plan.keep),
        sum(c.count for c in plan.store),
        len(plan.place),
        len(plan.reserved),
    )
    if note := new_slot_note(plan):
        logger.info("%s", note)
    logger.info("Wrote relocation (.json, .md) → %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
