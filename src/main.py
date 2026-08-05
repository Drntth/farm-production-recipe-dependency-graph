"""
Farm Production Graph - Layout Planner entry point.

Usage
-----
    python -m src.main
    python -m src.main --max-level 52
    python -m src.main --data-dir data --max-level 30
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.graph import build_graph, graph_summary
from src.loaders.json_loader import load_data

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("src.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Hay Day production dependency graph."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing locations.json, resources.json, recipes.json",
    )
    parser.add_argument(
        "--max-level",
        type=int,
        default=None,
        help="Only include entities with unlock_level <= this value",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for future export files (currently unused)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.data_dir.is_dir():
        logger.error("Data directory does not exist: %s", args.data_dir)
        return 1

    try:
        dataset = load_data(args.data_dir, max_level=args.max_level)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1

    logger.info("Loaded %s", dataset.summary())

    graph = build_graph(dataset)
    logger.info("Built %s", graph_summary(graph))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Graph ready. Exporters not yet implemented - output directory prepared at %s",
        args.output_dir,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
