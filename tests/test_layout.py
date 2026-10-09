"""Tests for the Layout Planner (src/layout)."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import LocationProgress, PlayerConfig
from src.graph import build_graph
from src.layout import cli
from src.layout.blocks import block_flow_order, detect_named_blocks
from src.layout.describe import layout_to_dict, layout_to_markdown
from src.layout.farm_map import (
    EXAMPLE_MAP,
    Background,
    Expansion,
    FarmMap,
    FixedItem,
    Zone,
    cells_to_tiles,
    load_farm_map,
    outline_segments,
)
from src.layout.fields import SHARED_BLOCK_ID, allocate_fields, apportion
from src.layout.inventory import CountSource, farm_stock
from src.layout.packing import Box, Rect, bounding_rect, pack, patch
from src.layout.planner import _grow, plan_layout
from src.layout.render_svg import render_svg
from src.layout.support import active_relations
from src.loaders.json_loader import DataSet, load_data
from src.models import (
    FieldGrant,
    LevelLimits,
    Location,
    LocationInstance,
    LocationType,
    Recipe,
    RecipeInput,
    RecipeOutput,
    Resource,
    ResourceType,
)

DATA_DIR = Path("data")
HAS_REAL_DATA = (DATA_DIR / "locations.json").exists()

P, A, F, T, B, O = (
    LocationType.PRODUCTION,
    LocationType.ANIMAL,
    LocationType.FIELD,
    LocationType.TREE,
    LocationType.BUSH,
    LocationType.OTHER,
)


def _loc(id_, type_, w=None, h=None, **kw) -> Location:
    return Location(
        id=id_,
        name=id_.replace("_", " ").capitalize(),
        type=type_,
        unlock_level=1,
        footprint_width=w,
        footprint_height=h,
        **kw,
    )


def _res(id_, type_, source=None) -> Resource:
    return Resource(id=id_, name=id_, type=type_, unlock_level=1, source_location_id=source)


def _rec(id_, loc, inputs, out=None) -> Recipe:
    return Recipe(
        id=id_,
        name=id_,
        location_id=loc,
        unlock_level=1,
        inputs=[RecipeInput(resource_id=r, amount=a) for r, a in inputs],
        output=RecipeOutput(resource_id=out or id_, amount=1),
    )


@pytest.fixture
def farm() -> DataSet:
    """
    field → wheat → feed_mill → chicken_feed → chicken_coop → egg → bakery
    field → wheat → bakery; cow_pasture → milk → dairy; apple_tree → apple → bakery
    mine (fixed) → ore → smelter → bar → jeweler; beehive_tree → honeycomb → honey
    nectar_bush supports beehive_tree; ice_cream_maker uses cream from dairy.
    """
    locations = [
        _loc("field", F, 1, 1),
        _loc("feed_mill", P, 3, 3),
        _loc("chicken_coop", A, 3, 3),
        _loc("bakery", P, 3, 3),
        _loc("cow_pasture", A, 4, 4),
        _loc("dairy", P, 4, 4),
        _loc("ice_cream_maker", P, 3, 2, rotatable=True),
        _loc("apple_tree", T, 1, 1),
        _loc("raspberry_bush", B, 1, 2, rotatable=True),
        _loc("mine", O, movable=False),
        _loc("smelter", P, 2, 2),
        _loc("jeweler", P, 2, 2),
        _loc("beehive_tree", A, 2, 2),
        _loc("nectar_bush", B, 1, 1),
        _loc("honey_extractor", P, 2, 2),
        _loc("lure_workbench", P, area="fishing_lake", movable=False),
        # synthetic sizes, not game values
        _loc("barn", LocationType.STORAGE, 4, 4),
        _loc("silo", LocationType.STORAGE, 3, 3),
    ]
    resources = [
        _res("wheat", ResourceType.CROP, "field"),
        _res("chicken_feed", ResourceType.PROCESSED_MATERIAL, "feed_mill"),
        _res("egg", ResourceType.ANIMAL_PRODUCT, "chicken_coop"),
        _res("milk", ResourceType.ANIMAL_PRODUCT, "cow_pasture"),
        _res("apple", ResourceType.CROP, "apple_tree"),
        _res("raspberry", ResourceType.CROP, "raspberry_bush"),
        _res("ore", ResourceType.ORE, "mine"),
        _res("honeycomb", ResourceType.ANIMAL_PRODUCT, "beehive_tree"),
        _res("bread", ResourceType.PROCESSED_MATERIAL),
        _res("cake", ResourceType.PROCESSED_MATERIAL),
        _res("cream", ResourceType.PROCESSED_MATERIAL),
        _res("ice_cream", ResourceType.PROCESSED_MATERIAL),
        _res("bar", ResourceType.PROCESSED_MATERIAL),
        _res("ring", ResourceType.PROCESSED_MATERIAL),
        _res("honey", ResourceType.PROCESSED_MATERIAL),
        _res("lure", ResourceType.PROCESSED_MATERIAL),
    ]
    recipes = [
        _rec("chicken_feed", "feed_mill", [("wheat", 4)]),
        _rec("egg", "chicken_coop", [("chicken_feed", 1)]),
        _rec("bread", "bakery", [("wheat", 3), ("egg", 2)]),
        _rec("cake", "bakery", [("apple", 2), ("raspberry", 2)]),
        _rec("cream", "dairy", [("milk", 2)]),
        _rec("ice_cream", "ice_cream_maker", [("cream", 2), ("raspberry", 1)]),
        _rec("bar", "smelter", [("ore", 3)]),
        _rec("ring", "jeweler", [("bar", 2)]),
        _rec("honey", "honey_extractor", [("honeycomb", 1)]),
        _rec("lure", "lure_workbench", [("wheat", 1)]),
    ]
    limits = LevelLimits(
        field_grants=[FieldGrant(level=1, count=6), FieldGrant(level=5, count=3)],
        location_instances=[
            LocationInstance(location_id="chicken_coop", instance=1, unlock_level=1),
            LocationInstance(location_id="chicken_coop", instance=2, unlock_level=1),
            LocationInstance(location_id="chicken_coop", instance=3, unlock_level=5),
        ],
    )
    return DataSet(locations, resources, recipes, limits)


def _blocks_by_location(blocks) -> dict[str, str]:
    return {loc: b.id for b in blocks for loc in b.locations}


# ---------------------------------------------------------------------------
# Support relations and farm map
# ---------------------------------------------------------------------------


def test_support_relation_needs_both_ends() -> None:
    assert [r.source for r in active_relations({"nectar_bush", "beehive_tree"})] == [
        "nectar_bush"
    ]
    assert active_relations({"nectar_bush"}) == []


def test_farm_map_validation() -> None:
    with pytest.raises(ValidationError):
        FixedItem(id="barn", x=1, y=2)  # partial position
    with pytest.raises(ValidationError):
        FarmMap(width=10)  # width without height
    with pytest.raises(ValidationError):
        FarmMap(width=5, height=5, fixed=[FixedItem(id="barn", x=3, y=3, width=3, height=3)])
    with pytest.raises(ValidationError):
        FarmMap(fixed=[FixedItem(id="barn"), FixedItem(id="barn")])
    m = FarmMap(fixed=[FixedItem(id="barn"), FixedItem(id="mine", x=0, y=0, width=4, height=4)])
    assert not m.bounded
    assert [f.id for f in m.placed_fixed] == ["mine"]


def test_background_and_expansions(tmp_path: Path) -> None:
    payload = {
        "width": 40,
        "height": 30,
        "background": {
            "image": "bg.png",
            "image_width": 1300,
            "image_height": 900,
            "origin_px": [600, 100],
            "x_axis_px": [24, 12],
            "y_axis_px": [-24, 12],
        },
        "fixed": [],
        "expansions": [
            {"id": "base", "section": "base", "number": None, "unlocked": True, "cells": [[0, 0, 3, 2]]},
            {"id": "main_1", "section": "main", "number": 1, "unlocked": False, "cells": [[5, 5, 2, 2]]},
        ],
    }
    p = tmp_path / "farm_map.json"
    p.write_text(json.dumps(payload))
    fm = load_farm_map(p)
    assert fm.background_path() == (tmp_path / "bg.png").resolve()
    assert fm.usable_tiles() == {(x, y) for x in range(3) for y in range(2)}

    with pytest.raises(ValidationError):  # parallel axes
        Background(image="a.png", image_width=1, image_height=1, origin_px=(0, 0),
                   x_axis_px=(2, 1), y_axis_px=(4, 2))
    with pytest.raises(ValidationError):  # outside the map
        FarmMap(width=4, height=4, expansions=[Expansion(id="a", section="main", cells=[(3, 3, 2, 2)])])
    with pytest.raises(ValidationError):  # background needs a bounded map
        FarmMap(background=payload["background"])
    assert FarmMap().usable_tiles() is None


def test_example_farm_map_loads() -> None:
    m = load_farm_map(EXAMPLE_MAP)
    assert all(f.id == f.id.lower() for f in m.fixed)


def test_missing_explicit_farm_map(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_farm_map(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def test_stock_sources(farm: DataSet) -> None:
    player = PlayerConfig(
        level=5,
        fields_owned=7,
        locations={"chicken_coop": LocationProgress(owned=2)},
    )
    stock = {s.location.id: s for s in farm_stock(farm, player, level=5)}

    assert (stock["field"].count, stock["field"].reserved) == (7, 2)
    assert stock["chicken_coop"].source == CountSource.PROFILE
    assert (stock["chicken_coop"].count, stock["chicken_coop"].reserved) == (2, 1)
    assert stock["apple_tree"].source == CountSource.PLACEHOLDER
    assert stock["bakery"].source == CountSource.SINGLE
    # fixed and non-farm locations are never stocked
    assert "mine" not in stock and "lure_workbench" not in stock


def test_stock_without_profile_uses_level(farm: DataSet) -> None:
    stock = {s.location.id: s for s in farm_stock(farm, None, level=1)}
    assert stock["field"].count == 6
    assert stock["chicken_coop"].count == 2
    assert stock["chicken_coop"].source == CountSource.LEVEL


# ---------------------------------------------------------------------------
# Named blocks
# ---------------------------------------------------------------------------


def test_named_blocks(farm: DataSet) -> None:
    G = build_graph(farm)
    blocks = detect_named_blocks(G)
    owner = _blocks_by_location(blocks)

    # every movable farm location except the shared-out fields is in exactly one block
    movable_farm = {
        l.id
        for l in farm.location_list
        if l.area.value == "farm" and l.movable and l.type != LocationType.FIELD
    }
    assert set(owner) == movable_farm
    assert sum(len(b.locations) for b in blocks) == len(movable_farm)
    # suppliers follow their strongest consumer
    assert owner["cow_pasture"] == owner["dairy"]
    assert owner["chicken_coop"] == owner["bakery"]
    # a big crop user keeps its own block instead of merging as a lone building
    assert next(b for b in blocks if b.id == owner["feed_mill"]).locations == ["feed_mill"]
    # support relation: nectar bush sits with the beehive tree
    assert owner["nectar_bush"] == owner["beehive_tree"] == owner["honey_extractor"]
    # lone buildings merge into the coupled block; the earlier / stronger one names it
    assert owner["jeweler"] == owner["smelter"]
    assert owner["ice_cream_maker"] == owner["dairy"]
    names = {b.id: b.name for b in blocks}
    assert names[owner["dairy"]] == "Dairy block"
    # fixed buildings never join a block
    assert "mine" not in owner


def test_block_flow_order_starts_upstream(farm: DataSet) -> None:
    G = build_graph(farm)
    blocks = detect_named_blocks(G)
    owner = _blocks_by_location(blocks)
    order = block_flow_order(G, blocks)
    assert sorted(order) == sorted(b.id for b in blocks)
    assert order.index(owner["feed_mill"]) < order.index(owner["bakery"])


# ---------------------------------------------------------------------------
# Fields per block
# ---------------------------------------------------------------------------


def test_apportion() -> None:
    assert apportion(10, {"a": 3.0, "b": 1.0}, minimum=1) == {"a": 7, "b": 3}
    assert sum(apportion(84, {"a": 101, "b": 7, "c": 1}, minimum=1).values()) == 84
    # not enough for the minimum: the heaviest keys get one each
    assert apportion(2, {"a": 1, "b": 5, "c": 3}, minimum=1) == {"b": 1, "c": 1}
    assert apportion(0, {"a": 1}) == {}


def test_allocate_fields_by_crop_demand(farm: DataSet) -> None:
    G = build_graph(farm)
    blocks = detect_named_blocks(G)
    owner = _blocks_by_location(blocks)
    shares = {s.block_id: s for s in allocate_fields(G, blocks, 14, 2)}

    # wheat: feed mill 4, bakery 3 (the fishing-lake lure workbench is no block)
    assert set(shares) == {owner["feed_mill"], owner["bakery"]}
    assert shares[owner["feed_mill"]].count == 8 and shares[owner["bakery"]].count == 6
    assert sum(s.reserved for s in shares.values()) == 2
    assert shares[owner["bakery"]].crops == ["wheat"]

    pooled = {s.block_id: s for s in allocate_fields(G, blocks, 14, pool_ratio=0.25)}
    assert pooled[SHARED_BLOCK_ID].count == 4
    assert sum(s.count for s in pooled.values()) == 14


# ---------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------


def _no_overlap(rects: list[Rect], gap: int = 0) -> bool:
    return not any(a.overlaps(b, gap) for a, b in combinations(rects, 2))


def test_patch_is_near_square() -> None:
    box = patch("field", 1, 1, 10, False)
    assert (box.w, box.h) == (4, 3)
    assert len(box.units) == 10
    bush = patch("bush", 1, 2, 4, True)
    assert bush.w * bush.h >= 8 and _no_overlap(bush.units)


def test_pack_respects_gap_and_obstacles() -> None:
    boxes = [Box(f"b{i}", 3, 2) for i in range(6)]
    obstacles = {"rock": Rect(0, 0, 2, 2)}
    placed, unplaced = pack(boxes, {("b0", "b1"): 5.0}, gap=1, obstacles=obstacles)
    assert not unplaced
    rects = [p.rect for p in placed.values()]
    assert _no_overlap(rects + [obstacles["rock"]], gap=1)


def test_pack_rotates_only_rotatable_boxes() -> None:
    placed, unplaced = pack([Box("r", 5, 2, rotatable=True)], {}, bounds=(2, 5))
    assert not unplaced and placed["r"].rotated
    assert (placed["r"].rect.w, placed["r"].rect.h) == (2, 5)

    placed, unplaced = pack([Box("s", 5, 2, rotatable=False)], {}, bounds=(2, 5))
    assert unplaced == ["s"] and not placed


def test_pack_pulls_coupled_boxes_together() -> None:
    boxes = [Box(k, 2, 2) for k in ("a", "b", "c", "d")]
    placed, _ = pack(boxes, {("a", "d"): 10.0, ("b", "c"): 0.1}, gap=0)
    a, d = placed["a"].rect, placed["d"].rect
    dist = abs(a.center[0] - d.center[0]) + abs(a.center[1] - d.center[1])
    assert dist == 2  # side by side


# ---------------------------------------------------------------------------
# Planner, SVG, description
# ---------------------------------------------------------------------------


def _check_layout(layout) -> None:
    items = [i for b in layout.blocks for i in b.items]
    assert _no_overlap([i.rect for i in items])
    frames = [b.frame for b in layout.blocks if b.frame is not None]
    fixed = [Rect(f.x, f.y, f.width, f.height) for f in layout.farm_map.placed_fixed]
    assert _no_overlap(frames + fixed)
    for b in layout.blocks:
        if b.frame is None:
            continue
        for i in b.items:
            assert bounding_rect([b.frame, i.rect]) == b.frame, (b.block.id, i)


def test_plan_layout_unbounded(farm: DataSet) -> None:
    player = PlayerConfig(level=5, locations={"chicken_coop": LocationProgress(owned=2)})
    layout = plan_layout(farm, level=5, player=player)
    _check_layout(layout)

    ext = layout.extent()
    assert (ext.x, ext.y) == (0, 0)
    assert "mine" in layout.fixed_unplaced
    coop_items = [i for b in layout.blocks for i in b.items if i.location_id == "chicken_coop"]
    assert sum(i.reserved for i in coop_items) == 1 and len(coop_items) == 3
    # fields: 9 at level 5, split into dedicated patches, none left in one big block
    field_items = [i for b in layout.blocks for i in b.items if i.location_id == "field"]
    assert len(field_items) == 9
    assert len({i.block_id for i in field_items}) == 2
    assert all(b.fields is None or b.fields.crops == ["wheat"] for b in layout.blocks)
    # non-rotatable non-square items keep the stored orientation
    for b in layout.blocks:
        for i in b.items:
            loc = farm.locations[i.location_id]
            if not loc.rotatable:
                assert (i.rect.w, i.rect.h) == (loc.footprint_width, loc.footprint_height)


def test_plan_layout_bounded_with_fixed(farm: DataSet) -> None:
    farm_map = FarmMap(
        width=40,
        height=40,
        fixed=[
            FixedItem(id="mine", x=36, y=0, width=4, height=4),
            FixedItem(id="farmhouse", x=17, y=17, width=6, height=6),
            FixedItem(id="event_board"),
        ],
    )
    layout = plan_layout(farm, level=5, farm_map=farm_map, reserve_ratio=0.5)
    _check_layout(layout)
    assert not layout.unplaced_blocks
    for b in layout.blocks:
        f = b.frame
        assert f.x >= 0 and f.y >= 0 and f.x + f.w <= 40 and f.y + f.h <= 40
    assert layout.fixed_unplaced == ["event_board"]
    smelter = next(b for b in layout.blocks if "smelter" in b.block.locations)
    assert any(n.b == "mine" and n.a == smelter.block.id for n in layout.neighbourhoods)


def test_plan_layout_only_on_unlocked_plots(farm: DataSet) -> None:
    unlocked = Expansion(id="base", section="base", unlocked=True, cells=[(0, 0, 30, 30)])
    locked = Expansion(id="main_1", section="main", number=1, cells=[(30, 0, 30, 60), (0, 30, 30, 30)])
    farm_map = FarmMap(width=60, height=60, expansions=[unlocked, locked])
    layout = plan_layout(farm, level=5, farm_map=farm_map)
    _check_layout(layout)
    assert not layout.unplaced_blocks
    usable = farm_map.usable_tiles()
    for b in layout.blocks:
        f = b.frame
        assert all((f.x + i, f.y + j) in usable for i in range(f.w) for j in range(f.h))


def test_unlocked_plot_without_cells_is_ignored() -> None:
    empty = Expansion(id="main_2", section="main", number=2, unlocked=True)
    assert FarmMap(width=10, height=10, expansions=[empty]).usable_tiles() is None
    drawn = Expansion(id="base", section="base", unlocked=True, cells=[(0, 0, 2, 1)])
    assert FarmMap(width=10, height=10, expansions=[empty, drawn]).usable_tiles() == {(0, 0), (1, 0)}



def test_outline_merges_touching_rectangles() -> None:
    # two touching rectangles of one plot form a 3x1 bar: 4 border segments, no inner edge
    tiles = cells_to_tiles([(0, 0, 2, 1), (2, 0, 1, 1)])
    assert sorted(outline_segments(tiles)) == sorted(
        [((0, 0), (3, 0)), ((0, 1), (3, 1)), ((0, 0), (0, 1)), ((3, 0), (3, 1))]
    )
    # an L shape has 6 border segments
    assert len(outline_segments(cells_to_tiles([(0, 0, 2, 1), (0, 1, 1, 1)]))) == 6

def test_zones_limit_usable_tiles() -> None:
    plot = Expansion(id="base", section="base", unlocked=True, cells=[(0, 0, 4, 4)])
    buildable = Zone(id="main_section", kind="buildable", cells=[(0, 0, 3, 3)])
    pond = Zone(id="pond", kind="blocked", cells=[(0, 0, 1, 1)])
    # plots, then buildable zones, then blocked zones
    fm = FarmMap(width=10, height=10, expansions=[plot], zones=[buildable, pond])
    assert fm.usable_tiles() == {(x, y) for x in range(3) for y in range(3)} - {(0, 0)}
    # without plots: the buildable zones are the start
    assert len(FarmMap(width=10, height=10, zones=[buildable, pond]).usable_tiles()) == 8
    # only blocked zones: the whole bounded map minus the blocked tiles
    assert len(FarmMap(width=2, height=2, zones=[pond]).usable_tiles()) == 3
    with pytest.raises(ValidationError):
        FarmMap(width=2, height=2, zones=[Zone(id="road", kind="blocked", cells=[(1, 1, 2, 1)])])
    with pytest.raises(ValidationError):
        Zone(id="road", kind="water", cells=[])


def test_unplaced_block_has_no_items(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, farm_map=FarmMap(width=2, height=2))
    assert layout.unplaced_blocks
    for b in layout.blocks:
        if b.frame is None:
            assert b.items == []
    data = layout_to_dict(layout)
    assert all(not b["items"] for b in data["blocks"] if b["frame"] is None)


def test_svg_background_matrix_maps_tiles(farm: DataSet, tmp_path: Path) -> None:
    from src.layout.render_svg import _image_matrix

    bg = Background(image="bg.png", image_width=1300, image_height=900,
                    origin_px=(600, 100), x_axis_px=(24, 12), y_axis_px=(-24, 12))
    farm_map = FarmMap(width=40, height=30, background=bg)
    farm_map._base_dir = tmp_path
    layout = plan_layout(farm, level=5, farm_map=farm_map)
    (tmp_path / "out").mkdir()
    svg = render_svg(layout, tmp_path / "out" / "layout.svg")
    assert 'href="../bg.png"' in svg

    # pixel of tile corner (x, y) must land where the grid draws that corner
    def pt(x, y):
        return (100 + (x - y) * 14, 40 + (x + y) * 7)

    a, b, c, d, e, f = _image_matrix(bg, pt)
    for x, y in ((0, 0), (7, 3), (40, 30)):
        px = (600 + 24 * x - 24 * y, 100 + 12 * x + 12 * y)
        assert (a * px[0] + c * px[1] + e, b * px[0] + d * px[1] + f) == pytest.approx(pt(x, y))


def test_plan_layout_shared_field_pool(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, field_pool=0.5)
    _check_layout(layout)
    shared = next(b for b in layout.blocks if b.block.id == SHARED_BLOCK_ID)
    assert shared.fields.count == 4 and shared.block.name == "Shared fields block"
    assert sum(i.location_id == "field" for b in layout.blocks for i in b.items) == 9



def test_plan_layout_avoids_blocked_zones(farm: DataSet, tmp_path: Path) -> None:
    road = Zone(id="road", kind="blocked", cells=[(0, 10, 60, 2)])
    layout = plan_layout(farm, level=5, farm_map=FarmMap(width=60, height=60, zones=[road]))
    for pb in layout.blocks:
        for it in pb.items:
            r = it.rect
            assert all((r.x + i, r.y + j) not in road.tiles() for i in range(r.w) for j in range(r.h))
    svg = render_svg(layout, tmp_path / "layout.svg")
    assert "road (blocked)" in svg


def test_barn_and_silo_form_a_storage_block(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5)
    storage = next(b for b in layout.blocks if b.block.id == "storage_block")
    assert storage.block.name == "Storage block"
    assert sorted(i.location_id for i in storage.items) == ["barn", "silo"]
    assert "barn" not in layout.fixed_unplaced


def test_barn_placed_on_the_map_stays_fixed(farm: DataSet) -> None:
    barn = FixedItem(id="barn", x=0, y=0, width=4, height=4)
    silo = FixedItem(id="silo")  # listed without a position: the planner places it
    layout = plan_layout(farm, level=5, farm_map=FarmMap(width=60, height=60, fixed=[barn, silo]))
    storage = next(b for b in layout.blocks if b.block.id == "storage_block")
    assert [i.location_id for i in storage.items] == ["silo"]
    assert layout.fixed_unplaced == ["mine"]



def test_pinned_copy_of_a_multi_copy_building_keeps_the_others(farm: DataSet) -> None:
    player = PlayerConfig(level=5, locations={"dairy": LocationProgress(owned=2)})
    dairy = FixedItem(id="dairy", x=0, y=0, width=4, height=4)
    fm = FarmMap(width=60, height=60, fixed=[dairy])
    layout = plan_layout(farm, level=5, player=player, farm_map=fm)
    planned = [i for b in layout.blocks for i in b.items if i.location_id == "dairy"]
    assert len(planned) == 1  # the second copy is still placed in its block


def test_plan_layout_rejects_negative_reserve(farm: DataSet) -> None:
    with pytest.raises(ValueError, match="negative"):
        plan_layout(farm, level=5, reserve_ratio=-0.1)

def test_base_plot_counts_as_unlocked() -> None:
    base = Expansion(id="base", section="base", cells=[(0, 0, 2, 1)])
    locked = Expansion(id="main_1", section="main", number=1, cells=[(5, 5, 1, 1)])
    assert FarmMap(width=10, height=10, expansions=[base, locked]).usable_tiles() == {(0, 0), (1, 0)}


def test_reserve_shrinks_until_blocks_fit(farm: DataSet) -> None:
    # find a map size where the full reserve does not fit but a smaller one does
    for size in range(60, 4, -1):
        layout = plan_layout(farm, level=5, farm_map=FarmMap(width=size, height=size), reserve_ratio=1.0)
        if 0 < layout.reserve_ratio < 1.0 and not layout.unplaced_blocks:
            break
    else:
        pytest.fail("no map size forced a smaller reserve")
    assert layout.reserve_requested == 1.0
    assert "lowered from 100%" in layout_to_markdown(layout)


def test_grow_adds_the_reserve_to_the_cheaper_side() -> None:
    # a 5 % reserve must not turn a 2-wide block into a 3-wide one
    assert _grow(2, 6, 0.05) == (2, 7)
    assert _grow(4, 4, 0.0) == (4, 4)
    w, h = _grow(10, 8, 0.2)
    assert w >= 10 and h >= 8 and w * h >= 96


def test_pack_size_order_places_the_largest_box_first() -> None:
    boxes = [Box("small", 1, 1), Box("big", 3, 3)]
    weights = {("big", "small"): 0.0}
    area = {(x, y) for x in range(10) for y in range(10)}
    placed, _ = pack(boxes, weights, bounds=(10, 10), area=area, order="size")
    assert list(placed) == ["big", "small"]

def test_plan_layout_reports_blocks_that_do_not_fit(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, farm_map=FarmMap(width=6, height=6))
    assert layout.unplaced_blocks
    assert "Did not fit" in layout_to_markdown(layout)


def test_outputs(farm: DataSet, tmp_path: Path) -> None:
    layout = plan_layout(farm, level=5)
    svg = render_svg(layout, tmp_path / "layout.svg")
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    ext = layout.extent()
    # grid lines on both axes (+ 1-tile border on each side when unbounded)
    assert svg.count("<line ") == (ext.w + 3) + (ext.h + 3)
    assert (tmp_path / "layout.svg").exists()

    payload = json.loads(json.dumps(layout_to_dict(layout)))
    assert {b["id"] for b in payload["blocks"]} == {b.block.id for b in layout.blocks}
    assert payload["support_relations"][0]["source"] == "nectar_bush"

    md = layout_to_markdown(layout)
    for heading in ("## Blocks", "## Relative order", "## Recommended neighbourhoods"):
        assert heading in md


# ---------------------------------------------------------------------------
# Real data and CLI
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_layout() -> None:
    full = load_data(DATA_DIR)
    level = max(l.unlock_level for l in full.location_list)
    layout = plan_layout(full.filter_by_max_level(level), level=level)
    _check_layout(layout)
    owner = _blocks_by_location(b.block for b in layout.blocks)
    assert owner["nectar_bush"] == owner["beehive_tree"]
    assert owner["cow_pasture"] == owner["dairy"]
    assert not layout.missing_footprint
    # fields are shared out: several blocks own fields, and all of them are placed
    field_blocks = [b for b in layout.blocks if b.fields is not None]
    assert len(field_blocks) > 1
    stock = next(s for s in layout.stock if s.location.id == "field")
    placed = sum(i.location_id == "field" for b in layout.blocks for i in b.items)
    assert placed == stock.count + stock.reserved


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_writes_outputs(tmp_path: Path) -> None:
    assert cli.main(["--level", "20", "--output-dir", str(tmp_path)]) == 0
    for name in ("layout.json", "layout.md", "layout.svg"):
        assert (tmp_path / name).exists()
    assert json.loads((tmp_path / "layout.json").read_text())["level"] == 20



@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_strategy_all_writes_one_set_per_strategy(tmp_path: Path) -> None:
    args = ["--level", "20", "--strategy", "all", "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    for stem, used in (("layout_coupling", "coupling"), ("layout_size", "size")):
        assert json.loads((tmp_path / f"{stem}.json").read_text())["strategy"] == used
        assert (tmp_path / f"{stem}.svg").exists()
    assert (tmp_path / "layout.svg").exists()


def test_plan_layout_rejects_unknown_strategy(farm: DataSet) -> None:
    with pytest.raises(ValueError, match="strategy"):
        plan_layout(farm, level=5, strategy="random")

@pytest.mark.parametrize("level", ["0", "-3"])
def test_cli_rejects_invalid_level(tmp_path: Path, level: str) -> None:
    assert cli.main(["--level", level, "--output-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "layout.json").exists()
