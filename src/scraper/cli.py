"""
Command-line interface for the scraper.

Usage:
    python -m src.scraper                       # every level on the wiki
    python -m src.scraper --level 56 --output-dir data
    python -m src.scraper --game-version 1.72
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .normalizer import build_level_limits, build_mastery_bonuses, normalize
from .parsers.level_limits import parse_field_grants
from .parsers.locations import parse_locations
from .parsers.masteries import parse_masteries
from .parsers.recipes import parse_recipes
from .parsers.resources import parse_resources
from .wiki_client import WikiClient
from .writer import (
    write_json_files,
    write_level_limits_file,
    write_mastery_bonuses_file,
    write_meta_file,
)

_NO_LEVEL_CAP = 10_000


def _highest_level(*entity_lists: list[dict[str, Any]]) -> int:
    """Highest unlock level in the scraped data (``meta.json`` ``max_level``)."""
    return max(
        (e["unlock_level"] for entities in entity_lists for e in entities), default=0
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Hay Day production data from Fandom Wiki"
    )
    parser.add_argument(
        "--level",
        "--max-level",
        dest="level",
        type=int,
        default=None,
        help="Maximum unlock level to include (default: every level on the wiki)",
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
    args = parser.parse_args(argv)

    # the tools filter by the player level; the data covers every level
    level = args.level if args.level is not None else _NO_LEVEL_CAP
    print(
        "Scraping Hay Day data "
        + (f"up to level {level} …" if args.level is not None else "for every level …")
    )
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

    print("  → mastery bonuses")
    raw_bonuses = parse_masteries(client)
    print(f"     {len(raw_bonuses)} speed-up rows")

    print("  → normalize")
    locations, resources, recipes = normalize(raw_locations, raw_resources, raw_recipes)
    level_limits = build_level_limits(
        raw_locations, field_grants, {loc["id"] for loc in locations}
    )

    mastery_bonuses = build_mastery_bonuses(
        raw_bonuses, {loc["id"] for loc in locations}
    )

    write_json_files(args.output_dir, locations, resources, recipes)
    write_level_limits_file(args.output_dir, level_limits)
    write_mastery_bonuses_file(args.output_dir, mastery_bonuses)
    write_meta_file(
        args.output_dir,
        max_level=_highest_level(locations, resources, recipes),
        wiki_revisions=client.get_revision_timestamps(client.fetched_pages),
        known_game_version=args.game_version,
    )
    print(f"Done. Data written to {args.output_dir}/")


if __name__ == "__main__":
    main()
