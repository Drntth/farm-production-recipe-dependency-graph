"""Tests for the Layout Planner (src/layout)."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import LocationProgress, PlayerConfig
from src.graph import build_graph
from src.layout import cli, visuals
from src.layout import planner as planner_module
from src.layout.blocks import Block, block_flow_order, detect_named_blocks
from src.layout.describe import layout_to_dict, layout_to_markdown
from src.layout.design import plan_design
from src.layout.farm_map import (
    EXAMPLE_MAP,
    Background,
    CurrentItem,
    Expansion,
    FarmMap,
    FixedItem,
    Zone,
    cells_to_tiles,
    load_farm_map,
    outline_segments,
)
from src.layout.fields import (
    SHARED_BLOCK_ID,
    allocate_fields,
    allocate_fields_by_use,
    apportion,
)
from src.layout.inventory import CountSource, farm_stock
from src.layout.packing import Box, Rect, bounding_rect, pack, patch
from src.layout.planner import PlacedBlock, _grow, plan_layout
from src.layout.render_svg import render_svg
from src.layout.sizing import Sizing
from src.layout.support import active_relations
from src.layout.templates import BlockTemplate, DesignTemplate
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
    return Resource(
        id=id_, name=id_, type=type_, unlock_level=1, source_location_id=source
    )


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
    # squirrels fetch peanut pods like bees fetch nectar
    assert [r.target for r in active_relations({"peanut_bush", "squirrel_house"})] == [
        "squirrel_house"
    ]


def test_farm_map_validation() -> None:
    with pytest.raises(ValidationError):
        FixedItem(id="barn", x=1, y=2)  # partial position
    with pytest.raises(ValidationError):
        FarmMap(width=10)  # width without height
    with pytest.raises(ValidationError):
        FarmMap(
            width=5, height=5, fixed=[FixedItem(id="barn", x=3, y=3, width=3, height=3)]
        )
    with pytest.raises(ValidationError):
        FarmMap(fixed=[FixedItem(id="barn"), FixedItem(id="barn")])
    m = FarmMap(
        fixed=[FixedItem(id="barn"), FixedItem(id="mine", x=0, y=0, width=4, height=4)]
    )
    assert not m.bounded
    assert [f.id for f in m.placed_fixed] == ["mine"]
    # older editor files carry "area": farm is dropped, other areas are rejected
    assert FarmMap.model_validate({"area": "farm", "width": 4, "height": 4}).bounded
    with pytest.raises(ValidationError, match="Only farm maps"):
        FarmMap.model_validate({"area": "town"})


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
            {
                "id": "base",
                "section": "base",
                "number": None,
                "unlocked": True,
                "cells": [[0, 0, 3, 2]],
            },
            {
                "id": "main_1",
                "section": "main",
                "number": 1,
                "unlocked": False,
                "cells": [[5, 5, 2, 2]],
            },
        ],
    }
    p = tmp_path / "farm_map.json"
    p.write_text(json.dumps(payload))
    fm = load_farm_map(p)
    assert fm.background_path() == (tmp_path / "bg.png").resolve()
    assert fm.usable_tiles() == {(x, y) for x in range(3) for y in range(2)}

    with pytest.raises(ValidationError):  # parallel axes
        Background(
            image="a.png",
            image_width=1,
            image_height=1,
            origin_px=(0, 0),
            x_axis_px=(2, 1),
            y_axis_px=(4, 2),
        )
    with pytest.raises(ValidationError):  # outside the map
        FarmMap(
            width=4,
            height=4,
            expansions=[Expansion(id="a", section="main", cells=[(3, 3, 2, 2)])],
        )
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
    assert next(b for b in blocks if b.id == owner["feed_mill"]).locations == [
        "feed_mill"
    ]
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
    player = PlayerConfig(
        level=5, locations={"chicken_coop": LocationProgress(owned=2)}
    )
    layout = plan_layout(farm, level=5, player=player)
    _check_layout(layout)

    ext = layout.extent()
    assert (ext.x, ext.y) == (0, 0)
    assert "mine" in layout.fixed_unplaced
    coop_items = [
        i for b in layout.blocks for i in b.items if i.location_id == "chicken_coop"
    ]
    assert sum(i.reserved for i in coop_items) == 1 and len(coop_items) == 3
    # fields: 9 at level 5, split into dedicated patches, none left in one big block
    field_items = [
        i for b in layout.blocks for i in b.items if i.location_id == "field"
    ]
    assert len(field_items) == 9
    assert len({i.block_id for i in field_items}) == 2
    assert all(b.fields is None or b.fields.crops == ["wheat"] for b in layout.blocks)
    # non-rotatable non-square items keep the stored orientation
    for b in layout.blocks:
        for i in b.items:
            loc = farm.locations[i.location_id]
            if not loc.rotatable:
                assert (i.rect.w, i.rect.h) == (
                    loc.footprint_width,
                    loc.footprint_height,
                )


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
    unlocked = Expansion(
        id="base", section="base", unlocked=True, cells=[(0, 0, 30, 30)]
    )
    locked = Expansion(
        id="main_1", section="main", number=1, cells=[(30, 0, 30, 60), (0, 30, 30, 30)]
    )
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
    assert FarmMap(width=10, height=10, expansions=[empty, drawn]).usable_tiles() == {
        (0, 0),
        (1, 0),
    }


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
    assert (
        len(FarmMap(width=10, height=10, zones=[buildable, pond]).usable_tiles()) == 8
    )
    # only blocked zones: the whole bounded map minus the blocked tiles
    assert len(FarmMap(width=2, height=2, zones=[pond]).usable_tiles()) == 3
    with pytest.raises(ValidationError):
        FarmMap(
            width=2,
            height=2,
            zones=[Zone(id="road", kind="blocked", cells=[(1, 1, 2, 1)])],
        )
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

    bg = Background(
        image="bg.png",
        image_width=1300,
        image_height=900,
        origin_px=(600, 100),
        x_axis_px=(24, 12),
        y_axis_px=(-24, 12),
    )
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
        assert (a * px[0] + c * px[1] + e, b * px[0] + d * px[1] + f) == pytest.approx(
            pt(x, y)
        )


def test_plan_layout_shared_field_pool(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, field_pool=0.5)
    _check_layout(layout)
    shared = next(b for b in layout.blocks if b.block.id == SHARED_BLOCK_ID)
    assert shared.fields.count == 4 and shared.block.name == "Shared fields block"
    assert sum(i.location_id == "field" for b in layout.blocks for i in b.items) == 9


def test_plan_layout_avoids_blocked_zones(farm: DataSet, tmp_path: Path) -> None:
    road = Zone(id="road", kind="blocked", cells=[(0, 10, 60, 2)])
    layout = plan_layout(
        farm, level=5, farm_map=FarmMap(width=60, height=60, zones=[road])
    )
    for pb in layout.blocks:
        for it in pb.items:
            r = it.rect
            assert all(
                (r.x + i, r.y + j) not in road.tiles()
                for i in range(r.w)
                for j in range(r.h)
            )
    svg = render_svg(layout, tmp_path / "layout.svg")
    assert "road (blocked)" in svg


def test_barn_and_silo_form_a_storage_block(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5)
    storage = next(b for b in layout.blocks if b.block.id == "storage_block")
    assert storage.block.name == "Storage block"
    assert sorted(i.location_id for i in storage.items) == ["barn", "silo"]
    assert "barn" not in layout.fixed_unplaced


def test_plan_layout_rejects_negative_reserve(farm: DataSet) -> None:
    with pytest.raises(ValueError, match="negative"):
        plan_layout(farm, level=5, reserve_ratio=-0.1)


def test_base_plot_counts_as_unlocked() -> None:
    base = Expansion(id="base", section="base", cells=[(0, 0, 2, 1)])
    locked = Expansion(id="main_1", section="main", number=1, cells=[(5, 5, 1, 1)])
    assert FarmMap(width=10, height=10, expansions=[base, locked]).usable_tiles() == {
        (0, 0),
        (1, 0),
    }


def test_reserve_shrinks_until_blocks_fit(farm: DataSet) -> None:
    # find a map size where the full reserve does not fit but a smaller one does
    for size in range(60, 4, -1):
        layout = plan_layout(
            farm, level=5, farm_map=FarmMap(width=size, height=size), reserve_ratio=1.0
        )
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
def test_cli_removes_stale_layout_files(tmp_path: Path) -> None:
    names = (
        "layout_town.svg",
        "layout_size.json",
        "layout_notes.txt",
        "layout_notes.md",
    )
    for name in names:
        (tmp_path / name).write_text("old", encoding="utf-8")
    # a failed run keeps the earlier outputs
    config = _design_config(
        tmp_path, design_layer=True, path_targets="buildings", item_gap=0
    )
    args = ["--level", "20", "--output-dir", str(tmp_path)]
    assert cli.main([*args, "--design-config", config]) == 1
    assert all((tmp_path / name).exists() for name in names)

    assert cli.main(args) == 0
    assert not (tmp_path / "layout_town.svg").exists()
    assert not (tmp_path / "layout_size.json").exists()
    assert (tmp_path / "layout_notes.txt").exists()  # not a layout file set
    assert (tmp_path / "layout_notes.md").exists()  # not a known layout stem
    assert (tmp_path / "layout.json").exists()


def _design_config(tmp_path: Path, **keys) -> str:
    """A design.json in *tmp_path* with the given keys."""
    path = tmp_path / "design.json"
    path.write_text(json.dumps(keys), encoding="utf-8")
    return str(path)


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_strategy_all_writes_one_set_per_strategy(tmp_path: Path) -> None:
    config = _design_config(tmp_path, strategy="all")
    args = ["--level", "20", "--design-config", config, "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    for stem, used in (("layout_coupling", "coupling"), ("layout_size", "size")):
        assert json.loads((tmp_path / f"{stem}.json").read_text())["strategy"] == used
        assert (tmp_path / f"{stem}.svg").exists()
    assert (tmp_path / "layout.svg").exists()


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_strategy_flow(tmp_path: Path) -> None:
    config = _design_config(tmp_path, strategy="flow", reserve=0.1)
    args = ["--level", "20", "--design-config", config, "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    data = json.loads((tmp_path / "layout.json").read_text())
    assert data["strategy"] in ("flow", "size")
    assert data["sized_by_production"] is False
    # the settings actually used are written next to the layout
    assert data["settings"]["strategy"] == "flow"
    assert data["settings"]["reserve"] == 0.1


def test_plan_layout_rejects_unknown_strategy(farm: DataSet) -> None:
    with pytest.raises(ValueError, match="strategy"):
        plan_layout(farm, level=5, strategy="random")


@pytest.mark.parametrize("level", ["0", "-3"])
def test_cli_rejects_invalid_level(tmp_path: Path, level: str) -> None:
    assert cli.main(["--level", level, "--output-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "layout.json").exists()


# ---------------------------------------------------------------------------
# Design layer: paths and decoration band
# ---------------------------------------------------------------------------


def _grid(w: int, h: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(w) for y in range(h)}


def _touches(tiles: set[tuple[int, int]], r: Rect) -> bool:
    return any(
        (x + dx, y + dy) in tiles
        for x in range(r.x, r.x + r.w)
        for y in range(r.y, r.y + r.h)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    )


def _connected(tiles: set[tuple[int, int]]) -> bool:
    if not tiles:
        return True
    start = min(tiles)
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n in tiles and n not in seen:
                seen.add(n)
                todo.append(n)
    return seen == tiles


def test_design_connects_blocks_and_key_buildings() -> None:
    blocks = {"a_block": Rect(1, 1, 3, 3), "b_block": Rect(8, 6, 3, 2)}
    fixed = {"farmhouse": Rect(5, 1, 2, 2), "mine": Rect(0, 8, 2, 2)}
    design = plan_design(_grid(12, 10), blocks, fixed, decor_band=1)

    assert design.connected[0] == "farmhouse"  # the hub
    assert set(design.connected) == {"farmhouse", "a_block", "b_block"}
    assert "mine" not in design.connected  # an obstacle, not a key building
    assert _connected(design.paths)
    for r in [*blocks.values(), *fixed.values()]:
        assert not any(
            r.x <= x < r.x + r.w and r.y <= y < r.y + r.h for x, y in design.paths
        )
    for key in ("farmhouse", "a_block", "b_block"):
        assert _touches(design.paths, {**blocks, **fixed}[key])
    # the band: next to a path, never on it or on a building
    assert design.decorations and not design.decorations & design.paths
    assert all(_touches(design.paths, Rect(x, y, 1, 1)) for x, y in design.decorations)


def test_design_reports_walled_in_blocks() -> None:
    # the right half is cut off by a wall of fixed tiles
    allowed = _grid(10, 5)
    fixed = {f"wall_{y}": Rect(5, y, 1, 1) for y in range(5)}
    blocks = {"left_block": Rect(1, 1, 2, 2), "right_block": Rect(7, 1, 2, 2)}
    design = plan_design(allowed, blocks, fixed, decor_band=0)

    assert design.connected == ["left_block"]  # no farmhouse: first block is the hub
    assert design.unreachable == ["right_block"]
    assert design.approached == {}  # only key buildings get a connection point
    assert design.decorations == set()
    with pytest.raises(ValueError):
        plan_design(allowed, blocks, fixed, decor_band=-1)


def test_design_reaches_cut_off_key_building_at_connection_point() -> None:
    # riverboat beyond a paved, non-buildable strip (x = 6..7 not allowed)
    allowed = _grid(6, 6) | {(8, y) for y in range(6)}
    blocks = {"a_block": Rect(1, 1, 2, 2)}
    fixed = {"farmhouse": Rect(1, 4, 2, 1), "riverboat": Rect(9, 2, 2, 2)}
    design = plan_design(allowed, blocks, fixed, decor_band=0)

    # the main path reaches the key building before the side path the block
    assert design.connected == ["farmhouse", "riverboat", "a_block"]
    assert not design.unreachable
    assert design.approached == {"riverboat": 3}  # x = 6, 7, 8 between
    assert any(x == 5 for x, _ in design.paths)  # the nearest reachable column
    assert design.paths <= allowed and _connected(design.paths)

    # too far behind non-buildable ground: no connection point, unreachable
    far = {**fixed, "riverboat": Rect(15, 2, 2, 2)}
    design = plan_design(allowed, blocks, far, decor_band=0)
    assert design.unreachable == ["riverboat"] and design.approached == {}


def test_plan_layout_with_design(farm: DataSet) -> None:
    farm_map = FarmMap(
        width=40,
        height=40,
        fixed=[FixedItem(id="farmhouse", x=17, y=17, width=6, height=6)],
    )
    layout = plan_layout(farm, level=5, farm_map=farm_map, gap=0, design=True)
    _check_layout(layout)
    frames = [b.frame for b in layout.blocks if b.frame is not None]
    assert _no_overlap(frames, gap=1)  # design forces room for paths
    d = layout.design
    assert d is not None and not d.unreachable
    assert d.connected[0] == "farmhouse"
    assert plan_layout(farm, level=5, farm_map=farm_map).design is None

    data = layout_to_dict(layout)["design"]
    assert len(data["paths"]) == len(d.paths)
    assert "## Design" in layout_to_markdown(layout)
    assert "<title>path</title>" in render_svg(layout)


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_design(tmp_path: Path) -> None:
    config = _design_config(tmp_path, design_layer=True)
    args = ["--level", "20", "--design-config", config, "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    assert json.loads((tmp_path / "layout.json").read_text())["design"] is not None
    bad = _design_config(tmp_path, decor_band=-1)
    assert cli.main(["--level", "20", "--design-config", bad]) == 1
    missing = str(tmp_path / "missing.json")
    assert cli.main(["--level", "20", "--design-config", missing]) == 1


def test_movable_location_in_fixed_is_an_error(farm: DataSet) -> None:
    barn = FixedItem(id="barn", x=0, y=0, width=4, height=4)
    silo = FixedItem(id="silo")  # also without a position
    mine = FixedItem(id="mine", x=10, y=10, width=3, height=3)
    fm = FarmMap(width=60, height=60, fixed=[barn, silo, mine])
    with pytest.raises(ValueError, match="movable items as fixed: barn, silo"):
        plan_layout(farm, level=5, farm_map=fm)


def test_old_movable_flag_is_a_clear_error() -> None:
    old = {"fixed": [{"id": "barn", "x": 0, "y": 0, "width": 4, "height": 4,
                      "movable": True}]}  # fmt: skip
    with pytest.raises(ValidationError, match="save it again"):
        FarmMap.model_validate(old)


def test_current_items_are_ignored_by_the_layout(farm: DataSet) -> None:
    fm = FarmMap(
        width=60,
        height=60,
        current=[
            CurrentItem(id="barn", x=0, y=0, width=4, height=4),
            CurrentItem(id="field", count=12),
        ],
    )
    assert fm.placed_fixed == []
    layout = plan_layout(farm, level=5, farm_map=fm)
    plain = plan_layout(farm, level=5, farm_map=FarmMap(width=60, height=60))
    assert layout_to_dict(layout)["blocks"] == layout_to_dict(plain)["blocks"]


def test_current_item_validation() -> None:
    with pytest.raises(ValidationError, match="one copy"):
        CurrentItem(id="dairy", x=0, y=0, width=4, height=4, count=2)
    with pytest.raises(ValidationError, match="x, y, width and height"):
        CurrentItem(id="dairy", x=0, y=0)
    with pytest.raises(ValidationError, match="outside"):
        FarmMap(
            width=5,
            height=5,
            current=[CurrentItem(id="dairy", x=3, y=3, width=4, height=4)],
        )
    with pytest.raises(ValidationError, match="cannot be current items: mine"):
        FarmMap(fixed=[FixedItem(id="mine")], current=[CurrentItem(id="mine")])
    with pytest.raises(ValidationError, match="twice"):
        FarmMap(current=[CurrentItem(id="field", count=3), CurrentItem(id="field")])
    # several placed copies of one id are fine
    FarmMap(current=[CurrentItem(id="dairy", x=0, y=0, width=4, height=4),
                     CurrentItem(id="dairy", x=4, y=0, width=4, height=4)])  # fmt: skip


def test_allocate_fields_by_use_splits_every_crop_by_its_users() -> None:
    blocks = [Block("a_block", "A", "a", ["a"]), Block("b_block", "B", "b", ["b"])]
    shares = allocate_fields_by_use(
        blocks,
        {"wheat": 4, "corn": 2, "sold_crop": 1},
        {"wheat": {"a": 3.0, "b": 1.0}, "corn": {"b": 2.0}, "sold_crop": {}},
        count=10,
        reserved=2,
    )
    by_id = {s.block_id: s for s in shares}
    assert by_id["a_block"].count == 3 and by_id["a_block"].crops == ["wheat"]
    assert by_id["b_block"].count == 3 and by_id["b_block"].crops == ["corn", "wheat"]
    # the sold crop's field plus the 3 owned fields the plan leaves empty
    assert by_id[SHARED_BLOCK_ID].count == 4
    assert by_id[SHARED_BLOCK_ID].crops == ["sold_crop"]
    assert sum(s.count for s in shares) == 10
    assert sum(s.reserved for s in shares) == 2
    # the plan never gets more fields than owned
    capped = allocate_fields_by_use(blocks, {"wheat": 9}, {"wheat": {"a": 1.0}}, 5)
    assert [(s.block_id, s.count) for s in capped] == [("a_block", 5)]
    # nothing planned: owned and reserved fields both end up shared
    idle = allocate_fields_by_use(blocks, {"wheat": 0}, {}, count=4, reserved=3)
    assert [(s.block_id, s.count, s.reserved) for s in idle] == [
        (SHARED_BLOCK_ID, 4, 3)
    ]
    # a crop below half a field is not listed, but a block lists at least one
    small = allocate_fields_by_use(
        blocks,
        {"wheat": 3, "corn": 1},
        {"wheat": {"a": 1.0}, "corn": {"a": 1.0, "b": 9.0}},
        count=4,
    )
    by_id = {s.block_id: s for s in small}
    assert by_id["a_block"].crops == ["wheat"]  # 0.1 corn field dropped
    assert by_id["b_block"].crops == ["corn"]


def test_pack_flow_order_follows_the_sequence() -> None:
    boxes = [Box("a", 2, 2), Box("b", 3, 3), Box("c", 1, 1)]
    weights = {("a", "b"): 5.0}
    placements, unplaced = pack(boxes, weights, order="flow", sequence=["c", "a", "b"])
    assert not unplaced
    assert list(placements) == ["c", "a", "b"]
    # keys missing from the sequence come last, by coupling
    placements, _ = pack(boxes, weights, order="flow", sequence=["c"])
    assert next(iter(placements)) == "c"


def test_plan_layout_with_sizing(farm: DataSet) -> None:
    sizing = Sizing(
        counts={"apple_tree": 4},
        crop_fields={"wheat": 5},
        crop_use={"wheat": {"feed_mill": 4.0, "bakery": 1.0}},
        flows={("feed_mill", "chicken_coop"): 2.0, ("dairy", "ice_cream_maker"): 1.0},
        extra_reserved={"chicken_coop": 1, "field": 2},
    )
    layout = plan_layout(farm, level=5, sizing=sizing, strategy="flow")
    _check_layout(layout)
    assert layout.sized
    stock = {s.location.id: s for s in layout.stock}
    assert stock["apple_tree"].count == 4
    assert stock["apple_tree"].source == CountSource.PRODUCTION
    assert stock["chicken_coop"].reserved == 1  # 3 at level 5, one more kept free
    fields = {pb.block.id: pb.fields for pb in layout.blocks if pb.fields}
    total = sum(f.count for f in fields.values())
    assert total == stock["field"].count  # every owned field has a block
    assert sum(f.reserved for f in fields.values()) == 2
    owner = {loc: pb.block.id for pb in layout.blocks for loc in pb.block.locations}
    assert fields[owner["feed_mill"]].count >= 3  # 4 of the 5 planned wheat fields
    assert layout.strategy in ("flow", "size")
    assert "production plan" in layout_to_markdown(layout)
    assert layout_to_dict(layout)["sized_by_production"] is True
    # a count of 0 drops the location from the layout
    none = plan_layout(farm, level=5, sizing=Sizing(counts={"apple_tree": 0}))
    assert "apple_tree" not in {s.location.id for s in none.stock}


# ---------------------------------------------------------------------------
# v1.0 design options: figures, path style and targets, item gap, design zones
# ---------------------------------------------------------------------------


def test_design_figures() -> None:
    # an L-shaped connection: one corner, no detour
    design = plan_design(
        _grid(6, 6), {"a_block": Rect(0, 0, 1, 1)}, {"farmhouse": Rect(4, 4, 1, 1)}
    )
    assert design.corners >= 1
    assert design.detour_ratio == pytest.approx(1.0)
    assert design.walked == design.direct
    assert plan_design(_grid(3, 3), {}, {}).detour_ratio == 1.0
    with pytest.raises(ValueError, match="path_style"):
        plan_design(_grid(3, 3), {}, {}, path_style="curvy")


def test_straight_paths_have_fewer_corners() -> None:
    # scattered blocks: breadth-first paths zigzag, a turn cost straightens them
    corners = {"b1": (14, 2), "b2": (8, 13), "b3": (5, 1), "b4": (1, 3)}
    blocks = {f"{k}_block": Rect(x, y, 2, 2) for k, (x, y) in corners.items()}
    fixed = {"farmhouse": Rect(13, 10, 2, 2)}
    args = (_grid(18, 18), blocks, fixed)
    shortest = plan_design(*args, decor_band=0)
    straight = plan_design(*args, decor_band=0, path_style="straight")
    assert set(straight.connected) == set(shortest.connected)
    assert not straight.unreachable
    assert straight.corners < shortest.corners
    assert _connected(straight.paths)


def test_design_terminal_of_several_rects_and_walk_only_tiles() -> None:
    patch_rects = [Rect(5, 1, 1, 1), Rect(6, 1, 1, 1)]
    walk_only = {(x, 3) for x in range(10)}  # a design zone across the map
    design = plan_design(
        _grid(10, 6),
        {"fields": patch_rects},
        {"farmhouse": Rect(1, 4, 1, 1)},
        decor_band=1,
        obstacles=[Rect(8, 4, 1, 1)],
        walk_only=walk_only,
    )
    assert design.connected == ["farmhouse", "fields"]
    assert not design.decorations & walk_only  # paths may cross, no band there
    assert (8, 4) not in design.paths | design.decorations  # reserved space


# ---------------------------------------------------------------------------
# v1.4 path network: main and side paths, main path width, stepped style
# ---------------------------------------------------------------------------


def test_main_path_reaches_key_buildings_first() -> None:
    # the block is nearer to the hub, but the truck is on the main path
    blocks = {"a_block": Rect(3, 0, 2, 2), "storage_block": Rect(14, 6, 2, 2)}
    fixed = {"farmhouse": Rect(0, 6, 2, 2), "truck": Rect(8, 10, 2, 1)}
    design = plan_design(_grid(18, 12), blocks, fixed, decor_band=0)

    assert design.connected[:3] == ["farmhouse", "truck", "storage_block"]
    assert design.connected[3] == "a_block"
    assert design.main_paths and design.side_paths
    assert design.main_paths | design.side_paths == design.paths
    assert not design.main_paths & design.side_paths
    assert _connected(design.paths)
    assert _touches(design.main_paths, blocks["storage_block"])
    assert _touches(design.main_paths, fixed["truck"])
    assert not _touches(design.main_paths, blocks["a_block"])  # a side path


def test_main_path_of_two_tiles_narrows_between_blocks() -> None:
    fixed = {"farmhouse": Rect(0, 4, 2, 2), "truck": Rect(16, 4, 2, 2)}
    open_design = plan_design(_grid(18, 10), {}, fixed, main_path_width=2)
    assert open_design.main_path_width == 2 and open_design.narrowed == 0
    assert len(open_design.main_paths) > len(open_design.lanes) > 0
    assert open_design.corners == plan_design(_grid(18, 10), {}, fixed).corners
    assert _connected(open_design.paths)

    # two walls leave a 1-tile corridor between the hub and the truck
    walls = {"w1": Rect(5, 0, 6, 5), "w2": Rect(5, 6, 6, 4)}
    narrow = plan_design(_grid(18, 10), walls, fixed, main_path_width=2)
    assert narrow.narrowed >= 5  # the corridor tiles
    assert {(x, 5) for x in range(5, 11)} <= narrow.paths
    with pytest.raises(ValueError, match="main_path_width"):
        plan_design(_grid(3, 3), {}, {}, main_path_width=3)


def test_second_lane_of_a_stepped_main_path_stays_joined() -> None:
    # stepped main path past scattered posts: no lane piece only touches a corner
    posts = {f"p{i}": Rect(3 + 2 * i, 2 + 2 * i, 1, 1) for i in range(5)}
    fixed = {"farmhouse": Rect(0, 0, 2, 1), "truck": Rect(14, 12, 1, 1), **posts}
    design = plan_design(
        _grid(16, 14), {}, fixed, main_path_style="stepped", main_path_width=2
    )
    assert design.lanes
    assert _connected(design.main_paths) and _connected(design.paths)


def test_unreachable_key_building_does_not_stop_the_side_paths() -> None:
    # the truck is far beyond non-buildable ground: no connection point
    fixed = {"farmhouse": Rect(0, 0, 2, 2), "truck": Rect(20, 2, 2, 2)}
    blocks = {"a_block": Rect(2, 7, 2, 2)}
    design = plan_design(_grid(10, 10), blocks, fixed, decor_band=0)
    assert design.unreachable == ["truck"]
    assert design.connected == ["farmhouse", "a_block"]
    assert not design.main_paths and design.side_paths
    assert design.approached == {}


def test_stepped_paths_follow_the_straight_line() -> None:
    # one connection from (2, 1) to (13, 12): a staircase, no long legs
    fixed = {"farmhouse": Rect(0, 0, 2, 1), "truck": Rect(14, 12, 1, 1)}
    args = (_grid(16, 14), {}, fixed)
    shortest = plan_design(*args, decor_band=0)
    stepped = plan_design(*args, decor_band=0, path_style="stepped")
    assert len(stepped.paths) == len(shortest.paths)  # still a shortest path
    assert stepped.detour_ratio == pytest.approx(1.0)
    assert stepped.corners > shortest.corners
    assert _connected(stepped.paths)
    rows = {}
    for x, y in stepped.paths:
        rows[y] = rows.get(y, 0) + 1
    assert max(rows.values()) <= 3  # never more than a short leg per row


def test_mixed_main_and_side_path_styles() -> None:
    blocks = {"a_block": Rect(12, 10, 2, 2)}
    fixed = {"farmhouse": Rect(0, 0, 2, 2), "truck": Rect(12, 0, 2, 1)}
    design = plan_design(
        _grid(16, 14),
        blocks,
        fixed,
        path_style="stepped",
        main_path_style="straight",
    )
    assert (design.main_path_style, design.path_style) == ("straight", "stepped")
    assert design.connected == ["farmhouse", "truck", "a_block"]
    # the straight main path is one leg along the top edge
    assert len({y for _, y in design.main_paths}) == 1
    defaults = plan_design(_grid(4, 4), {}, {}, path_style="stepped")
    assert defaults.main_path_style == "stepped"
    with pytest.raises(ValueError, match="path_style"):
        plan_design(_grid(3, 3), {}, {}, main_path_style="curvy")


def test_plan_layout_with_path_network(farm: DataSet) -> None:
    farm_map = FarmMap(
        width=40,
        height=40,
        fixed=[
            FixedItem(id="farmhouse", x=17, y=17, width=6, height=6),
            FixedItem(id="truck", x=2, y=30, width=4, height=3),
        ],
    )
    layout = plan_layout(
        farm,
        level=5,
        farm_map=farm_map,
        design=True,
        main_path_width=2,
        main_path_style="straight",
        path_style="stepped",
    )
    d = layout.design
    assert d is not None and not d.unreachable
    assert d.main_path_width == 2 and d.main_paths
    figures = layout_to_dict(layout)["design"]["figures"]
    assert figures["main_path_tiles"] == len(d.main_paths)
    assert figures["side_path_tiles"] == len(d.side_paths)
    assert figures["narrowed_tiles"] == d.narrowed
    assert (figures["main_path_style"], figures["path_style"]) == (
        "straight",
        "stepped",
    )
    assert "Main path (straight, 2 tile(s) wide)" in layout_to_markdown(layout)
    assert "<title>main path</title>" in render_svg(layout)


def test_item_gap_spaces_the_buildings_of_a_block(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, item_gap=1)
    assert layout.item_gap == 1
    for pb in layout.blocks:
        buildings = [i.rect for i in pb.items if not i.in_patch]
        for a, b in combinations(buildings, 2):
            assert not a.overlaps(b, gap=1), (pb.block.id, a, b)
        # a patch stays one piece: its units touch each other
        patches = [i.rect for i in pb.items if i.in_patch]
        if len(patches) > 1:
            assert bounding_rect(patches).w * bounding_rect(patches).h <= 2 * len(
                patches
            )
    with pytest.raises(ValueError):
        plan_layout(farm, level=5, item_gap=-1)


def test_paths_to_every_building(farm: DataSet) -> None:
    farm_map = FarmMap(
        width=50,
        height=50,
        fixed=[FixedItem(id="farmhouse", x=22, y=22, width=4, height=4)],
    )
    layout = plan_layout(
        farm,
        level=5,
        farm_map=farm_map,
        design=True,
        item_gap=1,
        path_targets="buildings",
    )
    d = layout.design
    assert d is not None and not d.unreachable
    for pb in layout.blocks:
        for item in pb.items:
            if not item.reserved and not item.in_patch:
                assert _touches(d.paths, item.rect), item
    assert "buildings and patches" in layout_to_markdown(layout)
    assert layout_to_dict(layout)["design"]["figures"]["path_targets"] == "buildings"
    # paths may enter the block frames, the band stays out of the reserve there
    for pb in layout.blocks:
        if pb.frame is not None:
            f = pb.frame
            assert not any(
                f.x <= x < f.x + f.w and f.y <= y < f.y + f.h for x, y in d.decorations
            ), pb.block.id
    with pytest.raises(ValueError, match="item_gap"):
        plan_layout(farm, level=5, design=True, path_targets="buildings")
    with pytest.raises(ValueError, match="path_targets"):
        plan_layout(farm, level=5, path_targets="trees")


def test_design_zones_keep_blocks_out(farm: DataSet) -> None:
    garden = Zone(id="garden", kind="design", cells=[(0, 0, 40, 20)])
    farm_map = FarmMap(
        width=40,
        height=40,
        fixed=[FixedItem(id="farmhouse", x=17, y=22, width=4, height=4)],
        zones=[garden],
    )
    layout = plan_layout(farm, level=5, farm_map=farm_map, design=True)
    _check_layout(layout)
    assert layout.design_zones
    zone = garden.tiles()
    for pb in layout.blocks:
        if pb.frame is not None:
            assert not (
                {
                    (pb.frame.x + i, pb.frame.y + j)
                    for i in range(pb.frame.w)
                    for j in range(pb.frame.h)
                }
                & zone
            ), pb.block.id
    assert not layout.design.decorations & zone
    data = layout_to_dict(layout)["design"]["figures"]
    assert data["design_zone_tiles"] == len(zone)
    assert "Design zones" in layout_to_markdown(layout)
    assert "#8B5CF6" in render_svg(layout)
    # switched off: the zone is ordinary land
    off = plan_layout(farm, level=5, farm_map=farm_map, design_zones=False)
    assert not off.design_zones


def test_item_gap_shrinks_before_blocks_are_left_out(
    farm: DataSet, caplog: pytest.LogCaptureFixture
) -> None:
    """Placing every block comes first: the gap is lowered, then the reserve."""
    roomy = plan_layout(
        farm, level=5, farm_map=FarmMap(width=30, height=30), item_gap=2
    )
    assert roomy.item_gap == 2 and roomy.item_gap_requested == 2

    tight = FarmMap(width=25, height=25)
    with caplog.at_level("WARNING"):
        layout = plan_layout(farm, level=5, farm_map=tight, item_gap=2)
    assert not layout.unplaced_blocks
    assert layout.item_gap == 1 and layout.item_gap_requested == 2
    assert layout.reserve_ratio == 0.2  # the reserve is kept while the gap shrinks
    assert "Item gap lowered from 2 to 1" in caplog.text
    assert "lowered from 2 so that every block fits" in layout_to_markdown(layout)
    assert layout_to_dict(layout)["item_gap"] == 1

    # no gap left: paths fall back from every building to the blocks
    tighter = FarmMap(width=21, height=21)
    with caplog.at_level("WARNING"):
        no_gap = plan_layout(
            farm,
            level=5,
            farm_map=tighter,
            item_gap=1,
            design=True,
            path_targets="buildings",
        )
    assert no_gap.item_gap == 0 and not no_gap.unplaced_blocks
    assert "paths go to the blocks" in caplog.text
    assert not any("/" in k for k in no_gap.design.connected)
    assert no_gap.design.path_targets == "blocks"


# ---------------------------------------------------------------------------
# Block images and collage
# ---------------------------------------------------------------------------


def _designed(farm: DataSet):
    farm_map = FarmMap(
        width=40,
        height=40,
        fixed=[FixedItem(id="farmhouse", x=17, y=17, width=6, height=6)],
    )
    return plan_layout(farm, level=5, farm_map=farm_map, design=True)


def test_block_layout_puts_one_block_on_its_own_grid(farm: DataSet) -> None:
    layout = _designed(farm)
    pb = next(b for b in layout.blocks if b.frame is not None and b.items)
    small = visuals.block_layout(layout, pb)
    (only,) = small.blocks
    m = visuals.MARGIN_TILES
    assert (only.frame.x, only.frame.y) == (m, m)
    assert (small.farm_map.width, small.farm_map.height) == (
        pb.frame.w + 2 * m,
        pb.frame.h + 2 * m,
    )
    # the items keep their place inside the frame
    dx, dy = m - pb.frame.x, m - pb.frame.y
    assert [(i.rect.x - dx, i.rect.y - dy) for i in only.items] == [
        (i.rect.x, i.rect.y) for i in pb.items
    ]
    # paths: only those around the block, moved with it
    assert small.design is not None
    for x, y in small.design.paths:
        assert 0 <= x < small.farm_map.width and 0 <= y < small.farm_map.height
    # the legend tells the map position
    svg = render_svg(small, offset=(pb.frame.x - m, pb.frame.y - m), scale=2)
    assert f"at ({pb.frame.x}, {pb.frame.y})" in svg
    unplaced = PlacedBlock(pb.block, None)
    with pytest.raises(ValueError):
        visuals.block_layout(layout, unplaced)


def test_collage_lays_every_block_side_by_side(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5)
    collage = visuals.collage_layout(layout)
    placed = {b.block.id for b in layout.blocks if b.frame is not None}
    assert {b.block.id for b in collage.blocks} == placed
    frames = [b.frame for b in collage.blocks]
    assert _no_overlap(frames, gap=visuals.COLLAGE_GAP)
    assert all(
        f.x >= 0
        and f.y >= 0
        and f.x + f.w <= collage.farm_map.width
        and f.y + f.h <= collage.farm_map.height
        for f in frames
    )
    assert collage.design is None and collage.fixed_unplaced == []
    _check_layout(collage)


def test_write_block_images(farm: DataSet, tmp_path: Path) -> None:
    layout = _designed(farm)
    stale = tmp_path / "gone_block.svg"
    stale.parent.mkdir(exist_ok=True)
    stale.write_text("<svg/>")
    paths = visuals.write_block_images(layout, tmp_path)
    placed = [b for b in layout.blocks if b.frame is not None]
    assert len(paths) == len(placed) + 1
    assert paths[-1].name == "collage.svg"
    assert not stale.exists()  # images of an earlier run are removed
    text = (tmp_path / f"{placed[0].block.id}.svg").read_text()
    assert f"<title>{placed[0].block.name} - level 5</title>" in text


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_block_images_setting(tmp_path: Path) -> None:
    args = ["--level", "20", "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    assert (tmp_path / "blocks" / "collage.svg").exists()
    off = tmp_path / "off"
    config = _design_config(tmp_path, block_images=False)
    assert (
        cli.main(["--level", "20", "--design-config", config, "--output-dir", str(off)])
        == 0
    )
    assert not (off / "blocks").exists()


def _garden(mode: str, **change) -> dict[str, BlockTemplate]:
    """Dairy and two cow pastures (one more than owned) with decoration tiles."""
    t = {
        "width": 9,
        "height": 9,
        "buildings": [
            {"location_id": "dairy", "x": 0, "y": 0, "width": 4, "height": 4},
            {"location_id": "cow_pasture", "x": 5, "y": 0, "width": 4, "height": 4},
            {"location_id": "cow_pasture", "x": 5, "y": 5, "width": 4, "height": 4},
        ],
        "decorations": [[4, 0, 1, 9], [0, 4, 4, 1]],
    } | change
    return {
        "dairy_block": BlockTemplate("garden", DesignTemplate.model_validate(t), mode)
    }


def _inside(r: Rect, frame: Rect) -> bool:
    return (
        frame.x <= r.x
        and r.x + r.w <= frame.x + frame.w
        and frame.y <= r.y
        and r.y + r.h <= frame.y + frame.h
    )


def test_template_reserve_keeps_its_area_free(farm: DataSet) -> None:
    plain = plan_layout(farm, level=5)
    layout = plan_layout(farm, level=5, templates=_garden("reserve"))
    pb = next(b for b in layout.blocks if b.block.id == "dairy_block")
    t = pb.template
    assert t is not None and t.mode == "reserve" and (t.rect.w, t.rect.h) == (9, 9)
    assert _inside(t.rect, pb.frame)
    every = [i.rect for b in layout.blocks for i in b.items]
    assert not any(r.overlaps(t.rect) for r in every)
    # the block keeps its own copies and grows by the template
    before = next(b for b in plain.blocks if b.block.id == "dairy_block")
    assert len(pb.items) == len(before.items)
    assert pb.frame.w * pb.frame.h > before.frame.w * before.frame.h
    assert layout.templates == {"dairy_block": "garden"}
    data = layout_to_dict(layout)
    block = next(b for b in data["blocks"] if b["id"] == "dairy_block")
    assert block["template"]["name"] == "garden" and block["template"]["width"] == 9
    assert "## Design templates" in layout_to_markdown(layout)
    assert "design template" in render_svg(layout)


def test_template_arrange_places_its_buildings(farm: DataSet) -> None:
    layout = plan_layout(farm, level=5, templates=_garden("arrange"))
    pb = next(b for b in layout.blocks if b.block.id == "dairy_block")
    t = pb.template
    assert t is not None and t.mode == "arrange"
    ox, oy = t.rect.x, t.rect.y
    at = {(i.location_id, i.rect.x - ox, i.rect.y - oy): i for i in pb.items}
    assert ("dairy", 0, 0) in at and ("cow_pasture", 5, 0) in at
    # one cow pasture is owned at level 5: the template's second one is reserved
    assert not at[("cow_pasture", 5, 0)].reserved
    assert at[("cow_pasture", 5, 5)].reserved
    assert sum(i.location_id == "cow_pasture" for i in pb.items) == 2
    assert {d.x - ox for d in t.decorations} == {4, 0}
    every = [i.rect for b in layout.blocks for i in b.items]
    assert not any(r.overlaps(d) for r in every for d in t.decorations)
    # the rest of the block is packed outside the template frame
    ice = next(i for i in pb.items if i.location_id == "ice_cream_maker")
    assert not ice.rect.overlaps(t.rect)
    assert all(_inside(i.rect, pb.frame) for i in pb.items)


def test_template_building_must_belong_to_the_block(farm: DataSet) -> None:
    bad = [{"location_id": "bakery", "x": 0, "y": 0, "width": 3, "height": 3}]
    with pytest.raises(ValueError, match="bakery is not in block dairy_block"):
        plan_layout(farm, level=5, templates=_garden("arrange", buildings=bad))
    wrong = [{"location_id": "dairy", "x": 0, "y": 0, "width": 3, "height": 3}]
    with pytest.raises(ValueError, match="footprint is 4x4"):
        plan_layout(farm, level=5, templates=_garden("reserve", buildings=wrong))
    # a rotatable building may stand transposed
    turned = [
        {"location_id": "ice_cream_maker", "x": 0, "y": 0, "width": 2, "height": 3}
    ]
    layout = plan_layout(
        farm, level=5, templates=_garden("arrange", buildings=turned, decorations=[])
    )
    pb = next(b for b in layout.blocks if b.block.id == "dairy_block")
    ice = next(i for i in pb.items if i.location_id == "ice_cream_maker")
    assert ice.rotated and (ice.rect.w, ice.rect.h) == (2, 3)


def test_template_of_an_unknown_block_is_skipped(
    farm: DataSet, caplog: pytest.LogCaptureFixture
) -> None:
    tpl = _garden("reserve")
    with caplog.at_level("WARNING"):
        layout = plan_layout(
            farm, level=5, templates={"loom_block": tpl["dairy_block"]}
        )
    assert "no block loom_block" in caplog.text
    assert all(pb.template is None for pb in layout.blocks)


def test_templates_are_dropped_before_the_reserve(
    farm: DataSet, caplog: pytest.LogCaptureFixture
) -> None:
    """A template is a wish: the item gap goes first, then the template."""
    big = _garden("reserve", width=20, height=20)
    tight = FarmMap(width=25, height=25)
    with caplog.at_level("WARNING"):
        layout = plan_layout(farm, level=5, farm_map=tight, item_gap=1, templates=big)
    assert not layout.unplaced_blocks
    assert layout.templates_dropped == ["dairy_block"]
    assert all(pb.template is None for pb in layout.blocks)
    assert layout.item_gap == 0
    assert "Design templates dropped" in caplog.text
    assert "Dropped so that every block fits" in layout_to_markdown(layout)
    assert layout_to_dict(layout)["templates_dropped"] == ["dairy_block"]


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_cli_uses_the_example_template(tmp_path: Path) -> None:
    """config/templates/dairy_garden.example.json on the dairy block."""
    config = _design_config(
        tmp_path, templates={"dairy_block": {"template": "dairy_garden"}}
    )
    args = ["--level", "20", "--design-config", config, "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    data = json.loads((tmp_path / "layout.json").read_text())
    block = next(b for b in data["blocks"] if b["id"] == "dairy_block")
    assert block["template"]["name"] == "dairy_garden" or data["templates_dropped"]

    missing = _design_config(tmp_path, templates={"dairy_block": {"template": "nope"}})
    args[3] = missing
    assert cli.main(args) == 1


def test_template_of_a_block_without_items_is_skipped(
    farm: DataSet, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No items, no frame: the template is neither listed nor reported as dropped."""
    real = planner_module._pack_block

    def empty_dairy(b, *args):
        return ([], None) if b.id == "dairy_block" else real(b, *args)

    monkeypatch.setattr(planner_module, "_pack_block", empty_dairy)
    with caplog.at_level("WARNING"):
        layout = plan_layout(farm, level=5, templates=_garden("reserve"))
    assert layout.templates == {}
    assert layout.templates_dropped == []
    assert "dairy_block has no items" in caplog.text
