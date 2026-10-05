"""
Farm Production Graph - Layout Planner entry point.

Usage
-----
    python -m src.main                      # level from config/player.json
    python -m src.main --level 30
    python -m src.main --data-dir data --level 30 --output-dir output
    python -m src.main --formats json --no-analysis
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import load_player_config, validate_player_config
from src.exporters import export_csv, export_graphml, export_json
from src.graph import analysis_summary, build_graph, graph_summary
from src.loaders.json_loader import load_data

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("src.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Hay Day production dependency graph and export it."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing locations.json, resources.json, recipes.json",
    )
    parser.add_argument(
        "--level",
        "--max-level",
        dest="level",
        type=int,
        default=None,
        help="Player level: only include entities with unlock_level <= this value "
        "(default: level from the player config)",
    )
    parser.add_argument(
        "--player-config",
        type=Path,
        default=None,
        help="Player config file (default: config/player.json, "
        "falling back to config/player.example.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for exported graph files",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["json", "csv", "graphml", "all"],
        default=["all"],
        help="Export formats to write (default: all)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip production-block / centrality analysis",
    )
    return parser.parse_args(argv)


def _log_analysis(summary: dict) -> None:
    blocks = summary["production_blocks"]
    logger.info("Production blocks: %d", len(blocks))
    for b in blocks[:8]:
        locs = ", ".join(b["locations"][:6])
        more = f" +{b['size'] - 6}" if b["size"] > 6 else ""
        logger.info("  block %d (size=%d): %s%s", b["id"], b["size"], locs, more)

    top = summary["centrality"]["betweenness"][:5]
    if top:
        logger.info("Top betweenness (bottlenecks):")
        for item in top:
            logger.info(
                "  %s (%s, %s) score=%.4f",
                item["id"],
                item.get("kind"),
                item.get("name"),
                item["score"],
            )

    couplings = summary["proximity_graph"]["top_couplings"][:5]
    if couplings:
        logger.info("Strongest location couplings:")
        for c in couplings:
            logger.info("  %s ↔ %s  w=%.2f", c["source"], c["target"], c["weight"])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.data_dir.is_dir():
        logger.error("Data directory does not exist: %s", args.data_dir)
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
        level = args.level if args.level is not None else player.level
        logger.info("Player level: %d", level)
        full_dataset = load_data(args.data_dir)
        dataset = full_dataset.filter_by_max_level(level)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1

    if player is not None:
        for problem in validate_player_config(player, full_dataset):
            logger.warning("Player config: %s", problem)

    logger.info("Loaded %s", dataset.summary())
    if dataset.level_limits is not None:
        limits = dataset.level_limits
        logger.info(
            "Level limits at level %d: %d fields, %d location instances",
            level,
            limits.fields_at(level),
            len(limits.location_instances),
        )

    graph = build_graph(dataset)
    logger.info("Built %s", graph_summary(graph))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    formats = set(args.formats)
    if "all" in formats:
        formats = {"json", "csv", "graphml"}

    written: list[str] = []

    if "json" in formats:
        p = export_json(graph, args.output_dir / "graph.json")
        written.append(str(p))
        logger.info("Wrote JSON  → %s", p)

    if "csv" in formats:
        nodes_p, edges_p = export_csv(graph, args.output_dir / "graph.csv")
        written.extend([str(nodes_p), str(edges_p)])
        logger.info("Wrote CSV   → %s , %s", nodes_p, edges_p)

    if "graphml" in formats:
        p = export_graphml(graph, args.output_dir / "graph.graphml")
        written.append(str(p))
        logger.info("Wrote GraphML → %s", p)

    if not args.no_analysis:
        summary = analysis_summary(graph)
        _log_analysis(summary)
        analysis_path = args.output_dir / "analysis.json"
        analysis_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(str(analysis_path.resolve()))
        logger.info("Wrote analysis → %s", analysis_path.resolve())

    logger.info("Done. %d file(s) written to %s", len(written), args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
