"""
Scraper tests on saved wiki HTML (tests/fixtures/wiki), no network.

The fixtures are trimmed copies of the real Fandom page structure: rowspan
rows for multi-copy buildings, '★★★' mastery times, shelter unlock rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from bs4 import BeautifulSoup

from src.scraper.durations import parse_duration_seconds, parse_timed_cell
from src.scraper.normalizer import build_level_limits, normalize
from src.scraper.parsers.level_limits import parse_field_grants
from src.scraper.parsers.locations import parse_locations
from src.scraper.parsers.recipes import parse_recipes
from src.scraper.parsers.resources import parse_resources

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"


class FakeWikiClient:
    """Serves fixture files instead of calling the MediaWiki API."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def get_page(self, page_name: str) -> BeautifulSoup:
        self.requested.append(page_name)
        path = FIXTURES / f"{page_name.replace('/', '_')}.html"
        return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")

    def get_goods_list(self) -> BeautifulSoup:
        return self.get_page("Goods_List")

    def get_production_locations_list(self) -> BeautifulSoup:
        return self.get_page("Production_Buildings_List")

    CATEGORIES: ClassVar[dict[str, list[str]]] = {
        "Fishing_Lake_Buildings": ["Lobster Pool", "Lure Workbench", "Tackle Box"],
        "Trees_and_Bushes": [
            "Apple Tree",
            "Cherry Tree",
            "Nectar Bush",
            "Peanut Bush",
            "Raspberry Bush",
            "Trees and Bushes",
        ],
    }
    WIKITEXT: ClassVar[dict[str, str]] = {
        "Nectar_Bush": "{{Infobox\n |level = 39|price = 120|title = Trees & bushes}}",
        "Peanut_Bush": "{{Infobox\n |level = 62|price = 300}}",
    }

    def get_category_members(self, category: str) -> list[str]:
        return self.CATEGORIES[category]

    def get_wikitext(self, page_name: str) -> str:
        self.requested.append(page_name)
        return self.WIKITEXT[page_name]

    def list_pages(self, prefix: str) -> list[str]:
        return [
            "Experience Levels/Levels 1-25",
            "Experience Levels/Levels 26-50",
            "Experience Levels/Levels 51-75",
        ]


@pytest.fixture
def client() -> FakeWikiClient:
    return FakeWikiClient()


# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("40 sec", 40),
        ("2 min", 120),
        ("2 h 30 min", 9000),
        ("1 d 3 h", 97200),
        ("4d", 345600),
        ("4h ", 14400),
        ("Instant", 0),
        ("Instant or 20 h", 0),
        ("N/A", None),
    ],
)
def test_parse_duration_seconds(text: str, expected: int | None) -> None:
    assert parse_duration_seconds(text) == expected


def test_parse_timed_cell_splits_mastery_time() -> None:
    assert parse_timed_cell("30 min ★★★ 25 min") == (1800, 1500)
    assert parse_timed_cell("2 h") == (7200, None)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def _by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items}


def test_production_building_instances(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))

    assert locs["feed_mill"]["_instance_levels"] == [2, 12]
    assert locs["smelter"]["_instance_levels"] == [24] * 5
    # second sugar mill unlocks at 76 > max level
    assert locs["sugar_mill"]["_instance_levels"] == [7]
    assert locs["bakery"]["_instance_levels"] == [4]


def test_production_building_footprints(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))

    assert (
        locs["feed_mill"]["footprint_width"],
        locs["feed_mill"]["footprint_height"],
    ) == (3, 3)
    assert (locs["dairy"]["footprint_width"], locs["dairy"]["footprint_height"]) == (
        4,
        4,
    )
    assert (
        locs["ice_cream_maker"]["footprint_width"],
        locs["ice_cream_maker"]["footprint_height"],
    ) == (3, 2)
    assert "footprint_width" not in locs["mine"]  # "N/A"


def test_max_level_cuts_buildings(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=30))
    assert "sushi_bar" not in locs
    assert "lobster_pool" not in locs
    assert "ice_cream_maker" in locs


def test_animal_shelters(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))

    coop = locs["chicken_coop"]
    assert coop["type"] == "animal"
    assert coop["unlock_level"] == 1
    assert coop["animal_capacity"] == 6
    assert coop["_instance_levels"] == [1, 12, 23]

    assert locs["lamb_pasture"]["animal_capacity"] == 5
    assert locs["beehive_tree"]["_instance_levels"] == [39]
    assert "animal_capacity" not in locs["beehive_tree"]  # "1-4 beehives"
    assert "squirrel_house" not in locs  # level 62
    assert "dog_house" not in locs  # pets are skipped


def test_trees_and_bushes_per_kind(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))
    res = _by_id(parse_resources(client, max_level=56))

    assert locs["apple_tree"]["type"] == "tree"
    assert locs["apple_tree"]["unlock_level"] == 15
    assert locs["cherry_tree"]["type"] == "tree"
    assert locs["raspberry_bush"]["type"] == "bush"
    assert "tree" not in locs and "bush" not in locs
    # Beehive tree is an animal shelter, not a fruit tree
    assert locs["beehive_tree"]["type"] == "animal"

    assert res["apple"]["source_location_id"] == "apple_tree"
    assert res["raspberry"]["source_location_id"] == "raspberry_bush"
    assert res["honeycomb"]["source_location_id"] == "beehive_tree"


