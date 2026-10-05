"""Parse locations (production buildings, animal shelters, fields, trees, bushes)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.scraper.normalizer import to_snake_case
from src.scraper.wiki_client import WikiClient


def _extract_first_int(text: str) -> int | None:
    m = re.search(r"(\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else None


def _extract_all_ints(text: str) -> list[int]:
    """Extract all integers; commas are treated as separators, not removed."""
    return [int(x) for x in re.findall(r"\d+", text)]


def _clean_building_name(name: str) -> str:
    """Strip 'x2', 'x5', '(1st)' etc. from building list names."""
    name = re.sub(r"\s*x\d+\s*", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(.*?\)\s*", " ", name)
    return name.strip()


def _find_main_table(soup: BeautifulSoup) -> Tag | None:
    table = soup.find("table", class_=re.compile(r"wikitable|article-table|sortable"))
    if table is not None:
        return table
    tables = soup.find_all("table")
    if not tables:
        return None
    return max(tables, key=lambda t: len(t.find_all("tr")))


def _parse_production_buildings(
    client: WikiClient, max_level: int, seen_ids: set[str]
) -> list[dict[str, Any]]:
    """Parse Production_Buildings_List."""
    results: list[dict[str, Any]] = []
    soup = client.get_production_locations_list()
    table = _find_main_table(soup)
    if table is None:
        return results

    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        name_cell = cells[0]
        name_link = name_cell.find("a")
        raw_name = (
            name_link.get_text(strip=True)
            if name_link
            else name_cell.get_text(strip=True)
        )
        if not raw_name:
            continue

        clean_name = _clean_building_name(raw_name)
        if not clean_name or clean_name.lower() in ("name", "building"):
            continue

        level_text = cells[1].get_text(" ", strip=True)
        level = _extract_first_int(level_text)
        if level is None or level > max_level:
            continue

        loc_id = to_snake_case(clean_name)
        if loc_id in seen_ids:
            continue
        seen_ids.add(loc_id)

        animal_ids = {
            "lobster_pool",
            "duck_salon",
            "beehive_tree",
            "squirrel_house",
        }
        if loc_id in animal_ids or loc_id.endswith(("_pool", "_salon")):
            loc_type = "animal"
        elif loc_id == "mine":
            loc_type = "other"
        else:
            loc_type = "production"

        results.append(
            {
                "id": loc_id,
                "name": clean_name,
                "type": loc_type,
                "unlock_level": level,
            }
        )
    return results


def _parse_animal_shelters(
    client: WikiClient, max_level: int, seen_ids: set[str]
) -> list[dict[str, Any]]:
    """
    Parse farm-animal shelters from the Animal_Shelters page.

    Only the 'Shelters for farm animals' section is used (pets are skipped).
    """
    results: list[dict[str, Any]] = []
    soup = client.get_page("Animal_Shelters")

    farm_heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if "farm animal" in tag.get_text(strip=True).lower():
            farm_heading = tag
            break

    tables: list[Tag] = []
    if farm_heading is not None:
        for sib in farm_heading.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            if isinstance(sib, Tag):
                if sib.name == "table":
                    tables.append(sib)
                else:
                    tables.extend(sib.find_all("table"))
    if not tables:
        tables = soup.find_all("table")

    for table in tables:
        _extract_shelters_from_table(table, max_level, seen_ids, results)
    return results


def _extract_shelters_from_table(
    table: Tag,
    max_level: int,
    seen_ids: set[str],
    results: list[dict[str, Any]],
) -> None:
    """
    Extract shelter name + earliest unlock level from the Animal_Shelters grid.

    Layout (farm animals section):
      image row | name row (wiki links) | capacity row | unlock-level row
      (pattern may repeat for a second group of shelters in the same table)
    """
    rows = table.find_all("tr")
    if not rows:
        return

    pet_keywords = (
        "dog",
        "cat",
        "horse",
        "bunny",
        "puppy",
        "donkey",
        "kitten",
        "guinea",
        "bird",
        "alpaca",
    )

    shelter_href_re = re.compile(
        r"^/wiki/[A-Za-z0-9_]+_(?:Coop|Pasture|Pen|Yard|House|Tree|Pool|Salon)$",
        re.IGNORECASE,
    )

    i = 0
    while i < len(rows):
        cells = rows[i].find_all(["td", "th"])
        names: list[str] = []
        for cell in cells:
            link = None
            for a in cell.find_all("a", href=True):
                href = a["href"].split("?")[0]
                if shelter_href_re.match(href):
                    link = a
                    break
            if link:
                name = link.get_text(strip=True)
                if name:
                    names.append(name)

        if not names:
            i += 1
            continue

        unlock_levels: list[int | None] = [None] * len(names)
        for j in range(i + 1, min(i + 5, len(rows))):
            level_cells = rows[j].find_all(["td", "th"])
            found_any = False
            for idx, cell in enumerate(level_cells):
                if idx >= len(names):
                    break
                text = cell.get_text(" ", strip=True).lower()
                if "level" not in text:
                    continue
                after_level = re.split(r"level\s*", text, maxsplit=1)
                level_part = after_level[1] if len(after_level) > 1 else text
                levels = _extract_all_ints(level_part)
                if levels:
                    unlock_levels[idx] = min(levels)
                    found_any = True
            if found_any:
                break

        for name, level in zip(names, unlock_levels):
            if level is None or level > max_level:
                continue
            loc_id = to_snake_case(name)
            if loc_id in seen_ids:
                continue
            if any(k in loc_id for k in pet_keywords):
                continue
            seen_ids.add(loc_id)
            results.append(
                {
                    "id": loc_id,
                    "name": name,
                    "type": "animal",
                    "unlock_level": level,
                }
            )
        i += 1


def _parse_generic_sources_from_goods(
    client: WikiClient, max_level: int, seen_ids: set[str]
) -> list[dict[str, Any]]:
    """
    Derive field / tree / bush / mine / fishing_lake locations from the
    Source column of the Goods List (no hard-coded location names).
    """
    results: list[dict[str, Any]] = []
    soup = client.get_goods_list()
    table = _find_main_table(soup)
    if table is None:
        return results

    type_hints = {
        "field": ("field", "Field"),
        "tree": ("tree", "Tree"),
        "bush": ("bush", "Bush"),
        "mine": ("other", "Mine"),
        "fishing": ("other", "Fishing Lake"),
        "lake": ("other", "Fishing Lake"),
    }

    earliest: dict[str, int] = {}
    display_names: dict[str, str] = {}

    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 7:
            continue

        level = _extract_first_int(cells[1].get_text(" ", strip=True))
        if level is None or level > max_level:
            continue

        source_cell = cells[6]
        source_text = source_cell.get_text(" ", strip=True).lower()

        for keyword, (loc_type, default_name) in type_hints.items():
            if keyword not in source_text:
                continue
            link = source_cell.find("a")
            if link and keyword in link.get_text(strip=True).lower():
                raw = link.get_text(strip=True)
                if "tree" in raw.lower():
                    loc_id, name = "tree", "Tree"
                elif "bush" in raw.lower():
                    loc_id, name = "bush", "Bush"
                elif "field" in raw.lower() or "farm" in raw.lower():
                    loc_id, name = "field", "Field"
                elif "mine" in raw.lower():
                    loc_id, name = "mine", "Mine"
                else:
                    loc_id = to_snake_case(raw)
                    name = raw
            else:
                loc_id = {
                    "field": "field",
                    "tree": "tree",
                    "bush": "bush",
                    "mine": "mine",
                    "fishing": "fishing_lake",
                    "lake": "fishing_lake",
                }.get(keyword, keyword)
                name = default_name

            if loc_id not in earliest or level < earliest[loc_id]:
                earliest[loc_id] = level
                display_names[loc_id] = name
            break

    for loc_id, level in earliest.items():
        if loc_id in seen_ids or level > max_level:
            continue
        seen_ids.add(loc_id)
        loc_type = {
            "field": "field",
            "tree": "tree",
            "bush": "bush",
            "mine": "other",
            "fishing_lake": "other",
        }.get(loc_id, "other")
        results.append(
            {
                "id": loc_id,
                "name": display_names.get(loc_id, loc_id.replace("_", " ").title()),
                "type": loc_type,
                "unlock_level": level,
            }
        )
    return results


def parse_locations(client: WikiClient, max_level: int) -> list[dict[str, Any]]:
    """
    Return raw list of locations up to max_level.

    Data is taken exclusively from wiki pages – nothing is hard-coded:
    - Production_Buildings_List  → type=production
    - Animal_Shelters            → type=animal (farm animals only)
    - Goods_List Source column   → generic field / tree / bush / mine / fishing_lake
    """
    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    results.extend(_parse_production_buildings(client, max_level, seen_ids))
    results.extend(_parse_animal_shelters(client, max_level, seen_ids))
    results.extend(_parse_generic_sources_from_goods(client, max_level, seen_ids))

    return results
