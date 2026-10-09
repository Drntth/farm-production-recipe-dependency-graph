"""
Support relations - placement links that the production graph does not show.

A support relation pulls a *source* location toward a *target* location even
though no resource flows between them. The nectar bush is the first case: it
produces no goods, but bees fly to it from the beehive tree, and the farther
the bush, the slower the bees (wiki: Nectar_Bush, docs/game-facts/animals.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportRelation:
    source: str
    target: str
    reason: str
    weight: float = 10.0  # same scale as graph coupling weights


SUPPORT_RELATIONS: tuple[SupportRelation, ...] = (
    SupportRelation(
        source="nectar_bush",
        target="beehive_tree",
        reason="bees fly slower to distant nectar bushes (wiki: Nectar_Bush)",
    ),
)


def active_relations(location_ids: set[str]) -> list[SupportRelation]:
    """Relations whose two ends are both present (e.g. unlocked at the level)."""
    return [
        r
        for r in SUPPORT_RELATIONS
        if r.source in location_ids and r.target in location_ids
    ]
