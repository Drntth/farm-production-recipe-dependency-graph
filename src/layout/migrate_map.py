"""
Split a one-file farm map (before v2.0) into a base map and a profile map.

Usage
-----
    python -m src migrate-map                     # config/farm_map.json → config/profile_map.json
    python -m src migrate-map --base-output data/base_map.json   # also write the geometry

The geometry (size, fixed buildings, plots, buildable / blocked zones) goes
to the base map, the player's part (unlocked plots, design zones, current
farm, background screenshot) to the profile map. Without ``--base-output``
the geometry is compared with ``<data-dir>/base_map.json``: the tools merge
the profile map with that file.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

from .farm_map import (
    LOCAL_MAP,
    LOCAL_PROFILE_MAP,
    FarmMap,
    base_map_json,
    is_one_file_map,
    load_base_map,
    merge_maps,
    profile_map_json,
    split_map,
)

logger = logging.getLogger("src.layout")


def map_json_text(data: dict[str, Any]) -> str:
    """A map as JSON with one line per object in a list (fixed item, plot, …)."""
    lines = ["{"]
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if isinstance(value, list) and any(isinstance(v, dict) for v in value):
            lines.append(f"  {json.dumps(key)}: [")
            for j, item in enumerate(value):
                end = "," if j < len(value) - 1 else ""
                lines.append(f"    {json.dumps(item, ensure_ascii=False)}{end}")
            lines.append(f"  ]{comma}")
        else:
            lines.append(
                f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}{comma}"
            )
    lines.append("}")
    return "\n".join(lines) + "\n"


def rebase_background(profile: dict[str, Any], source: Path, target: Path) -> None:
    """Keep the background image path valid next to the new file."""
    bg = profile.get("background")
    if bg is None or Path(bg["image"]).is_absolute():
        return
    image = source.parent / bg["image"]
    bg["image"] = Path(os.path.relpath(image, target.parent)).as_posix()


def migrate(
    source: Path,
    output: Path,
    *,
    base_output: Path | None = None,
    base_map: Path | None = None,
) -> list[Path]:
    """Write the profile map (and the base map); return the written files."""
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not is_one_file_map(data):
        raise ValueError(f"Not a one-file farm map: {source}")
    base, profile = split_map(FarmMap.model_validate(data))
    written = []
    if base_output is not None:
        base_output.parent.mkdir(parents=True, exist_ok=True)
        base_output.write_text(map_json_text(base_map_json(base)), encoding="utf-8")
        written.append(base_output)
    elif base_map is not None:
        shared = load_base_map(base_map)
        if shared != base:
            logger.warning(
                "The geometry of %s differs from %s; the tools merge the profile "
                "map with %s (write the measured geometry with --base-output)",
                source,
                base_map,
                base_map,
            )
        merge_maps(shared, profile)  # unknown unlocked plots are an error
    profile_data = profile_map_json(profile)
    rebase_background(profile_data, source, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(map_json_text(profile_data), encoding="utf-8")
    written.append(output)
    return written


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Split a one-file farm map into a base map and a profile map."
    )
    parser.add_argument("--map", type=Path, default=LOCAL_MAP, help="One-file map")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=LOCAL_PROFILE_MAP)
    parser.add_argument(
        "--base-output",
        type=Path,
        default=None,
        help="Also write the geometry as a base map (e.g. data/base_map.json)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite an existing profile map"
    )
    args = parser.parse_args(argv)
    if not args.map.exists():
        logger.error("Farm map not found: %s", args.map)
        return 1
    if args.output.exists() and not args.force:
        logger.error("%s exists; use --force to overwrite it", args.output)
        return 1
    base_map = None if args.base_output else args.data_dir / "base_map.json"
    try:
        written = migrate(
            args.map, args.output, base_output=args.base_output, base_map=base_map
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cannot migrate the farm map: %s", exc)
        return 1
    logger.info("Wrote %s", ", ".join(p.as_posix() for p in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
