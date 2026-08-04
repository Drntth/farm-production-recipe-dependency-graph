"""Parse all resources (crops, animal products, processed materials, ores)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import NavigableString, Tag

from src.scraper.normalizer import to_snake_case
from src.scraper.wiki_client import WikiClient


def _extract_first_int(text: str) -> int | None:
    m = re.search(r"(\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else None


def _cell_text(cell: Tag) -> str:
    return cell.get_text(" ", strip=True)


def _parse_needs(cell: Tag) -> list[tuple[str, int]]:
    """Parse the 'Needs' column into list of (resource_name, amount)."""
    results: list[tuple[str, int]] = []
    for a in cell.find_all("a"):
        name = a.get_text(strip=True)
        amount = 1
        next_sib = a.next_sibling
        if isinstance(next_sib, NavigableString):
            m = re.search(r"\((\d+)\)", str(next_sib))
            if m:
                amount = int(m.group(1))
        results.append((name, amount))
    if not results:
        text = _cell_text(cell)
        for m in re.finditer(r"([A-Za-z][A-Za-z0-9 '.-]+?)\s*\((\d+)\)", text):
            results.append((m.group(1).strip(), int(m.group(2))))
    return results


def _classify_type_and_source(
    name: str, source_text: str, needs: list[tuple[str, int]]
) -> tuple[str, str]:
    """
    Return (resource_type, source_location_id).

    Heuristics based on the Source column of the Goods List.
    """
    source_lower = source_text.lower()
    name_lower = name.lower()

    animal_source_map = {
        "chicken": "chicken_coop",
        "cow": "cow_pasture",
        "pig": "pig_pen",
        "sheep": "sheep_pasture",
        "lamb": "lamb_pasture",
        "goat": "goat_yard",
        "bee": "beehive_tree",
        "honeycomb": "beehive_tree",
        "beehive": "beehive_tree",
        "lobster": "lobster_pool",
        "duck": "duck_salon",
        "squirrel": "squirrel_house",
        "fish": "fishing_lake",
    }

    animal_product_names = {
        "egg",
        "milk",
        "bacon",
        "wool",
        "goat milk",
        "honeycomb",
        "lamb chop",
        "fish fillet",
        "lobster tail",
        "duck feather",
        "peanuts",
    }

    if "ore" in name_lower or ("mine" in source_lower and "animal" not in source_lower):
        return "ore", "mine"

    is_animal_source = any(k in source_lower for k in animal_source_map)
    is_animal_name = name_lower in animal_product_names or any(
        k in name_lower for k in ("chop", "fillet", "feather", "honeycomb")
    )
    if is_animal_source or is_animal_name or "animal product" in source_lower:
        for key, loc in animal_source_map.items():
            if key in source_lower or key in name_lower:
                return "animal_product", loc
        bare = to_snake_case(source_text.split("(")[0].strip()) if source_text else ""
        if bare in animal_source_map:
            return "animal_product", animal_source_map[bare]
        if bare in {
            "lamb",
            "sheep",
            "cow",
            "pig",
            "chicken",
            "goat",
            "duck",
            "lobster",
        }:
            return "animal_product", animal_source_map.get(bare, bare + "_pasture")
        if is_animal_name:
            return "animal_product", "animal"

    if "field" in source_lower or "crop" in source_lower:
        if "tree" in source_lower:
            return "crop", "tree"
        if "bush" in source_lower:
            return "crop", "bush"
        return "crop", "field"

    if "tree" in source_lower:
        return "crop", "tree"
    if "bush" in source_lower:
        return "crop", "bush"

    loc_id = to_snake_case(source_text.split("(")[0].strip()) if source_text else ""
    loc_id = re.sub(r"_x\d+$", "", loc_id)
    return "processed_material", loc_id or "unknown"


def parse_resources(client: WikiClient, max_level: int = 52) -> list[dict[str, Any]]:
    """
    Parse the Goods List table and return raw resource dicts.

    Every resource receives a provisional source_location_id; the normalizer
    may refine it from recipes.
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
        if len(cells) < 6:
            continue

        name_cell = cells[0]
        name_link = name_cell.find("a")
        name = name_link.get_text(strip=True) if name_link else _cell_text(name_cell)
        if not name or name.lower() in ("name", "goods"):
            continue

        level = _extract_first_int(_cell_text(cells[1]))
        if level is None or level > max_level:
            continue

        needs = _parse_needs(cells[5]) if len(cells) > 5 else []
        source_text = _cell_text(cells[6]) if len(cells) > 6 else ""

        res_type, source_loc = _classify_type_and_source(name, source_text, needs)
        res_id = to_snake_case(name)

        if res_id in seen:
            continue
        seen.add(res_id)

        results.append(
            {
                "id": res_id,
                "name": name,
                "type": res_type,
                "unlock_level": level,
                "source_location_id": source_loc,
                "_needs": needs,
                "_source_text": source_text,
            }
        )

    return results
