"""Convert raw scraped data into the final schema expected by the Layout Planner."""

from __future__ import annotations

import re
from typing import Any


def to_snake_case(name: str) -> str:
    """Convert a display name to snake_case English id."""
    cleaned = re.sub(r"[®™©]", "", name)
    cleaned = re.sub(r"\s*\(.*?\)\s*", " ", cleaned)
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


# Optional schema fields copied as-is from raw entries when present.
_LOCATION_OPTIONAL = ("area", "footprint_width", "footprint_height", "animal_capacity")
_RESOURCE_OPTIONAL = ("growth_time_seconds",)
_RECIPE_OPTIONAL = ("production_time_seconds", "production_time_3star_seconds")


def _copy_optional(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: raw[k] for k in keys if raw.get(k) is not None}


def build_level_limits(
    raw_locations: list[dict[str, Any]],
    field_grants: list[dict[str, Any]],
    known_location_ids: set[str],
) -> dict[str, Any]:
    """
    Build the level_limits.json payload.

    ``location_instances`` comes from the private ``_instance_levels`` list
    of each raw location (one row per copy); unknown locations are dropped.
    """
    instances: list[dict[str, Any]] = []
    done: set[str] = set()
    for raw in raw_locations:
        loc_id = raw.get("id")
        levels = raw.get("_instance_levels") or []
        if not loc_id or loc_id in done or loc_id not in known_location_ids:
            continue
        done.add(loc_id)
        for n, level in enumerate(sorted(levels), start=1):
            instances.append(
                {"location_id": loc_id, "instance": n, "unlock_level": int(level)}
            )
    instances.sort(key=lambda x: (x["unlock_level"], x["location_id"], x["instance"]))
    return {"field_grants": field_grants, "location_instances": instances}


