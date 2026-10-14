"""Combiner: layout sized by the production plan (real data, no network)."""

from __future__ import annotations

import importlib
import json
import math
import re
from pathlib import Path

import pytest

from src.combiner import cli, combine, sizing_from_plan, upcoming_unlocks
from src.combiner.combine import FlowLink, _distance, flow_links
from src.combiner.report import _demote, combined_to_dict, combined_to_markdown
from src.config import PlayerConfig
from src.layout.farm_map import FarmMap, FixedItem
from src.layout.packing import Rect
from src.loaders.json_loader import DataSet, load_data
from src.models import LocationType
from src.planner import run_planner

DATA_DIR = Path("data")
LEVEL = 20  # a mid-game test level; the code never hard-codes one

pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="no real data"
)


@pytest.fixture(scope="module")
def full() -> DataSet:
    return load_data(DATA_DIR)


@pytest.fixture(scope="module")
def player() -> PlayerConfig:
    return PlayerConfig(level=LEVEL)


def test_layout_and_planner_stay_independent() -> None:
    """Only the Combiner may import both planners."""
    for package, other in (("layout", "planner"), ("planner", "layout")):
        for path in Path("src", package).glob("*.py"):
            text = path.read_text(encoding="utf-8")
            pattern = rf"^\s*(from|import)\s+(src\.{other}|\.\.{other})\b"
            assert not re.search(pattern, text, re.MULTILINE), path


def test_sizing_from_plan(full: DataSet, player: PlayerConfig) -> None:
    data = full.filter_by_max_level(LEVEL)
    plan = run_planner(player, data).chosen
    sizing = sizing_from_plan(plan, data)

    # fields: whole numbers that add up to what the plan uses
    assert sum(sizing.crop_fields.values()) == math.ceil(plan.fields_used - 1e-6)
    assert set(sizing.crop_fields) <= set(plan.crops)
    # every crop with fields has its users, and crops are no flow between blocks
    fields = {l.id for l in data.location_list if l.type == LocationType.FIELD}
    assert all(src not in fields for src, _ in sizing.flows)
    assert all(amount > 0 for amount in sizing.flows.values())
    # recommended trees / bushes become whole copies
    for fp in plan.fruits.values():
        if fp.plants_source == "recommended":
            assert sizing.counts[fp.location_id] == math.ceil(fp.plants - 1e-6)


def test_upcoming_unlocks(full: DataSet) -> None:
    extra, upcoming = upcoming_unlocks(full, LEVEL, 5)
    assert upcoming
    assert all(LEVEL < u.unlock_level <= LEVEL + 5 for u in upcoming)
    limits = full.level_limits
    fields = next(u for u in upcoming if u.kind == "fields")
    assert fields.count == limits.fields_at(LEVEL + 5) - limits.fields_at(LEVEL)
    # more copies of placed buildings are reserved; new unlocks are only listed
    assert {u.location_id for u in upcoming if u.kind in ("copies", "fields")} == set(
        extra
    )
    new = {u.location_id for u in upcoming if u.kind == "new"}
    assert not new & set(extra)
    assert upcoming_unlocks(full, LEVEL, 0) == ({}, [])


def test_combine(full: DataSet, player: PlayerConfig) -> None:
    farm_map = FarmMap(
        width=70,
        height=70,
        fixed=[FixedItem(id="farmhouse", x=30, y=30, width=6, height=6)],
    )
    combined = combine(full, player, farm_map, lookahead=3)
    layout = combined.layout
    assert layout.sized and not layout.unplaced_blocks
    assert layout.strategy in ("flow", "size")
    assert layout.design is None  # the design layer only when requested

    # every owned field is in a block
    stock = {s.location.id: s for s in layout.stock}
    field_id = next(
        k for k, s in stock.items() if s.location.type == LocationType.FIELD
    )
    assert (
        sum(pb.fields.count for pb in layout.blocks if pb.fields)
        == stock[field_id].count
    )
    # recommended trees / bushes are placed with the plan's count
    for loc_id, n in combined.sizing.counts.items():
        if n > 0:
            assert stock[loc_id].count == n
    # flows between placed blocks have a distance
    assert combined.flow_links
    assert all(link.distance is not None for link in combined.flow_links)
    assert combined.free_tiles is not None and combined.free_tiles > 0

    data = full.filter_by_max_level(LEVEL)
    payload = combined_to_dict(combined, data)
    assert payload["summary"]["design"] is False
    assert payload["layout"]["sized_by_production"] is True
    assert payload["schedule"]["level"] == LEVEL
    assert [b["id"] for b in payload["blocks"]][: len(layout.flow_order)] == [
        b for b in layout.flow_order
    ]
    md = combined_to_markdown(combined, data)
    assert md.startswith(f"# Combined farm plan - level {LEVEL}")
    assert md.count("\n# ") == 0  # the layout and schedule headings are demoted
    assert "## Goods flows between blocks" in md

    with_design = combine(full, player, farm_map, lookahead=0, design=True)
    assert with_design.layout.design is not None
    assert with_design.upcoming == []
    with pytest.raises(ValueError):
        combine(full, player, farm_map, lookahead=-1)


def test_flow_links_and_distance() -> None:
    assert _distance(Rect(0, 0, 2, 2), Rect(2, 0, 2, 2)) == 0  # touching
    assert _distance(Rect(0, 0, 2, 2), Rect(5, 4, 1, 1)) == 5
    assert _distance(Rect(0, 0, 1, 1), None) is None


def test_flow_links_merge_locations_into_blocks(
    full: DataSet, player: PlayerConfig
) -> None:
    combined = combine(full, player, lookahead=0)
    links = flow_links(combined.layout, {("no_such", "x"): 1.0})
    assert links == []
    heaviest = combined.flow_links[0]
    assert isinstance(heaviest, FlowLink) and heaviest.source != heaviest.target
    assert heaviest.per_hour == max(link.per_hour for link in combined.flow_links)


def test_demote_skips_code_fences() -> None:
    assert _demote("# A\n```\n# not a heading\n```\n## B") == (
        "## A\n```\n# not a heading\n```\n### B"
    )


def test_cli_writes_combined_outputs(tmp_path: Path) -> None:
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": LEVEL}))
    args = ["--player-config", str(player), "--output-dir", str(tmp_path)]
    assert cli.main([*args, "--design", "--lookahead", "2"]) == 0
    for name in ("combined.json", "combined.md", "combined.svg"):
        assert (tmp_path / name).exists()
    data = json.loads((tmp_path / "combined.json").read_text())
    assert data["level"] == LEVEL and data["summary"]["design"] is True
    assert data["expansion"]["lookahead_levels"] == 2

    assert cli.main([*args, "--lookahead", "-1"]) == 1
    assert cli.main([*args, "--storage-share", "0"]) == 1


def test_cli_reports_unsolvable_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsolvable(*args, **kwargs):
        raise RuntimeError("Production plan not solvable: test")

    # the package exports the function combine, which shadows the module name
    module = importlib.import_module("src.combiner.combine")
    monkeypatch.setattr(module, "run_planner", unsolvable)
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": LEVEL}))
    args = ["--player-config", str(player), "--output-dir", str(tmp_path)]
    assert cli.main(args) == 1
    assert not (tmp_path / "combined.json").exists()
