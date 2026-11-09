"""
Login suggestion, recommendations and the ordered action list.

- Logins: the plan is solved for every candidate number of logins spread over
  the login window; the suggestion is the fewest logins that keep
  ``min_efficiency`` of the best production time with at most
  ``MAX_SUGGESTED_LOGINS`` logins (more logins always produce more). The schedule gives the
  login times and the long items worth starting at the last login of the day
  (they run through the night gap).
- Recommendations: fields (all granted fields if the profile has no count,
  plus how many the plan uses), trees and bushes the profile leaves open, and
  nectar bushes for the honeycomb (5 per bush) and peanut bushes for the
  peanuts (2,000 pods / 300 per peanut) the plan makes (wiki).
- Actions per login, in order: collect, feed animals, plant fields, fill the
  machine queues upstream first (a machine whose goods feed another comes
  earlier), then sell or deliver the surplus.
"""

from __future__ import annotations

import math

import networkx as nx

from src.loaders.json_loader import DataSet
from src.settings import DEFAULT_MIN_EFFICIENCY, LoginWindow

from .capacity import FEEDER_BUSHES, CapacityModel, LineKind
from .profile import ResolvedProfile
from .quantities import DEFAULT_STORAGE_SHARE, ProductionPlan, plan_production

LOGIN_CANDIDATES = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 24)
# busy hours grow almost linearly with logins, so the efficiency rule alone
# would always suggest the most; the suggestion stays at "a few logins a day"
MAX_SUGGESTED_LOGINS = 8
HOURS_PER_DAY = 24
_TOP_SURPLUS = 15
_TOP_LAST_LOGIN = 10


def compare_logins(
    capacity: CapacityModel,
    profile: ResolvedProfile,
    dataset: DataSet,
    window: LoginWindow | None = None,
    counts: tuple[int, ...] = LOGIN_CANDIDATES,
    storage_share: float = DEFAULT_STORAGE_SHARE,
) -> list[ProductionPlan]:
    """One plan per number of logins in *counts*, spread over *window*."""
    window = window or LoginWindow()
    return [
        plan_production(capacity, profile, dataset, window.gaps(n), storage_share)
        for n in sorted(set(counts))
    ]


def suggest_logins(
    plans: list[ProductionPlan], min_efficiency: float = DEFAULT_MIN_EFFICIENCY
) -> ProductionPlan:
    """
    Fewest logins whose production time is within *min_efficiency* of the
    best plan with at most ``MAX_SUGGESTED_LOGINS`` logins; the fewest of all
    when nothing can be produced.
    """
    few = [p for p in plans if p.logins <= MAX_SUGGESTED_LOGINS] or plans
    best = max(p.busy_hours_per_hour for p in few)
    good = [p for p in few if p.busy_hours_per_hour >= min_efficiency * best]
    return min(good or few, key=lambda p: p.logins)


def last_login_items(plan: ProductionPlan, capacity: CapacityModel) -> list[dict]:
    """
    Planned recipes and crops that take longer than a day gap: started at the
    last login of the day they finish in the night gap instead of waiting.
    Empty when the logins are even (no night gap).
    """
    day, night = min(plan.login_gaps), max(plan.login_gaps)
    if night - day < 1e-9:
        return []
    items: list[dict] = []
    for rp in plan.recipes.values():
        seconds = capacity.recipes[rp.recipe_id].time_seconds
        if rp.per_hour > 1e-9 and seconds and seconds / 3600 > day + 1e-9:
            items.append(
                {
                    "recipe_id": rp.recipe_id,
                    "location_id": rp.location_id,
                    "hours": round(seconds / 3600, 2),
                }
            )
    for crop in plan.crops.values():
        seconds = capacity.crops[crop.resource_id].growth_time_seconds
        if crop.plantings_per_hour > 1e-9 and seconds / 3600 > day + 1e-9:
            items.append(
                {"resource_id": crop.resource_id, "hours": round(seconds / 3600, 2)}
            )
    items.sort(key=lambda i: (-i["hours"], i.get("recipe_id") or i["resource_id"]))
    return items[:_TOP_LAST_LOGIN]


