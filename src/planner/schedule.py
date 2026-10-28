"""
Login interval suggestion, recommendations and the ordered action list.

- Interval: the plan is solved for every candidate interval; the suggestion
  is the longest one that keeps ``min_efficiency`` of the best production
  time (fewer logins, little lost output).
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
from src.settings import DEFAULT_MIN_EFFICIENCY

from .capacity import FEEDER_BUSHES, CapacityModel, LineKind
from .profile import ResolvedProfile
from .quantities import DEFAULT_STORAGE_SHARE, ProductionPlan, plan_production

INTERVAL_CANDIDATES = (0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
HOURS_PER_DAY = 24
_TOP_SURPLUS = 15


def compare_intervals(
    capacity: CapacityModel,
    profile: ResolvedProfile,
    dataset: DataSet,
    intervals: tuple[float, ...] = INTERVAL_CANDIDATES,
    storage_share: float = DEFAULT_STORAGE_SHARE,
) -> list[ProductionPlan]:
    return [
        plan_production(capacity, profile, dataset, t, storage_share)
        for t in sorted(intervals)
    ]


def suggest_interval(
    plans: list[ProductionPlan], min_efficiency: float = DEFAULT_MIN_EFFICIENCY
) -> ProductionPlan:
    """
    Longest interval whose production time is within *min_efficiency* of the
    best; the shortest one when nothing can be produced at all.
    """
    best = max(p.busy_hours_per_hour for p in plans)
    if best <= 0:
        return min(plans, key=lambda p: p.interval_hours)
    good = [p for p in plans if p.busy_hours_per_hour >= min_efficiency * best]
    return max(good, key=lambda p: p.interval_hours)


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


def actions(plan: ProductionPlan, dataset: DataSet, capacity: CapacityModel) -> list:
    t = plan.interval_hours
    goods = ["animal goods", *(g for g in FEEDER_BUSHES if g in capacity.hives)]
    steps: list[dict] = [
        {
            "action": "collect",
            "what": "harvest ready fields, trees and bushes; collect "
            f"{', '.join(goods)} and finished machine goods",
        }
    ]
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
) -> dict:
    """The schedule.json payload."""
    return {
        "level": capacity.level,
        "login_interval_hours": chosen.interval_hours,
        "logins_per_day": round(HOURS_PER_DAY / chosen.interval_hours, 1),
        "storage": {
            "share_for_production": chosen.storage_share,
            "barn_capacity": capacity.barn_capacity,
            "barn_per_login": round(chosen.barn_per_login, 1),
            "silo_capacity": capacity.silo_capacity,
            "silo_per_login": round(chosen.silo_per_login, 1),
        },
        "intervals": [
            {
                "hours": p.interval_hours,
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

    lines = [
        f"# Production schedule (level {schedule['level']})",
        "",
        (
            f"Log in every **{schedule['login_interval_hours']:g} h** "
            f"({schedule['logins_per_day']:g} logins per day).  "
        ),
        (
            f"Per login: about {s['barn_per_login']:g} goods into the barn "
            f"(capacity {cap('barn_capacity')}), {s['silo_per_login']:g} into the "
            f"silo (capacity {cap('silo_capacity')}); "
            f"{s['share_for_production']:.0%} of each is planned for production."
        ),
        "",
        "## Login intervals",
        "",
        "| Interval (h) | Production hours per hour | Spare per good and day |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {i['hours']:g} | {i['production_hours_per_hour']:g} "
        f"| {i['balance_per_day']:g} |"
        for i in schedule["intervals"]
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
