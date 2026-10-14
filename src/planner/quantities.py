"""
Steady-state production quantities for one login interval.

A linear program (scipy / HiGHS) over rates per hour:

- ``x_r``: crafts of recipe *r* (machines, animal feeding, lobster / duck);
- ``p_c``: plantings of field crop *c*;
- ``n_k``: plants of tree / bush kind *k* whose count the profile leaves open;
- ``h_g``: goods *g* the beehives make (honeycomb);
- ``balance``: the surplus every produced good gets at least, per hour.

Constraints: no good is used faster than it is made; machine time (copies)
and queue (slots per login); animals, slots, fields and trees are served only
at a login, so one cycle takes the growth time rounded up to whole login
intervals; the goods made between two logins fit into the given share of the
barn and silo.

Four solves, each keeping the previous optimum (lexicographic):

1. maximise ``balance``: every good gets the same spare amount per hour;
2. minimise the use of external goods for that balance; this use becomes
   their limit, because their supply is not known;
3. maximise production time: idle machines and animals are filled;
4. minimise fields and recommended trees / bushes for that plan.

Some rates are estimates, listed in docs/wiki-gaps.md (tree / bush yield,
honeycomb). Goods without a production model (ores from the mine, fish) are
external: they are not planned, only their
use is reported. Recipes with non-good inputs (vouchers, diamonds) are skipped.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import linprog

from src.loaders.json_loader import DataSet
from src.models import LocationType, ResourceType
from src.settings import DEFAULT_STORAGE_SHARE  # rest of barn / silo: stock

from .capacity import SECONDS_PER_HOUR, CapacityModel, LineKind
from .profile import ResolvedProfile

CROP_HARVEST = 2  # crops harvested per planting (wiki: Crops)
_KEEP = 1 - 1e-6  # keep a previous optimum up to solver tolerance
_MAX_BALANCE = 1e6
_PLANNED_KINDS = {LineKind.MACHINE, LineKind.ANIMAL, LineKind.SLOT_ANIMAL}


@dataclass(frozen=True)
class RecipePlan:
    recipe_id: str
    location_id: str
    per_hour: float


@dataclass(frozen=True)
class CropPlan:
    resource_id: str
    plantings_per_hour: float
    fields: float  # fields this crop keeps busy


@dataclass(frozen=True)
class FruitPlan:
    resource_id: str
    location_id: str
    plants: float
    plants_source: str  # "profile" or "recommended"
    per_hour: float


@dataclass(frozen=True)
class ProductionPlan:
    interval_hours: float
    storage_share: float
    balance_per_hour: float
    busy_hours_per_hour: float  # production hours of machines and animals
    recipes: dict[str, RecipePlan]
    crops: dict[str, CropPlan]
    fruits: dict[str, FruitPlan]
    hive_per_hour: dict[str, float]
    surplus_per_hour: dict[str, float]
    external_per_hour: dict[str, float]
    utilization: dict[str, float]
    fields_used: float
    barn_per_login: float
    silo_per_login: float
    skipped_recipes: dict[str, str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def login_cycle_hours(seconds: int, interval_hours: float) -> float:
    """Hours one cycle takes when it can only restart at a login."""
    hours = seconds / SECONDS_PER_HOUR
    return max(1, math.ceil(hours / interval_hours - 1e-9)) * interval_hours


class _Program:
    """Variable index and constraint rows of the linear program."""

    def __init__(self) -> None:
        self.index: dict[tuple[str, str], int] = {}
        self.rows: list[dict[int, float]] = []
        self.bounds_b: list[float] = []

    def var(self, kind: str, key: str) -> int:
        return self.index.setdefault((kind, key), len(self.index))

    def add(self, coefs: dict[int, float], bound: float) -> None:
        """Add ``sum(coef * var) <= bound``."""
        self.rows.append(coefs)
        self.bounds_b.append(bound)

    def solve(self, objective: dict[int, float]):
        n = len(self.index)
        c = np.zeros(n)
        for i, v in objective.items():
            c[i] = v
        a = np.zeros((len(self.rows), n))
        for r, coefs in enumerate(self.rows):
            for i, v in coefs.items():
                a[r, i] += v
        bounds = [(0, None)] * n
        bounds[self.index[("balance", "")]] = (0, _MAX_BALANCE)
        result = linprog(
            c, A_ub=a, b_ub=np.array(self.bounds_b), bounds=bounds, method="highs"
        )
        if result.status != 0:
            raise RuntimeError(f"Production plan not solvable: {result.message}")
        return result


def plan_production(
    capacity: CapacityModel,
    profile: ResolvedProfile,
    dataset: DataSet,
    interval_hours: float,
    storage_share: float = DEFAULT_STORAGE_SHARE,
) -> ProductionPlan:
    """Solve the production plan for logins every *interval_hours*."""
    if interval_hours <= 0 or not 0 < storage_share <= 1:
        raise ValueError("interval_hours must be > 0 and storage_share in (0, 1]")
    t = interval_hours

    # --- sources of every good ------------------------------------------
    fields = capacity.fields or 0
    crop_ok = {c for c in capacity.crops if fields > 0}
    fruit_fixed: dict[str, float] = {}  # resource -> plants owned
    fruit_free: set[str] = set()  # resource -> count to recommend
    for res_id, fruit in capacity.fruits.items():
        if fruit.yield_per_harvest is None:
            continue
        owned = profile.locations[fruit.location_id].owned
        if owned is None:
            fruit_free.add(res_id)
        elif owned > 0:
            fruit_fixed[res_id] = owned
    hive_ok = {g for g, h in capacity.hives.items() if h.parallel}
    modelled_raw = crop_ok | fruit_free | set(fruit_fixed) | hive_ok

    skipped: dict[str, str] = {}
    candidates = []
    for rate in capacity.recipes.values():
        rec = dataset.recipes[rate.recipe_id]
        cap = capacity.locations.get(rec.location_id)
        outside = [
            i.resource_id for i in rec.inputs if i.resource_id not in dataset.resources
        ]
        if outside:
            skipped[rec.id] = "external input: " + ", ".join(outside)
        elif cap is None or cap.kind not in _PLANNED_KINDS:
            skipped[rec.id] = "no production model for this location"
        elif not cap.parallel:
            skipped[rec.id] = "location not available"
        elif not rate.time_seconds:
            skipped[rec.id] = "no production time"
        else:
            candidates.append(rec)

    def has_model(res_id: str) -> bool:
        """The plan could make it (crop, fruit with data, hive or any recipe)."""
        if res_id in capacity.hives:
            return True
        res = dataset.resources[res_id]
        src = dataset.locations.get(res.source_location_id or "")
        if res.type == ResourceType.CROP and src is not None:
            if src.type == LocationType.FIELD:
                return True
            return src.lifetime_yield is not None
        return any(r.output.resource_id == res_id for r in candidates)

    # drop recipes whose inputs cannot be made (e.g. a tree kind owned 0 times)
    available = set(modelled_raw)
    planned = []
    changed = True
    while changed:
        changed = False
        available = set(modelled_raw) | {r.output.resource_id for r in planned}
        for rec in candidates:
            if rec in planned or rec.id in skipped:
                continue
            missing = [
                i.resource_id
                for i in rec.inputs
                if has_model(i.resource_id) and i.resource_id not in available
            ]
            if not missing:
                planned.append(rec)
                changed = True
    for rec in candidates:
        if rec not in planned:
            missing = sorted(
                i.resource_id
                for i in rec.inputs
                if has_model(i.resource_id) and i.resource_id not in available
            )
            skipped.setdefault(rec.id, "input not available: " + ", ".join(missing))
    planned.sort(key=lambda r: r.id)
    produced = set(modelled_raw) | {r.output.resource_id for r in planned}

    # --- linear program ---------------------------------------------------
    lp = _Program()
    bal = lp.var("balance", "")
    xs = {rec.id: lp.var("x", rec.id) for rec in planned}
    ps = {c: lp.var("p", c) for c in sorted(crop_ok)}
    ns = {k: lp.var("n", k) for k in sorted(fruit_free)}
    hs = {g: lp.var("h", g) for g in sorted(hive_ok)}
    times = {rec.id: capacity.recipes[rec.id].time_seconds for rec in planned}

    def fruit_rate(res_id: str) -> float:
        fruit = capacity.fruits[res_id]
        return fruit.yield_per_harvest / login_cycle_hours(
            fruit.harvest_interval_seconds, t
        )

    # balance: made - used >= balance, for every produced good
    supply: dict[str, dict[int, float]] = {g: {} for g in produced}
    constant: dict[str, float] = dict.fromkeys(produced, 0.0)
    used: dict[str, dict[int, float]] = {}
    for rec in planned:
        out = supply[rec.output.resource_id]
        out[xs[rec.id]] = out.get(xs[rec.id], 0) + rec.output.amount
        for inp in rec.inputs:
            row = used.setdefault(inp.resource_id, {})
            row[xs[rec.id]] = row.get(xs[rec.id], 0) + inp.amount
    for c, i in ps.items():
        supply[c][i] = CROP_HARVEST - 1  # one crop goes back into the field
    for k, i in ns.items():
        supply[k][i] = fruit_rate(k)
    for k, owned in fruit_fixed.items():
        constant[k] = owned * fruit_rate(k)
    for g, i in hs.items():
        supply[g][i] = 1
    for g in sorted(produced):
        row = {i: -v for i, v in supply[g].items()}
        for i, v in used.get(g, {}).items():
            row[i] = row.get(i, 0) + v
        row[bal] = 1
        lp.add(row, constant[g])

    # machines: time of all copies, and the queue refilled once per login
    by_location: dict[str, list] = {}
    for rec in planned:
        by_location.setdefault(rec.location_id, []).append(rec)
    for loc_id, recs in by_location.items():
        cap = capacity.locations[loc_id]
        if cap.kind == LineKind.MACHINE:
            lp.add(
                {xs[r.id]: times[r.id] / SECONDS_PER_HOUR for r in recs}, cap.parallel
            )
            if cap.queue:
                lp.add({xs[r.id]: 1 for r in recs}, cap.queue / t)
        else:  # animals / slots: busy until the next login after the cycle
            lp.add(
                {xs[r.id]: login_cycle_hours(times[r.id], t) for r in recs},
                cap.parallel,
            )

    # beehives: one good per cycle each, collected at a login
    for g, i in hs.items():
        hive = capacity.hives[g]
        lp.add({i: login_cycle_hours(hive.cycle_seconds, t)}, hive.parallel)

    # fields busy until the next login after growth
    crop_cycle = {
        c: login_cycle_hours(capacity.crops[c].growth_time_seconds, t) for c in ps
    }
    if ps:
        lp.add({i: crop_cycle[c] for c, i in ps.items()}, fields)

    # storage: goods made between two logins fit into the share; the fruit of
    # owned trees comes anyway, so it only shrinks the room left for crops
    warnings: list[str] = []
    if capacity.silo_capacity is not None:
        silo_row = {i: CROP_HARVEST * t for i in ps.values()}
        silo_row.update({i: fruit_rate(k) * t for k, i in ns.items()})
        room = storage_share * capacity.silo_capacity
        fixed = sum(constant[k] for k in fruit_fixed) * t
        if fixed > room:
            warnings.append(
                f"the owned trees and bushes alone fill {fixed:.0f} silo places per "
                f"login, more than the {room:.0f} planned for production"
            )
        lp.add(silo_row, max(room - fixed, 0.0))
    if capacity.barn_capacity is not None and (xs or hs):
        barn_row = {xs[r.id]: r.output.amount * t for r in planned}
        barn_row.update(dict.fromkeys(hs.values(), t))
        lp.add(barn_row, storage_share * capacity.barn_capacity)

    busy = {xs[r.id]: times[r.id] / SECONDS_PER_HOUR for r in planned}
    best = lp.solve({bal: -1})
    lp.add({bal: -1}, -best.x[bal] * _KEEP)
    outside = {g: row for g, row in used.items() if g not in produced}
    if outside:
        total: dict[int, float] = {}
        for row in outside.values():
            for i, v in row.items():
                total[i] = total.get(i, 0) + v
        lean = lp.solve(total)
        for row in outside.values():
            limit = sum(lean.x[i] * v for i, v in row.items())
            lp.add(row, limit / _KEEP + 1e-9)
    filled = lp.solve({i: -v for i, v in busy.items()})
    lp.add({i: -v for i, v in busy.items()}, filled.fun * _KEEP)
    land = {i: crop_cycle[c] for c, i in ps.items()}
    land.update(dict.fromkeys(ns.values(), 1.0))
    final = lp.solve(land) if land else filled
    x = final.x

    # --- results ------------------------------------------------------------
    def clean(v: float) -> float:
        return 0.0 if abs(v) < 1e-9 else float(v)

    recipes = {
        rec.id: RecipePlan(rec.id, rec.location_id, clean(x[xs[rec.id]]))
        for rec in planned
    }
    crops = {
        c: CropPlan(c, clean(x[i]), clean(x[i] * crop_cycle[c])) for c, i in ps.items()
    }
    fruits = {}
    for k in sorted(fruit_free | set(fruit_fixed)):
        fruit = capacity.fruits[k]
        plants = clean(x[ns[k]]) if k in ns else fruit_fixed[k]
        fruits[k] = FruitPlan(
            k,
            fruit.location_id,
            plants,
            "recommended" if k in ns else "profile",
            plants * fruit_rate(k),
        )

    made: dict[str, float] = dict.fromkeys(produced, 0.0)
    use: dict[str, float] = {}
    for rec in planned:
        rate = recipes[rec.id].per_hour
        made[rec.output.resource_id] += rate * rec.output.amount
        for inp in rec.inputs:
            use[inp.resource_id] = use.get(inp.resource_id, 0) + rate * inp.amount
    for c, plan in crops.items():
        made[c] += plan.plantings_per_hour * (CROP_HARVEST - 1)
    for k, plan in fruits.items():
        made[k] += plan.per_hour
    hive = {g: clean(x[i]) for g, i in hs.items()}
    for g, rate in hive.items():
        made[g] += rate
    surplus = {g: clean(made[g] - use.get(g, 0)) for g in sorted(produced)}
    external = {
        g: clean(v) for g, v in sorted(use.items()) if g not in produced and v > 1e-9
    }

    utilization = {}
    for loc_id, recs in sorted(by_location.items()):
        cap = capacity.locations[loc_id]
        if cap.kind == LineKind.MACHINE:
            load = sum(recipes[r.id].per_hour * times[r.id] for r in recs)
            utilization[loc_id] = clean(load / SECONDS_PER_HOUR / cap.parallel)
        else:
            load = sum(
                recipes[r.id].per_hour * login_cycle_hours(times[r.id], t) for r in recs
            )
            utilization[loc_id] = clean(load / cap.parallel)

    return ProductionPlan(
        interval_hours=t,
        storage_share=storage_share,
        balance_per_hour=clean(x[bal]),
        busy_hours_per_hour=clean(sum(x[i] * v for i, v in busy.items())),
        recipes=recipes,
        crops=crops,
        fruits=fruits,
        hive_per_hour=hive,
        surplus_per_hour=surplus,
        external_per_hour=external,
        utilization=utilization,
        fields_used=clean(sum(c.fields for c in crops.values())),
        barn_per_login=clean(
            (
                sum(recipes[r.id].per_hour * r.output.amount for r in planned)
                + sum(hive.values())
            )
            * t
        ),
        silo_per_login=clean(
            (
                sum(c.plantings_per_hour * CROP_HARVEST for c in crops.values())
                + sum(f.per_hour for f in fruits.values())
            )
            * t
        ),
        skipped_recipes=dict(sorted(skipped.items())),
        warnings=warnings,
    )