def normalize(
    raw_locations: list[dict[str, Any]],
    raw_resources: list[dict[str, Any]],
    raw_recipes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    - Ensure snake_case ids
    - Deduplicate
    - Set source_location_id on every resource
    - Validate referential integrity (best-effort)
    - Sort by unlock_level then id
    """
    # --- Locations ---
    loc_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_locations:
        loc_id = raw.get("id") or to_snake_case(raw.get("name", ""))
        if not loc_id:
            continue
        entry = {
            "id": loc_id,
            "name": raw.get("name", loc_id.replace("_", " ").title()),
            "type": raw.get("type", "other"),
            "unlock_level": int(raw.get("unlock_level", 1)),
            **_copy_optional(raw, _LOCATION_OPTIONAL),
        }
        existing = loc_by_id.get(loc_id)
        if existing is None or entry["unlock_level"] < existing["unlock_level"]:
            loc_by_id[loc_id] = entry
    locations = sorted(loc_by_id.values(), key=lambda x: (x["unlock_level"], x["id"]))

    # --- Resources ---
    res_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_resources:
        res_id = raw.get("id") or to_snake_case(raw.get("name", ""))
        if not res_id:
            continue
        source = raw.get("source_location_id") or raw.get("source") or ""
        if isinstance(source, str):
            source = to_snake_case(source) if source else ""
        entry = {
            "id": res_id,
            "name": raw.get("name", res_id.replace("_", " ").title()),
            "type": raw.get("type", "processed_material"),
            "unlock_level": int(raw.get("unlock_level", 1)),
            "source_location_id": source,
            **_copy_optional(raw, _RESOURCE_OPTIONAL),
        }
        existing = res_by_id.get(res_id)
        if existing is None or entry["unlock_level"] < existing["unlock_level"]:
            res_by_id[res_id] = entry

    # --- Recipes ---
    recipe_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_recipes:
        recipe_id = raw.get("id") or to_snake_case(raw.get("name", ""))
        if not recipe_id:
            continue
        location_id = raw.get("location_id") or ""
        if location_id:
            location_id = to_snake_case(location_id)

        inputs = []
        for inp in raw.get("inputs") or []:
            rid = inp.get("resource_id") or to_snake_case(inp.get("name", ""))
            if not rid:
                continue
            inputs.append(
                {
                    "resource_id": rid,
                    "amount": int(inp.get("amount", 1)),
                }
            )

        output = raw.get("output") or {}
        out_id = output.get("resource_id") or to_snake_case(
            output.get("name", recipe_id)
        )
        out_amount = int(output.get("amount", 1))

        entry = {
            "id": recipe_id,
            "name": raw.get("name", recipe_id.replace("_", " ").title()),
            "location_id": location_id,
            "unlock_level": int(raw.get("unlock_level", 1)),
            "inputs": inputs,
            "output": {
                "resource_id": out_id,
                "amount": out_amount,
            },
            **_copy_optional(raw, _RECIPE_OPTIONAL),
        }
        existing = recipe_by_id.get(recipe_id)
        if existing is None or entry["unlock_level"] < existing["unlock_level"]:
            recipe_by_id[recipe_id] = entry

    for recipe in recipe_by_id.values():
        out_id = recipe["output"]["resource_id"]
        if out_id in res_by_id:
            res = res_by_id[out_id]
            if not res.get("source_location_id") and recipe.get("location_id"):
                res["source_location_id"] = recipe["location_id"]
            if res.get("type") in (None, "", "raw_material"):
                res["type"] = "processed_material"

    animal_source_aliases = {
        "lamb": "lamb_pasture",
        "sheep": "sheep_pasture",
        "cow": "cow_pasture",
        "pig": "pig_pen",
        "chicken": "chicken_coop",
        "goat": "goat_yard",
        "beehive": "beehive_tree",
        "bee": "beehive_tree",
    }
    animal_product_ids = {
        "egg",
        "milk",
        "bacon",
        "wool",
        "goat_milk",
        "honeycomb",
        "lamb_chop",
        "fish_fillet",
        "lobster_tail",
        "duck_feather",
        "peanuts",
    }
    for res in res_by_id.values():
        sid = res.get("source_location_id") or ""
        if sid in animal_source_aliases:
            res["source_location_id"] = animal_source_aliases[sid]
        if res["id"] in animal_product_ids or res.get("type") == "animal_product":
            res["type"] = "animal_product"
            sid = res.get("source_location_id") or ""
            if sid in animal_source_aliases:
                res["source_location_id"] = animal_source_aliases[sid]

    location_type_overrides = {
        "lobster_pool": "animal",
        "duck_salon": "animal",
        "beehive_tree": "animal",
        "squirrel_house": "animal",
        "mine": "other",
        "fishing_lake": "other",
        "field": "field",
        "tree": "tree",
        "bush": "bush",
    }
    for loc_id, loc_type in location_type_overrides.items():
        if loc_id in loc_by_id:
            loc_by_id[loc_id]["type"] = loc_type

    for bare, real in animal_source_aliases.items():
        if bare in loc_by_id and real in loc_by_id:
            del loc_by_id[bare]
        elif bare in loc_by_id and real not in loc_by_id:
            entry = loc_by_id.pop(bare)
            entry["id"] = real
            entry["name"] = real.replace("_", " ").title()
            entry["type"] = "animal"
            loc_by_id[real] = entry

    known_locs = set(loc_by_id.keys())
    type_from_id = {
        "field": "field",
        "tree": "tree",
        "bush": "bush",
        "mine": "other",
        "fishing_lake": "other",
    }
    for res in res_by_id.values():
        sid = res.get("source_location_id") or ""
        if not sid or sid in known_locs:
            continue
        loc_type = type_from_id.get(sid)
        if loc_type is None:
            if (
                res.get("type") == "animal_product"
                or sid in animal_source_aliases.values()
            ):
                loc_type = "animal"
            elif res.get("type") == "crop" and sid.endswith("_tree"):
                loc_type = "tree"
            elif res.get("type") == "crop" and sid.endswith("_bush"):
                loc_type = "bush"
            elif res.get("type") == "crop":
                loc_type = "field"
            elif res.get("type") == "ore":
                loc_type = "other"
            else:
                loc_type = "production"
        loc_by_id[sid] = {
            "id": sid,
            "name": sid.replace("_", " ").title(),
            "type": loc_type,
            "unlock_level": int(res.get("unlock_level", 1)),
            "area": "fishing_lake" if sid == "fishing_lake" else "farm",
        }
        known_locs.add(sid)

    locations = sorted(loc_by_id.values(), key=lambda x: (x["unlock_level"], x["id"]))
    resources = sorted(res_by_id.values(), key=lambda x: (x["unlock_level"], x["id"]))
    recipes = sorted(recipe_by_id.values(), key=lambda x: (x["unlock_level"], x["id"]))

    recipes = [
        r for r in recipes if not r["location_id"] or r["location_id"] in known_locs
    ]

    return locations, resources, recipes
