"""
One Production Planner run: profile → capacity → plans → schedule.

Shared by ``python -m src.planner`` and the Combiner.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import PlayerConfig
from src.loaders.json_loader import DataSet
from src.settings import LoginWindow

from .capacity import CapacityModel, build_capacity
from .mastery import mastery_modifier
from .profile import ResolvedProfile, resolve_profile
from .quantities import DEFAULT_STORAGE_SHARE, ProductionPlan
from .schedule import (
    DEFAULT_MIN_EFFICIENCY,
    LOGIN_CANDIDATES,
    build_schedule,
    compare_logins,
    suggest_logins,
)


@dataclass
class PlanRun:
    profile: ResolvedProfile
    capacity: CapacityModel
    plans: list[ProductionPlan]  # one per candidate number of logins
    chosen: ProductionPlan
    schedule: dict  # the schedule.json payload


def run_planner(
    player: PlayerConfig,
    dataset: DataSet,
    *,
    login_window: LoginWindow | None = None,
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
    window = login_window or LoginWindow()
    counts = LOGIN_CANDIDATES
    if window.logins is not None:
        counts = (*counts, window.logins)
    plans = compare_logins(
        capacity, profile, dataset, window, counts, storage_share=storage_share
    )
    if window.logins is None:
        chosen = suggest_logins(plans, min_efficiency)
    else:
        chosen = next(p for p in plans if p.logins == window.logins)
    schedule = build_schedule(
        chosen, plans, capacity, profile, dataset, window, window.logins is None
    )
    return PlanRun(profile, capacity, plans, chosen, schedule)