def test_trees_and_bushes_without_goods(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))

    assert locs["nectar_bush"]["type"] == "bush"
    assert locs["nectar_bush"]["unlock_level"] == 39
    assert "peanut_bush" not in locs  # level 62
    # fruit trees already known from the Goods List are not fetched again
    assert "Apple_Tree" not in client.requested


def test_area_from_category(client: FakeWikiClient) -> None:
    locs = _by_id(parse_locations(client, max_level=56))

    assert locs["lobster_pool"]["area"] == "fishing_lake"
    assert locs["lure_workbench"]["area"] == "fishing_lake"
    assert locs["dairy"]["area"] == "farm"
    assert locs["chicken_coop"]["area"] == "farm"


# ---------------------------------------------------------------------------
# Resources and recipes
# ---------------------------------------------------------------------------


def test_resource_growth_times(client: FakeWikiClient) -> None:
    res = _by_id(parse_resources(client, max_level=56))

    assert res["wheat"]["growth_time_seconds"] == 120
    assert res["egg"]["growth_time_seconds"] == 1200
    assert res["cherry"]["growth_time_seconds"] == 97200
    assert res["silver_ore"]["growth_time_seconds"] == 0
    # processed goods carry their time on the recipe, not the resource
    assert "growth_time_seconds" not in res["bread"]


def test_recipe_production_times(client: FakeWikiClient) -> None:
    rec = _by_id(parse_recipes(client, max_level=56))

    assert rec["bread"]["production_time_seconds"] == 300
    assert rec["bread"]["production_time_3star_seconds"] == 255
    assert rec["cream"]["production_time_seconds"] == 7200
    assert rec["cream"]["production_time_3star_seconds"] == 6120
    assert "wheat" not in rec


def test_animal_feeding_recipes(client: FakeWikiClient) -> None:
    rec = _by_id(parse_recipes(client, max_level=56))

    assert rec["egg"]["location_id"] == "chicken_coop"
    assert rec["egg"]["inputs"] == [{"resource_id": "chicken_feed", "amount": 1}]
    assert rec["egg"]["production_time_seconds"] == 1200
    assert rec["milk"]["location_id"] == "cow_pasture"
    assert rec["milk"]["inputs"] == [{"resource_id": "cow_feed", "amount": 1}]
    # honeycomb has no needs (nectar is not a good), so it stays a pure resource
    assert "honeycomb" not in rec


def test_caught_animal_needs_become_traps() -> None:
    raw_recipe = {
        "id": "lobster_tail",
        "name": "Lobster tail",
        "location_id": "lobster_pool",
        "unlock_level": 44,
        "inputs": [{"resource_id": "lobster", "amount": 1}],
        "output": {"resource_id": "lobster_tail", "amount": 1},
    }
    raw_resources = [
        {
            "id": "lobster_trap",
            "name": "Lobster trap",
            "type": "processed_material",
            "unlock_level": 44,
            "source_location_id": "net_maker",
        },
        {
            "id": "lobster_tail",
            "name": "Lobster tail",
            "type": "animal_product",
            "unlock_level": 44,
            "source_location_id": "lobster_pool",
        },
    ]
    raw_locations = [
        {
            "id": "net_maker",
            "name": "Net maker",
            "type": "production",
            "unlock_level": 30,
        },
        {
            "id": "lobster_pool",
            "name": "Lobster pool",
            "type": "animal",
            "unlock_level": 44,
        },
    ]
    _, _, recipes = normalize(raw_locations, raw_resources, [raw_recipe])
    assert recipes[0]["inputs"] == [{"resource_id": "lobster_trap", "amount": 1}]


# ---------------------------------------------------------------------------
# Level limits
# ---------------------------------------------------------------------------


def test_field_grants(client: FakeWikiClient) -> None:
    grants = parse_field_grants(client, max_level=29)

    assert grants == [
        {"level": 1, "count": 6},
        {"level": 3, "count": 3},
        {"level": 5, "count": 3},
        {"level": 27, "count": 3},
        {"level": 29, "count": 3},
    ]
    # pages starting above the player level are not fetched
    assert "Experience_Levels/Levels_51-75" not in client.requested


def test_full_pipeline_builds_valid_level_limits(client: FakeWikiClient) -> None:
    from src.models import LevelLimits

    raw_locs = parse_locations(client, max_level=50)
    locations, _, _ = normalize(
        raw_locs, parse_resources(client, 50), parse_recipes(client, 50)
    )
    payload = build_level_limits(
        raw_locs, parse_field_grants(client, 50), {loc["id"] for loc in locations}
    )
    limits = LevelLimits.model_validate(payload)

    assert limits.instances_at("feed_mill", 11) == 1
    assert limits.instances_at("feed_mill", 12) == 2
    assert limits.instances_at("smelter", 24) == 5
    assert limits.instances_at("chicken_coop", 50) == 3
    assert limits.fields_at(5) == 12
    # private helper keys never reach the normalised output
    assert all(not k.startswith("_") for loc in locations for k in loc)
