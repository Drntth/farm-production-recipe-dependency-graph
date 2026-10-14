"""Production Planner: profile defaults, mastery modifiers, capacity model."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest

from src.config import MasterySystem, PlayerConfig
from src.loaders.json_loader import DataSet
from src.models import (
    FieldGrant,
    LevelLimits,
    Location,
    LocationInstance,
    MasteryBonus,
    Recipe,
    Resource,
)
from src.planner import (
    LineKind,
    StarsModifier,
    WorkbenchModifier,
    build_capacity,
    mastery_modifier,
    resolve_profile,
)
from src.planner.cli import main
from src.planner.quantities import login_cycle_hours, plan_production
from src.planner.schedule import (
    build_schedule,
    compare_intervals,
    schedule_to_markdown,
    suggest_interval,
)


def _loc(loc_id: str, loc_type: str, level: int = 1, **kw) -> Location:
    return Location(
        id=loc_id, name=loc_id.title(), type=loc_type, unlock_level=level, **kw
    )


def _recipe(rec_id: str, loc_id: str, base: int, three_star: int | None = None):
    return Recipe(
        id=rec_id,
        name=rec_id.title(),
        location_id=loc_id,
        unlock_level=1,
        output={"resource_id": rec_id, "amount": 1},
        production_time_seconds=base,
        production_time_3star_seconds=three_star,
    )


def _res(res_id: str, res_type: str, source: str | None = None, growth=None):
    return Resource(
        id=res_id,
        name=res_id.title(),
        type=res_type,
        unlock_level=1,
        source_location_id=source,
        growth_time_seconds=growth,
    )


def _dataset() -> DataSet:
    locations = [
        _loc("field", "field"),
        _loc("barn", "storage"),
        _loc("chicken_coop", "animal", animal_capacity=6),
        _loc("feed_mill", "production", base_slots=3),
        _loc("bakery", "production", base_slots=2),
        _loc("duck_salon", "animal", base_slots=1, max_slots=6),
        _loc("beehive_tree", "animal"),
        _loc("apple_tree", "tree", lifetime_yield=13, lifetime_harvests=4),
        _loc("mine", "other"),
    ]
    resources = [
        _res("wheat", "crop", "field", growth=120),
        _res("apple", "crop", "apple_tree", growth=57600),
        _res("egg", "animal_product", "chicken_coop", growth=1200),
        _res("duck_feather", "animal_product", "duck_salon"),
        _res("chicken_feed", "processed_material"),
        _res("bread", "processed_material"),
    ]
    recipes = [
        _recipe("egg", "chicken_coop", 1200),
        _recipe("chicken_feed", "feed_mill", 300, 240),
        _recipe("bread", "bakery", 300, 255),
        _recipe("duck_feather", "duck_salon", 10800),
    ]
    limits = LevelLimits(
        field_grants=[FieldGrant(level=1, count=6), FieldGrant(level=3, count=3)],
        location_instances=[
            LocationInstance(location_id="chicken_coop", instance=1, unlock_level=1),
            LocationInstance(location_id="chicken_coop", instance=2, unlock_level=12),
            LocationInstance(location_id="feed_mill", instance=1, unlock_level=1),
            LocationInstance(location_id="feed_mill", instance=2, unlock_level=12),
        ],
    )
    bonuses = [
        MasteryBonus(location_id="feed_mill", stars=s, time_reduction_percent=p)
        for s, p in ((1, 5), (2, 10), (3, 15))
    ] + [MasteryBonus(location_id="bakery", stars=3, time_reduction_percent=15)]
    return DataSet(locations, resources, recipes, limits, bonuses)


# ---------------------------------------------------------------------------
# Profile defaults (option B)
# ---------------------------------------------------------------------------


def test_empty_profile_gets_level_defaults() -> None:
    profile = resolve_profile(PlayerConfig(level=20), _dataset())
    loc = profile.locations

    assert loc["chicken_coop"].owned == 2  # all copies unlocked at the level
    assert loc["chicken_coop"].animals == 12  # full shelters
    assert loc["feed_mill"].slots == 6  # base slots x copies
    assert loc["bakery"].owned == 1  # single building without limit rows
    assert loc["bakery"].mastery_stars == 0
    assert loc["duck_salon"].slots == 1
    assert loc["beehive_tree"].beehives == 1
    assert loc["apple_tree"].owned is None  # to be recommended
    assert "field" not in loc and "barn" not in loc
    assert profile.fields_owned is None
    assert profile.fields_available == 9
    assert profile.missing() == ["barn_capacity", "silo_capacity"]


def test_profile_values_win_over_defaults() -> None:
    player = PlayerConfig(
        level=20,
        barn_capacity=500,
        silo_capacity=600,
        fields_owned=7,
        locations={
            "chicken_coop": {"owned": 1},
            "feed_mill": {"slots": 9, "mastery_stars": 2},
            "apple_tree": {"owned": 4},
        },
    )
    profile = resolve_profile(player, _dataset())
    coop = profile.locations["chicken_coop"]

    assert coop.owned == 1
    assert coop.animals == 6  # default follows the given copies
    assert "owned" not in coop.defaults
    assert "animals" in coop.defaults
    assert profile.locations["feed_mill"].slots == 9
    assert profile.locations["apple_tree"].owned == 4
    assert profile.fields_owned == 7
    assert profile.missing() == []


def test_profile_ignores_locations_above_the_level() -> None:
    data = _dataset().filter_by_max_level(1)
    player = PlayerConfig(level=1, locations={"sushi_bar": {"slots": 2}})
    assert "sushi_bar" not in resolve_profile(player, data).locations


# ---------------------------------------------------------------------------
# Mastery modifiers
# ---------------------------------------------------------------------------


def _times(stars: int) -> tuple[int | None, int | None]:
    data = _dataset()
    player = PlayerConfig(
        level=20,
        locations={
            "feed_mill": {"mastery_stars": stars},
            "bakery": {"mastery_stars": stars},
        },
    )
    profile = resolve_profile(player, data)
    mod = StarsModifier(data.mastery_bonuses)
    feed_mill, bakery = profile.locations["feed_mill"], profile.locations["bakery"]
    return (
        mod.production_time(data.recipes["chicken_feed"], feed_mill),
        mod.production_time(data.recipes["bread"], bakery),
    )


@pytest.mark.parametrize(
    ("stars", "feed", "bread"),
    [
        (0, 300, 300),
        (1, 285, 300),  # feed mill: 5 % at one star, bakery: coins only
        (2, 270, 300),
        (3, 240, 255),  # three stars: the scraped 3-star time
    ],
)
def test_stars_modifier(stars: int, feed: int, bread: int) -> None:
    assert _times(stars) == (feed, bread)


def test_stars_without_3star_time_use_the_bonus() -> None:
    mod = StarsModifier(
        [MasteryBonus(location_id="bakery", stars=3, time_reduction_percent=15)]
    )
    recipe = _recipe("bread", "bakery", 300)
    profile = resolve_profile(
        PlayerConfig(level=1, locations={"bakery": {"mastery_stars": 3}}), _dataset()
    )
    assert mod.production_time(recipe, profile.locations["bakery"]) == 255


def test_workbench_uses_base_time_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mod = mastery_modifier(MasterySystem.WORKBENCH, _dataset())
    assert isinstance(mod, WorkbenchModifier)
    recipe = _dataset().recipes["chicken_feed"]
    with caplog.at_level(logging.WARNING):
        assert mod.production_time(recipe, None) == 300
        assert mod.production_time(recipe, None) == 300
    assert sum("Workbench" in r.message for r in caplog.records) == 1


# ---------------------------------------------------------------------------
# Capacity model
# ---------------------------------------------------------------------------


def _capacity(player: PlayerConfig):
    data = _dataset()
    profile = resolve_profile(player, data)
    return build_capacity(profile, data, mastery_modifier(player.mastery_system, data))


def test_capacity_parallel_lines_and_queues() -> None:
    cap = _capacity(PlayerConfig(level=20, locations={"duck_salon": {"slots": 4}}))
    loc = cap.locations

    # machines: copies run in parallel, slots only queue
    assert (loc["feed_mill"].kind, loc["feed_mill"].parallel) == (LineKind.MACHINE, 2)
    assert loc["feed_mill"].queue == 6
    # animals: each animal produces on its own
    assert (loc["chicken_coop"].kind, loc["chicken_coop"].parallel) == (
        LineKind.ANIMAL,
        12,
    )
    # duck salon: one duck per slot
    assert (loc["duck_salon"].kind, loc["duck_salon"].parallel) == (
        LineKind.SLOT_ANIMAL,
        4,
    )
    assert loc["beehive_tree"].kind == LineKind.BEEHIVE
    assert loc["apple_tree"].parallel is None
    assert loc["mine"].kind == LineKind.OTHER


def test_capacity_recipe_rates() -> None:
    cap = _capacity(PlayerConfig(level=20))
    # 12 chickens, one egg per 20 min each
    assert cap.recipes["egg"].max_per_hour == pytest.approx(36)
    # 2 feed mills, 5 min each
    assert cap.recipes["chicken_feed"].max_per_hour == pytest.approx(24)
    assert cap.recipes["duck_feather"].max_per_hour == pytest.approx(1 / 3)


def test_capacity_crops_and_storage() -> None:
    cap = _capacity(PlayerConfig(level=20, barn_capacity=75, fields_owned=8))
    # one planted crop gives two, one goes back into the field: +1 per 2 min
    assert cap.crops["wheat"].net_per_field_per_hour == pytest.approx(30)
    assert "apple" not in cap.crops  # tree fruit, not a field crop
    # 13 apples over 4 harvests, one harvest per 16 h
    assert cap.fruits["apple"].yield_per_harvest == pytest.approx(3.25)
    assert cap.fruits["apple"].per_plant_per_hour == pytest.approx(3.25 / 16)
    assert (cap.fields, cap.fields_source) == (8, "profile")
    assert (cap.barn_capacity, cap.silo_capacity) == (75, None)

    level_only = _capacity(PlayerConfig(level=20))
    assert (level_only.fields, level_only.fields_source) == (9, "level")


def test_capacity_to_dict_is_json() -> None:
    data = _capacity(PlayerConfig(level=20)).to_dict()
    assert data["locations"]["feed_mill"]["kind"] == "machine"
    json.dumps(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_writes_capacity(tmp_path: Path) -> None:
    if not Path("data/locations.json").exists():
        pytest.skip("no real data")
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": 20, "barn_capacity": 100}))
    out = tmp_path / "out"

    assert main(["--player-config", str(player), "--output-dir", str(out)]) == 0
    data = json.loads((out / "capacity.json").read_text(encoding="utf-8"))
    assert data["level"] == 20
    assert data["locations"]["feed_mill"]["kind"] == "machine"


def test_cli_level_without_config(tmp_path: Path) -> None:
    if not Path("data/locations.json").exists():
        pytest.skip("no real data")
    missing = tmp_path / "nope.json"
    assert main(["--player-config", str(missing), "--output-dir", str(tmp_path)]) == 1
    assert (
        main(
            [
                "--player-config",
                str(missing),
                "--level",
                "10",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )


# ---------------------------------------------------------------------------
# Quantities (linear program) and schedule
# ---------------------------------------------------------------------------


def _farm(
    apple_trees: int | None = None, barn: int | None = None, silo: int = 500
) -> tuple:
    """Small farm: wheat / corn fields, chickens, feed mill, bakery, apples, ore."""
    locations = [
        _loc("field", "field"),
        _loc("chicken_coop", "animal", animal_capacity=6),
        _loc("feed_mill", "production", base_slots=3),
        _loc("bakery", "production", base_slots=2),
        _loc("apple_tree", "tree", lifetime_yield=12, lifetime_harvests=4),
        _loc("mine", "other"),
        _loc("smelter", "production", base_slots=1),
        _loc("beehive_tree", "animal"),
    ]
    resources = [
        _res("wheat", "crop", "field", growth=120),
        _res("corn", "crop", "field", growth=300),
        _res("apple", "crop", "apple_tree", growth=57600),
        _res("egg", "animal_product", "chicken_coop", growth=1200),
        _res("iron_ore", "ore", "mine", growth=0),
        _res("chicken_feed", "processed_material"),
        _res("bread", "processed_material"),
        _res("apple_pie", "processed_material"),
        _res("iron_bar", "processed_material"),
        _res("lucky_cake", "processed_material"),
        _res("honeycomb", "animal_product", "beehive_tree", growth=2100),
        _res("honey", "processed_material"),
    ]

    def rec(rid, loc, base, inputs):
        return Recipe(
            id=rid,
            name=rid.title(),
            location_id=loc,
            unlock_level=1,
            inputs=[{"resource_id": r, "amount": a} for r, a in inputs],
            output={"resource_id": rid, "amount": 1},
            production_time_seconds=base,
        )

    recipes = [
        rec("egg", "chicken_coop", 1200, [("chicken_feed", 1)]),
        rec("chicken_feed", "feed_mill", 300, [("wheat", 2), ("corn", 1)]),
        rec("bread", "bakery", 300, [("wheat", 3)]),
        rec("apple_pie", "bakery", 3600, [("apple", 2), ("egg", 1)]),
        rec("iron_bar", "smelter", 1800, [("iron_ore", 3)]),
        rec("lucky_cake", "bakery", 600, [("voucher", 1)]),
        rec("honey", "bakery", 1200, [("honeycomb", 2)]),
    ]
    limits = LevelLimits(field_grants=[FieldGrant(level=1, count=12)])
    data = DataSet(locations, resources, recipes, limits)
    locs = {"chicken_coop": {"owned": 1}}
    if apple_trees is not None:
        locs["apple_tree"] = {"owned": apple_trees}
    player = PlayerConfig(
        level=10, barn_capacity=barn, silo_capacity=silo, locations=locs
    )
    profile = resolve_profile(player, data)
    cap = build_capacity(profile, data, mastery_modifier(MasterySystem.STARS, data))
    return cap, profile, data


def test_login_cycle_rounds_up_to_logins() -> None:
    assert login_cycle_hours(120, 1) == 1  # wheat waits for the next login
    assert login_cycle_hours(3 * 3600, 2) == 4
    assert login_cycle_hours(4 * 3600, 2) == 4
    assert login_cycle_hours(0, 0.5) == 0.5


def test_plan_respects_balance_and_capacity() -> None:
    cap, profile, data = _farm()
    plan = plan_production(cap, profile, data, interval_hours=2)

    assert plan.balance_per_hour > 0
    for good, spare in plan.surplus_per_hour.items():
        assert spare >= plan.balance_per_hour * (1 - 1e-5), good
    # machines: time of the copies, and one queue per login
    bakery = [r for r in plan.recipes.values() if r.location_id == "bakery"]
    times = {r: data.recipes[r].production_time_seconds for r in plan.recipes}
    assert sum(r.per_hour * times[r.recipe_id] for r in bakery) <= 3600 + 1e-6
    assert sum(r.per_hour for r in bakery) * 2 <= 2 + 1e-6  # 2 slots
    # 6 chickens, one egg per 20 min, fed only every 2 h
    assert plan.recipes["egg"].per_hour <= 6 / 2 + 1e-6
    assert plan.fields_used <= 12 + 1e-6
    assert 0 < plan.utilization["bakery"] <= 1 + 1e-6


def test_plan_external_and_skipped() -> None:
    cap, profile, data = _farm()
    plan = plan_production(cap, profile, data, interval_hours=1)

    assert plan.skipped_recipes["lucky_cake"] == "external input: voucher"
    # the mine has no rate: its ore is external, limited to what balance needs
    assert plan.external_per_hour["iron_ore"] == pytest.approx(
        3 * plan.recipes["iron_bar"].per_hour
    )
    assert plan.recipes["iron_bar"].per_hour == pytest.approx(
        plan.balance_per_hour, rel=1e-4
    )


def test_beehives_make_honeycomb() -> None:
    cap, profile, data = _farm()
    assert cap.hives["honeycomb"].parallel == 1  # default: one beehive
    plan = plan_production(cap, profile, data, interval_hours=2)
    # one honeycomb per 35 min, collected every 2 h
    assert 0 < plan.hive_per_hour["honeycomb"] <= 0.5 + 1e-6
    assert "honeycomb" not in plan.external_per_hour
    rec = build_schedule(plan, [plan], cap, profile, data)["recommendations"]
    assert rec["nectar_bush"]["bushes_per_day"] == pytest.approx(
        plan.hive_per_hour["honeycomb"] * 24 / 5, abs=0.01
    )


def test_plan_recommends_trees_or_uses_profile() -> None:
    cap, profile, data = _farm()
    recommended = plan_production(cap, profile, data, interval_hours=2)
    assert recommended.fruits["apple"].plants_source == "recommended"
    assert recommended.fruits["apple"].plants > 0

    cap, profile, data = _farm(apple_trees=0)
    plan = plan_production(cap, profile, data, interval_hours=2)
    assert "apple" not in plan.fruits
    assert plan.skipped_recipes["apple_pie"] == "input not available: apple"


def test_plan_storage_share_limits_output() -> None:
    cap, profile, data = _farm(barn=10)
    plan = plan_production(cap, profile, data, interval_hours=4, storage_share=0.5)
    assert plan.barn_per_login <= 5 + 1e-6


def test_small_silo_with_owned_trees_still_plans() -> None:
    # 40 apple trees fill the 5 planned silo places alone: no crash, a warning
    cap, profile, data = _farm(apple_trees=40, silo=10)
    plan = plan_production(cap, profile, data, interval_hours=12)
    assert plan.warnings and "silo" in plan.warnings[0]
    assert plan.fields_used == 0  # no room left for crops


def test_barn_counts_honeycomb() -> None:
    cap, profile, data = _farm(barn=1000)
    plan = plan_production(cap, profile, data, interval_hours=2)
    made = sum(
        r.per_hour * data.recipes[r.recipe_id].output.amount
        for r in plan.recipes.values()
    )
    assert plan.hive_per_hour["honeycomb"] > 0
    assert plan.barn_per_login == pytest.approx(
        (made + plan.hive_per_hour["honeycomb"]) * 2
    )


def test_skipped_reason_names_only_missing_goods() -> None:
    cap, profile, data = _farm(apple_trees=0)
    data.recipes["apple_pie"].inputs.append(
        data.recipes["iron_bar"].inputs[0]  # iron ore: external, not "missing"
    )
    plan = plan_production(cap, profile, data, interval_hours=2)
    assert plan.skipped_recipes["apple_pie"] == "input not available: apple"


def test_suggest_interval_without_production() -> None:
    cap, profile, data = _farm()
    plans = compare_intervals(cap, profile, data, intervals=(1, 4))
    idle = [replace(p, busy_hours_per_hour=0.0) for p in plans]
    assert suggest_interval(idle).interval_hours == 1


def test_fields_without_level_limits() -> None:
    cap, profile, data = _farm()
    profile = replace(profile, fields_available=None)
    plan = plan_production(cap, profile, data, interval_hours=2)
    schedule = build_schedule(plan, [plan], cap, profile, data)
    assert "recommended" not in schedule["recommendations"]["fields"]
    assert "None" not in schedule_to_markdown(schedule, data)


def test_longer_interval_produces_less() -> None:
    cap, profile, data = _farm()
    short, long_ = compare_intervals(cap, profile, data, intervals=(0.5, 12))
    assert long_.busy_hours_per_hour < short.busy_hours_per_hour
    with pytest.raises(ValueError):
        plan_production(cap, profile, data, interval_hours=0)


def test_suggest_interval_keeps_efficiency() -> None:
    cap, profile, data = _farm()
    plans = compare_intervals(cap, profile, data)
    best = max(p.busy_hours_per_hour for p in plans)
    chosen = suggest_interval(plans, 0.8)
    assert chosen.busy_hours_per_hour >= 0.8 * best
    assert all(
        p.busy_hours_per_hour < 0.8 * best
        for p in plans
        if p.interval_hours > chosen.interval_hours
    )


def test_schedule_actions_and_recommendations() -> None:
    cap, profile, data = _farm()
    plans = compare_intervals(cap, profile, data, intervals=(1, 2))
    schedule = build_schedule(plans[0], plans, cap, profile, data)

    steps = schedule["actions_per_login"]
    kinds = [s["action"] for s in steps]
    assert kinds[0] == "collect" and kinds[-1] == "sell_or_deliver"
    assert kinds.index("feed") < kinds.index("plant") < kinds.index("queue")
    queued = [s["location_id"] for s in steps if s["action"] == "queue"]
    assert queued.index("feed_mill") < queued.index("bakery")  # upstream first
    assert [s["step"] for s in steps] == list(range(1, len(steps) + 1))

    rec = schedule["recommendations"]
    assert rec["fields"]["recommended"] == 12  # profile leaves fields open
    assert rec["trees_and_bushes"]["apple_tree"]["source"] == "recommended"
    assert schedule["external_per_day"]["iron_ore"] > 0
    json.dumps(schedule)

    md = schedule_to_markdown(schedule, data)
    assert "Log in every **1 h**" in md
    assert "**queue** Feed_Mill" in md


def test_rare_items_are_counted_per_logins() -> None:
    from src.planner.schedule import _count

    assert _count(3, 1) == {"per_login": 3, "per_day": 72, "count": 3}
    rare = _count(0.1, 2)
    assert rare["count"] == 1 and rare["every_n_logins"] == 5


def test_cli_writes_schedule(tmp_path: Path) -> None:
    if not Path("data/locations.json").exists():
        pytest.skip("no real data")
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": 20, "barn_capacity": 200}))
    out = tmp_path / "out"
    args = ["--player-config", str(player), "--output-dir", str(out)]

    settings = tmp_path / "planner.json"
    settings.write_text(json.dumps({"production": {"login_interval": 3}}))
    assert main([*args, "--planner-config", str(settings)]) == 0
    schedule = json.loads((out / "schedule.json").read_text(encoding="utf-8"))
    assert schedule["login_interval_hours"] == 3
    assert schedule["settings"]["login_interval"] == 3
    assert (out / "schedule.md").exists()
    settings.write_text(json.dumps({"production": {"storage_share": 0}}))
    assert main([*args, "--planner-config", str(settings)]) == 1


def test_cli_reports_unsolvable_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not Path("data/locations.json").exists():
        pytest.skip("no real data")

    def unsolvable(*args, **kwargs):
        raise RuntimeError("Production plan not solvable: test")

    monkeypatch.setattr("src.planner.run.compare_intervals", unsolvable)
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": 20}))
    args = ["--player-config", str(player), "--output-dir", str(tmp_path)]
    assert main(args) == 1
