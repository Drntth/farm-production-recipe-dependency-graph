"""Relocation plan: keep / store / place lists from the current farm to a layout."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src import cli as unified
from src.layout.farm_map import CurrentItem, FarmMap, FixedItem
from src.loaders.json_loader import DataSet
from src.models import Location, LocationType
from src.relocation import (
    cli,
    load_layout,
    plan_relocation,
    relocation_to_dict,
    relocation_to_markdown,
)

P, A, F = LocationType.PRODUCTION, LocationType.ANIMAL, LocationType.FIELD


def _loc(id_, type_, w=None, h=None, **kw) -> Location:
    return Location(
        id=id_,
        name=id_,
        type=type_,
        unlock_level=1,
        footprint_width=w,
        footprint_height=h,
        **kw,
    )


@pytest.fixture
def data() -> DataSet:
    # synthetic sizes, not game values
    return DataSet(
        [
            _loc("dairy", P, 4, 4),
            _loc("cow_pasture", A, 4, 4),
            _loc("field", F, 1, 1),
            _loc("bakery", P, 3, 3),
            _loc("ice_cream_maker", P, 3, 2, rotatable=True),
            _loc("smelter", P, 2, 1),
            _loc("mine", LocationType.OTHER, movable=False),
            _loc("lure_workbench", P, 2, 2, area="fishing_lake", movable=False),
        ],
        [],
        [],
    )


def _item(id_, x, y, w, h, *, rotated=False, reserved=False) -> dict:
    return {
        "location_id": id_,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "rotated": rotated,
        "reserved": reserved,
    }


@pytest.fixture
def layout() -> dict:
    """The part of layout_to_dict the relocation plan reads."""
    return {
        "level": 20,
        "map": {"bounded": True, "width": 20, "height": 20},
        "fixed": [
            {"id": "mine", "name": "Mine", "x": 0, "y": 0, "width": 2, "height": 2}
        ],
        "blocks": [
            {
                "id": "dairy_block",
                "name": "Dairy block",
                "items": [
                    _item("dairy", 2, 2, 4, 4),
                    _item("cow_pasture", 6, 2, 4, 4),
                    _item("cow_pasture", 6, 6, 4, 4, reserved=True),
                    _item("field", 2, 6, 1, 1),
                    _item("field", 3, 6, 1, 1),
                ],
            },
            {
                "id": "bakery_block",
                "name": "Bakery block",
                "items": [
                    _item("bakery", 12, 2, 3, 3),
                    _item("ice_cream_maker", 12, 6, 2, 3, rotated=True),
                ],
            },
        ],
    }


def _map(*current: CurrentItem, size: int = 20) -> FarmMap:
    mine = FixedItem(id="mine", x=0, y=0, width=2, height=2)
    return FarmMap(width=size, height=size, fixed=[mine], current=list(current))


@pytest.fixture
def farm_map() -> FarmMap:
    return _map(
        CurrentItem(id="dairy", x=2, y=2, width=4, height=4),  # at its target
        CurrentItem(id="cow_pasture", x=10, y=10, width=4, height=4),
        CurrentItem(id="bakery", x=0, y=10, width=3, height=3),
        CurrentItem(id="bakery", x=3, y=10, width=3, height=3),
        CurrentItem(id="field", count=1),
    )


def test_keep_store_place(layout: dict, farm_map: FarmMap, data: DataSet) -> None:
    plan = plan_relocation(layout, farm_map, data)
    assert [(t.location_id, t.rect) for t in plan.keep] == [("dairy", (2, 2, 4, 4))]
    assert [(c.id, c.x) for c in plan.store] == [
        ("bakery", 0),
        ("bakery", 3),
        ("cow_pasture", 10),
        ("field", None),
    ]
    assert [t.location_id for t in plan.place] == [
        "cow_pasture",
        "field",
        "field",
        "bakery",
        "ice_cream_maker",
    ]
    assert [t.rect for t in plan.reserved] == [(6, 6, 4, 4)]
    assert plan.surplus == {"bakery": 1}
    assert plan.missing == {"field": 1, "ice_cream_maker": 1}
    assert plan.current_copies == 5
    # 1 item stays, 3 placed items have to be stored first
    assert plan.new_slot_simpler


def test_keep_matches_each_target_once(layout: dict, data: DataSet) -> None:
    # two current copies on the same target (a measuring error): one is kept
    twice = CurrentItem(id="dairy", x=2, y=2, width=4, height=4)
    plan = plan_relocation(layout, _map(twice, twice), data)
    assert len(plan.keep) == 1
    assert [c.id for c in plan.store] == ["dairy"]
    assert not plan.new_slot_simpler


def test_rotated_current_item_is_accepted(layout: dict, data: DataSet) -> None:
    turned = CurrentItem(id="ice_cream_maker", x=12, y=6, width=2, height=3)
    plan = plan_relocation(layout, _map(turned), data)
    assert [t.location_id for t in plan.keep] == ["ice_cream_maker"]


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (CurrentItem(id="windmill", count=1), "Unknown current item id 'windmill'"),
        (CurrentItem(id="mine", count=1), "cannot be current items: mine"),
        (CurrentItem(id="lure_workbench"), "not a movable farm item"),
        (CurrentItem(id="dairy", x=0, y=4, width=3, height=3), "footprint is 4x4"),
        # not rotatable: the swapped size is wrong
        (CurrentItem(id="smelter", x=4, y=4, width=1, height=2), "footprint is 2x1$"),
    ],
)
def test_current_item_errors(
    layout: dict, data: DataSet, item: CurrentItem, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        plan_relocation(layout, _map(item), data)


def test_layout_of_another_map_is_an_error(layout: dict, data: DataSet) -> None:
    with pytest.raises(ValueError, match="20x20 map, this one is 30x30"):
        plan_relocation(layout, _map(size=30), data)
    moved = FarmMap(
        width=20, height=20, fixed=[FixedItem(id="mine", x=5, y=5, width=2, height=2)]
    )
    with pytest.raises(ValueError, match="elsewhere on the farm map: mine"):
        plan_relocation(layout, moved, data)
    with pytest.raises(ValueError, match="farm map has no size"):
        plan_relocation(layout, FarmMap(), data)
    layout["map"] = {"bounded": False, "width": None, "height": None}
    with pytest.raises(ValueError, match="without a farm map"):
        plan_relocation(layout, _map(), data)


def test_load_layout_reads_layout_and_combined(layout: dict, tmp_path: Path) -> None:
    (tmp_path / "layout.json").write_text(json.dumps(layout))
    (tmp_path / "combined.json").write_text(json.dumps({"layout": layout, "level": 20}))
    (tmp_path / "other.json").write_text(json.dumps({"level": 20}))
    assert load_layout(tmp_path / "layout.json") == layout
    assert load_layout(tmp_path / "combined.json") == layout
    (tmp_path / "list.json").write_text("[]")
    for name in ("other.json", "list.json"):
        with pytest.raises(ValueError, match="Not a layout"):
            load_layout(tmp_path / name)


def test_report(layout: dict, farm_map: FarmMap, data: DataSet) -> None:
    plan = plan_relocation(layout, farm_map, data)
    d = relocation_to_dict(plan, "output/combined.json")
    assert d["summary"] == {
        "current_copies": 5,
        "keep": 1,
        "store": 4,
        "place": 5,
        "reserved": 1,
        "not_in_layout": 1,
        "not_owned": 2,
    }
    assert [b["block"] for b in d["place"]] == ["dairy_block", "bakery_block"]
    assert d["store"][-1] == {"location_id": "field", "count": 1}
    assert "new layout slot" in d["note"]
    md = relocation_to_markdown(plan, "output/combined.json")
    for text in ("## Keep", "## Store", "### Bakery block", "## Not owned yet"):
        assert text in md
    assert "| ice_cream_maker | (12, 6) 2x3 | yes |" in md
    assert "| 1 | 4 | 5 | 1 | 1 | 2 |" in md
    assert "no current farm" not in md
    empty = relocation_to_markdown(plan_relocation(layout, _map(), data), "x.json")
    assert "no current farm" in empty
    assert "| 0 | 0 | 6 | 1 | 0 | 6 |" in empty


def test_cli_writes_the_report(
    layout: dict,
    farm_map: FarmMap,
    data: DataSet,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cli, "load_data", lambda _dir: data)
    map_file = tmp_path / "farm_map.json"
    map_file.write_text(farm_map.model_dump_json())
    out = tmp_path / "out"
    args = ["--map", str(map_file), "--output-dir", str(out)]
    assert cli.main(args) == 1  # no layout yet
    out.mkdir()
    (out / "layout.json").write_text(json.dumps(layout))
    assert cli.main(args) == 0
    assert json.loads((out / "relocation.json").read_text())["layout_file"].endswith(
        "layout.json"
    )
    assert (out / "relocation.md").exists()
    # combined.json wins over layout.json; --layout picks a file
    assert cli.default_layout(out) == out / "layout.json"
    (out / "combined.json").write_text(json.dumps({"layout": layout}))
    assert cli.default_layout(out) == out / "combined.json"
    # an older combined.json still wins, with a warning
    os.utime(out / "combined.json", (0, 0))
    with caplog.at_level("WARNING", logger="src.relocation"):
        assert cli.default_layout(out) == out / "combined.json"
    assert "is newer than" in caplog.text
    bad = _map(CurrentItem(id="windmill"))
    map_file.write_text(bad.model_dump_json())
    assert cli.main([*args, "--layout", str(out / "layout.json")]) == 1


def test_relocate_is_a_command_but_not_part_of_all() -> None:
    assert unified.COMMANDS["relocate"][0] == "src.relocation.cli"
    assert "relocate" not in [c for c, _ in unified.ALL_STEPS]
