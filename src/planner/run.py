"""
One Production Planner run: profile → capacity → plans → schedule.

Shared by ``python -m src.planner`` and the Combiner.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import PlayerConfig
from src.loaders.json_loader import DataSet

from .capacity import CapacityModel, build_capacity
from .mastery import mastery_modifier
from .profile import ResolvedProfile, resolve_profile
from .quantities import DEFAULT_STORAGE_SHARE, ProductionPlan, plan_production
from .schedule import (
    DEFAULT_MIN_EFFICIENCY,
    build_schedule,
    compare_intervals,
    suggest_interval,
)


@dataclass
class PlanRun:
    profile: ResolvedProfile
    capacity: CapacityModel
    plans: list[ProductionPlan]  # one per candidate interval
    chosen: ProductionPlan
    schedule: dict  # the schedule.json payload


def run_planner(
    player: PlayerConfig,
    dataset: DataSet,
    *,
    login_interval: float | None = None,
    storage_share: float = DEFAULT_STORAGE_SHARE,
    min_efficiency: float = DEFAULT_MIN_EFFICIENCY,
) -> PlanRun:
    """
    Plan production for the level-filtered *dataset*.

    Raises ``RuntimeError`` when the linear program cannot be solved.
    """
    profile = resolve_profile(player, dataset)
    capacity = build_capacity(
        profile, dataset, mastery_modifier(profile.mastery_system, dataset)
    )
    plans = compare_intervals(capacity, profile, dataset, storage_share=storage_share)
    if login_interval is None:
        chosen = suggest_interval(plans, min_efficiency)
    else:
        chosen = plan_production(
            capacity, profile, dataset, login_interval, storage_share
        )
    schedule = build_schedule(chosen, plans, capacity, profile, dataset)
    return PlanRun(profile, capacity, plans, chosen, schedule)
