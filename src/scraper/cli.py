"""
Command-line interface for the scraper.

Usage:
    python -m src.scraper                       # level from config/player.json
    python -m src.scraper --level 56 --output-dir data
    python -m src.scraper --game-version 1.72
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import load_player_config

from .normalizer import build_level_limits, normalize
from .parsers.level_limits import parse_field_grants
from .parsers.locations import parse_locations
from .parsers.recipes import parse_recipes
from .parsers.resources import parse_resources
from .wiki_client import WikiClient
from .writer import write_json_files, write_level_limits_file, write_meta_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Hay Day production data from Fandom Wiki"
    )
    parser.add_argument(
        "--level",
        "--max-level",
        dest="level",
        type=int,
        default=None,
        help="Maximum unlock level to include (default: level from the player config)",
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
        default=Path("data"),
        help="Directory for JSON output (default: data)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between wiki requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--game-version",
        default=None,
        help="Game version the data was checked against, stored in meta.json",
    )
    args = parser.parse_args()

    level = args.level
    if level is None:
        level = load_player_config(args.player_config).level

    print(f"Scraping Hay Day data up to level {level} …")
    client = WikiClient(delay=args.delay)

    print("  → locations")
    raw_locations = parse_locations(client, max_level=level)
    print(f"     {len(raw_locations)} raw locations")

    print("  → resources")
    raw_resources = parse_resources(client, max_level=level)
    print(f"     {len(raw_resources)} raw resources")

    print("  → recipes")
    raw_recipes = parse_recipes(client, max_level=level)
    print(f"     {len(raw_recipes)} raw recipes")

    print("  → field grants")
    field_grants = parse_field_grants(client, max_level=level)
    print(f"     {len(field_grants)} levels with new fields")

    print("  → normalize")
    locations, resources, recipes = normalize(raw_locations, raw_resources, raw_recipes)
    level_limits = build_level_limits(
        raw_locations, field_grants, {loc["id"] for loc in locations}
    )

    write_json_files(args.output_dir, locations, resources, recipes)
    write_level_limits_file(args.output_dir, level_limits)
    write_meta_file(
        args.output_dir,
        max_level=level,
        wiki_revisions=client.get_revision_timestamps(client.fetched_pages),
        known_game_version=args.game_version,
    )
    print(f"Done. Data written to {args.output_dir}/")


if __name__ == "__main__":
    main()
