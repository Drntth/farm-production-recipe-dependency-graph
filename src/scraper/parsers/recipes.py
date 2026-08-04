"""Parse recipes (only production-location transformations)."""

from __future__ import annotations

import re
from typing import Any

from src.scraper.normalizer import to_snake_case
from src.scraper.wiki_client import WikiClient

from .resources import _cell_text, _extract_first_int, _parse_needs


def _is_recipe_source(source_text: str) -> bool:
    """Return True if the Source column points to a production building."""
    s = source_text.lower()

    non_recipe = (
        "field",
        "tree",
        "bush",
        "crop",
        "animal product",
        "chicken",
        "cow",
        "pig",
        "sheep",
        "goat",
        "bee",
        "lobster",
        "duck",
        "squirrel",
        "mine",
        "fishing",
        "n/a",
    )
    if any(k in s for k in non_recipe):
        return False
    return bool(source_text.strip()) and "n/a" not in s


def parse_recipes(client: WikiClient, max_level: int = 52) -> list[dict[str, Any]]:
    """
    Build recipes from the Goods List.

    Only rows whose Source is a production building become recipes.
    Animal products and raw crops are excluded (they are pure resources).
    """
    soup = client.get_goods_list()
    table = soup.find("table", class_=re.compile(r"wikitable|article-table|sortable"))
    if table is None:
        tables = soup.find_all("table")
        table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)

    if table is None:
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 7:
            continue

        name_cell = cells[0]
        name_link = name_cell.find("a")
        name = name_link.get_text(strip=True) if name_link else _cell_text(name_cell)
        if not name:
            continue

        level = _extract_first_int(_cell_text(cells[1]))
        if level is None or level > max_level:
            continue

        needs = _parse_needs(cells[5])
        source_text = _cell_text(cells[6])

        if not _is_recipe_source(source_text):
            continue

        source_link = cells[6].find("a")
        location_name = (
            source_link.get_text(strip=True)
            if source_link
            else source_text.split("(")[0].strip()
        )
        location_id = to_snake_case(location_name)
        location_id = re.sub(r"_x\d+$", "", location_id)

        recipe_id = to_snake_case(name)
        if recipe_id in seen:
            continue
        seen.add(recipe_id)

        inputs = [{"resource_id": to_snake_case(n), "amount": a} for n, a in needs if n]

        results.append(
            {
                "id": recipe_id,
                "name": name,
                "location_id": location_id,
                "unlock_level": level,
                "inputs": inputs,
                "output": {
                    "resource_id": recipe_id,
                    "amount": 1,
                },
            }
        )

    return results