def machine_order(plan: ProductionPlan, dataset: DataSet) -> list[str]:
    """Locations of the plan, producers of an input before its consumers."""
    graph = nx.DiGraph()
    makers: dict[str, set[str]] = {}
    for rp in plan.recipes.values():
        graph.add_node(rp.location_id)
        makers.setdefault(dataset.recipes[rp.recipe_id].output.resource_id, set()).add(
            rp.location_id
        )
    for rp in plan.recipes.values():
        for inp in dataset.recipes[rp.recipe_id].inputs:
            for src in makers.get(inp.resource_id, ()):
                if src != rp.location_id:
                    graph.add_edge(src, rp.location_id)
    dag = nx.condensation(graph)  # cycles (rare) become one step
    order: list[str] = []
    for generation in nx.topological_generations(dag):
        members = sorted(loc for n in generation for loc in dag.nodes[n]["members"])
        order.extend(members)
    return order


def _count(per_hour: float, interval: float) -> dict:
    """Items per login: rounded count, or one every N logins for rare items."""
    per_login = per_hour * interval
    item: dict = {"per_login": round(per_login, 2), "per_day": round(per_hour * 24, 2)}
    if per_login >= 0.5:
        item["count"] = round(per_login)
    else:
        item["count"] = 1
        item["every_n_logins"] = math.ceil(1 / per_login)
    return item


def recommendations(
    plan: ProductionPlan, profile: ResolvedProfile, capacity: CapacityModel
) -> dict:
    fields = {
        "available": profile.fields_available,
        "owned": profile.fields_owned,
        "used_by_plan": math.ceil(plan.fields_used - 1e-6),
    }
    if profile.fields_owned is None and profile.fields_available is not None:
        fields["recommended"] = profile.fields_available
        fields["note"] = "own every granted field: they cost 1 coin each (wiki)"
    plants = {
        fp.location_id: {
            "resource_id": fp.resource_id,
            "plants": math.ceil(fp.plants - 1e-6)
            if fp.plants_source == "recommended"
            else fp.plants,
            "source": fp.plants_source,
        }
        for fp in plan.fruits.values()
    }
    no_data = sorted(
        f.location_id for f in capacity.fruits.values() if f.yield_per_harvest is None
    )
    result = {"fields": fields, "trees_and_bushes": plants}
    if no_data:
        result["no_yield_data"] = no_data
    for good, (bush, per_bush) in FEEDER_BUSHES.items():
        rate = plan.hive_per_hour.get(good) or plan.external_per_hour.get(good)
        if rate:
            result[bush] = {
                "resource_id": good,
                f"{good}_per_day": round(rate * HOURS_PER_DAY, 2),
                "bushes_per_day": round(rate * HOURS_PER_DAY / per_bush, 2),
            }
    return result


# every "action" of actions(); the site translates them (web/content/*.json)
ACTIONS = ("collect", "feed", "plant", "queue", "sell_or_deliver")


def collect_what(feeder_goods: list[str]) -> str:
    """The "what" of the collect step; `feeder_goods` in FEEDER_BUSHES order."""
    goods = ["animal goods", *feeder_goods]
    return (
        "harvest ready fields, trees and bushes; collect "
        f"{', '.join(goods)} and finished machine goods"
    )


