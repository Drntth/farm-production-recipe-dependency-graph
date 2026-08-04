"""
Command-line interface for the scraper.

Usage:
    python -m src.scraper --max-level 52
    python -m src.scraper --max-level 52 --output-dir data
"""

from __future__ import annotations

import argparse
from pathlib import Path

from normalizer import normalize
from parsers.locations import parse_locations
from parsers.recipes import parse_recipes
from parsers.resources import parse_resources
from wiki_client import WikiClient
from writer import write_json_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Hay Day production data from Fandom Wiki"
    )
    parser.add_argument(
        "--max-level",
        type=int,
        default=52,
        help="Maximum unlock level to include (default: 52)",
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
    args = parser.parse_args()

    print(f"Scraping Hay Day data up to level {args.max_level} …")
    client = WikiClient(delay=args.delay)

    print("  → locations")
    raw_locations = parse_locations(client, max_level=args.max_level)
    print(f"     {len(raw_locations)} raw locations")

    print("  → resources")
    raw_resources = parse_resources(client, max_level=args.max_level)
    print(f"     {len(raw_resources)} raw resources")

    print("  → recipes")
    raw_recipes = parse_recipes(client, max_level=args.max_level)
    print(f"     {len(raw_recipes)} raw recipes")

    print("  → normalize")
    locations, resources, recipes = normalize(raw_locations, raw_resources, raw_recipes)

    write_json_files(args.output_dir, locations, resources, recipes)
    print(f"Done. Data written to {args.output_dir}/")


if __name__ == "__main__":
    main()
