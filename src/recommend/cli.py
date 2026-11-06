"""
Level recommendations CLI: one JSON and one SVG per level for the web site.

Usage
-----
    python -m src recommend                    # levels 1-100 → output/recommendations/
    python -m src recommend --levels 1,10,40   # only these levels
    python -m src recommend --levels 30-50 --output-dir web/data

Every level uses its level-default profile, the built-in settings and the
base map with only section ``base`` unlocked; see ``build.py``. The files are
generated, not committed. A run over levels 1-100 takes a few minutes.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import tomllib
from pathlib import Path

from src.api import write_files
from src.layout.farm_map import load_base_map
from src.loaders.json_loader import data_directory, load_data

from .build import DEFAULT_LEVELS, recommendations

logger = logging.getLogger("src.recommend")

DEFAULT_OUTPUT = Path("output") / "recommendations"
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
# the tools' per-level warnings (unset barn capacity, blocks that do not
# fit, …) repeat for every level; the level JSON keeps what matters
QUIET = ("src.graph", "src.layout", "src.planner", "src.combiner")
# far above any game level; stops a typo like 1-1000000 before it builds the set
LEVEL_LIMIT = 1000


def parse_levels(value: str) -> tuple[int, ...]:
    """``"1-100"``, ``"1,10,40"`` or a mix (``"1-5,40"``) → sorted levels."""
    levels: set[int] = set()
    try:
        for part in value.split(","):
            part = part.strip()
            if "-" in part:
                low, high = (int(x) for x in part.split("-", 1))
                if low > high:
                    raise ValueError
                if high > LEVEL_LIMIT:
                    raise argparse.ArgumentTypeError(
                        f"levels must be at most {LEVEL_LIMIT}"
                    )
                levels |= set(range(low, high + 1))
            else:
                level = int(part)
                if level > LEVEL_LIMIT:
                    raise argparse.ArgumentTypeError(
                        f"levels must be at most {LEVEL_LIMIT}"
                    )
                levels.add(level)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid levels {value!r}; use e.g. 1-100 or 1,10,40"
        ) from None
    if not levels or min(levels) < 1:
        raise argparse.ArgumentTypeError("levels must be at least 1")
    return tuple(sorted(levels))


def core_version(path: Path = PYPROJECT) -> str | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return None


def _meta(data_dir: Path) -> dict:
    try:
        return json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the level recommendations (combined plan of every "
        "level-default profile on section base) for the web site."
    )
    parser.add_argument("--data-dir", type=data_directory, default=Path("data"))
    parser.add_argument(
        "--levels",
        type=parse_levels,
        default=DEFAULT_LEVELS,
        help="Levels to write, e.g. 1-100 (default) or 1,10,40",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    try:
        data = load_data(args.data_dir)
        base = load_base_map(args.data_dir / "base_map.json")
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1
    meta = _meta(args.data_dir)
    max_level = meta.get("max_level")
    max_level = max_level if isinstance(max_level, int) else None

    saved = {name: logging.getLogger(name).level for name in QUIET}
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.ERROR)
    start = time.monotonic()
    try:
        run = recommendations(
            data,
            base,
            args.levels,
            game_version=meta.get("known_game_version"),
            core_version=core_version(),
            data_max_level=max_level,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    finally:
        for name, level in saved.items():
            logging.getLogger(name).setLevel(level)

    try:
        write_files(args.output_dir, run["files"])
    except OSError as exc:
        logger.error("Failed to write %s: %s", args.output_dir, exc)
        return 1
    rows = run["result"]["levels"]
    partial = [str(r["level"]) for r in rows if r["blocks_not_placed"]]
    logger.info(
        "Wrote %d level recommendations → %s (%.0f s)",
        len(rows),
        args.output_dir,
        time.monotonic() - start,
    )
    if partial:
        logger.info(
            "Blocks not placed on section base at %d levels (first: %s)",
            len(partial),
            partial[0],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