def actions(plan: ProductionPlan, dataset: DataSet, capacity: CapacityModel) -> list:
    """
    The ordered steps of one login. Counts use the mean gap (24 h / logins):
    with a night gap a login by day needs fewer, the last login of the day more.
    """
    t = HOURS_PER_DAY / plan.logins  # mean login gap
    feeder = [g for g in FEEDER_BUSHES if g in capacity.hives]
    steps: list[dict] = [{"action": "collect", "what": collect_what(feeder)}]
    animal_kinds = {LineKind.ANIMAL, LineKind.SLOT_ANIMAL}
    order = machine_order(plan, dataset)
    for loc_id in order:
        if capacity.locations[loc_id].kind not in animal_kinds:
            continue
        items = [
            {"recipe_id": rp.recipe_id, **_count(rp.per_hour, t)}
            for rp in plan.recipes.values()
            if rp.location_id == loc_id and rp.per_hour > 1e-9
        ]
        if items:
            steps.append({"action": "feed", "location_id": loc_id, "items": items})
    planted = [
        {"resource_id": c.resource_id, "fields": round(c.fields, 1)}
        | _count(c.plantings_per_hour, t)
        for c in sorted(plan.crops.values(), key=lambda c: -c.fields)
        if c.plantings_per_hour > 1e-9
    ]
    if planted:
        steps.append({"action": "plant", "items": planted})
    for loc_id in order:
        if capacity.locations[loc_id].kind != LineKind.MACHINE:
            continue
        items = [
            {"recipe_id": rp.recipe_id, **_count(rp.per_hour, t)}
            for rp in sorted(plan.recipes.values(), key=lambda r: -r.per_hour)
            if rp.location_id == loc_id and rp.per_hour > 1e-9
        ]
        if items:
            steps.append(
                {
                    "action": "queue",
                    "location_id": loc_id,
                    "slots": capacity.locations[loc_id].queue,
                    "items": items,
                }
            )
    surplus = sorted(
        ((v, g) for g, v in plan.surplus_per_hour.items() if v > 1e-9), reverse=True
    )
    steps.append(
        {
            "action": "sell_or_deliver",
            "items": [
                {"resource_id": g, **_count(v, t)} for v, g in surplus[:_TOP_SURPLUS]
            ],
        }
    )
    for n, step in enumerate(steps, start=1):
        step["step"] = n
    return steps


def build_schedule(
    chosen: ProductionPlan,
    plans: list[ProductionPlan],
    capacity: CapacityModel,
    profile: ResolvedProfile,
    dataset: DataSet,
    window: LoginWindow | None = None,
    suggested: bool = True,
) -> dict:
    """The schedule.json payload."""
    window = window or LoginWindow()
    times = window.times(chosen.logins)
    last = last_login_items(chosen, capacity)
    return {
        "level": capacity.level,
        "logins_per_day": chosen.logins,
        "logins_suggested": suggested,
        "login_times": times,
        "day_gap_hours": round(min(chosen.login_gaps), 2),
        "night_gap_hours": round(max(chosen.login_gaps), 2),
        "last_login": {"time": times[-1], "items": last} if last else None,
        "storage": {
            "share_for_production": chosen.storage_share,
            "barn_capacity": capacity.barn_capacity,
            "barn_per_login": round(chosen.barn_per_login, 1),
            "silo_capacity": capacity.silo_capacity,
            "silo_per_login": round(chosen.silo_per_login, 1),
        },
        "login_options": [
            {
                "logins": p.logins,
                "longest_gap_hours": round(max(p.login_gaps), 2),
                "production_hours_per_hour": round(p.busy_hours_per_hour, 2),
                "balance_per_day": round(p.balance_per_hour * HOURS_PER_DAY, 2),
            }
            for p in plans
        ],
        "recommendations": recommendations(chosen, profile, capacity),
        "actions_per_login": actions(chosen, dataset, capacity),
        "external_per_day": {
            g: round(v * HOURS_PER_DAY, 2) for g, v in chosen.external_per_hour.items()
        },
        "warnings": chosen.warnings,
        "plan": chosen.to_dict(),
    }


def schedule_to_markdown(schedule: dict, dataset: DataSet) -> str:
    """Human-readable schedule.md."""

    def name(res_or_recipe: str) -> str:
        if res_or_recipe in dataset.recipes:
            return dataset.recipes[res_or_recipe].name
        if res_or_recipe in dataset.resources:
            return dataset.resources[res_or_recipe].name
        loc = dataset.locations.get(res_or_recipe)
        # a feeder bush may be missing from a trimmed data set
        return loc.name if loc is not None else res_or_recipe.replace("_", " ")

    def fmt(item: dict) -> str:
        key = item.get("recipe_id") or item["resource_id"]
        if "every_n_logins" in item:
            return f"{name(key)} 1 every {item['every_n_logins']} logins"
        return f"{name(key)} {item['count']}"

    s = schedule["storage"]

    def cap(key: str) -> str:
        return "not set" if s[key] is None else str(s[key])

    n = schedule["logins_per_day"]
    gaps = (
        f"{schedule['day_gap_hours']:g} h apart"
        if schedule["day_gap_hours"] == schedule["night_gap_hours"]
        else f"{schedule['day_gap_hours']:g} h apart by day, "
        f"{schedule['night_gap_hours']:g} h at night"
    )
    lines = [
        f"# Production schedule (level {schedule['level']})",
        "",
        (
            f"Log in **{n} times a day** "
            f"({'suggested' if schedule['logins_suggested'] else 'set'}): "
            f"{', '.join(schedule['login_times'])}; {gaps}.  "
        ),
        (
            f"Per login: about {s['barn_per_login']:g} goods into the barn "
            f"(capacity {cap('barn_capacity')}), {s['silo_per_login']:g} into the "
            f"silo (capacity {cap('silo_capacity')}); "
            f"{s['share_for_production']:.0%} of each is planned for production."
        ),
        "",
        "## Logins per day",
        "",
        (
            "| Logins | Longest gap (h) | Production hours per hour "
            "| Spare per good and day |"
        ),
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {i['logins']} | {i['longest_gap_hours']:g} "
        f"| {i['production_hours_per_hour']:g} | {i['balance_per_day']:g} |"
        for i in schedule["login_options"]
    ]
    if schedule["warnings"]:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in schedule["warnings"]]
    rec = schedule["recommendations"]
    f = rec["fields"]
    lines += ["", "## Recommendations", ""]
    if "recommended" in f:
        lines.append(f"- Fields: own all {f['recommended']} ({f['note']}).")
    of = f" of {f['available']}" if f["available"] is not None else ""
    lines.append(f"- Fields used by the plan: {f['used_by_plan']}{of}.")
    for loc_id, plant in rec["trees_and_bushes"].items():
        lines.append(f"- {name(loc_id)}: {plant['plants']} ({plant['source']}).")
    if rec.get("no_yield_data"):
        lines.append(
            "- No yield data yet (fruit treated as external): "
            + ", ".join(name(i) for i in rec["no_yield_data"])
            + "."
        )
    for good, (bush, _) in FEEDER_BUSHES.items():
        if bush in rec:
            fb = rec[bush]
            lines.append(
                f"- {name(bush)}: about {fb['bushes_per_day']:g} new per day "
                f"for {fb[f'{good}_per_day']:g} {name(good).lower()}."
            )
    lines += ["", "## Every login", ""]
    for step in schedule["actions_per_login"]:
        where = f" {name(step['location_id'])}" if "location_id" in step else ""
        head = f"{step['step']}. **{step['action'].replace('_', ' ')}**{where}"
        if "items" in step:
            lines.append(f"{head}: " + ", ".join(fmt(i) for i in step["items"]))
        else:
            lines.append(f"{head}: {step['what']}")
    if schedule["last_login"]:
        last = schedule["last_login"]
        lines += [
            "",
            f"## Last login ({last['time']})",
            "",
            "Start the long ones before the night: "
            + ", ".join(
                f"{name(i.get('recipe_id') or i['resource_id'])} {i['hours']:g} h"
                for i in last["items"]
            )
            + ".",
        ]
    if schedule["external_per_day"]:
        lines += [
            "",
            "## Needed from outside the plan (per day)",
            "",
            ", ".join(
                f"{name(g)} {v:g}" for g, v in schedule["external_per_day"].items()
            ),
        ]
    return "\n".join(lines) + "\n"
