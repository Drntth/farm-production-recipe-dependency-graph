"""
Edge types and relationship helpers for the production dependency graph.

The graph is a directed weighted MultiDiGraph (NetworkX) whose edges
carry rich attributes so that later stages (clustering, layout heuristics,
exporters) can reason about *why* two nodes are connected.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class EdgeType(str, Enum):
    """Semantic category of a dependency edge."""

    PRODUCES = "produces"
    """Location produces a raw resource (source_location → resource)."""

    CONSUMES = "consumes"
    """Resource is an input to a recipe at a location (resource → location)."""

    OUTPUTS = "outputs"
    """Location produces the output of a recipe (location → resource)."""


ATTR_EDGE_TYPE = "edge_type"
ATTR_WEIGHT = "weight"
ATTR_AMOUNT = "amount"
ATTR_RECIPE_ID = "recipe_id"
ATTR_RATIO = "ratio"


def edge_attrs(
    edge_type: EdgeType,
    weight: float,
    *,
    amount: int = 1,
    recipe_id: str | None = None,
    ratio: float | None = None,
) -> dict[str, Any]:
    """Build a consistent attribute dictionary for a NetworkX edge."""
    attrs: dict[str, Any] = {
        ATTR_EDGE_TYPE: edge_type.value,
        ATTR_WEIGHT: float(weight),
        ATTR_AMOUNT: int(amount),
    }
    if recipe_id is not None:
        attrs[ATTR_RECIPE_ID] = recipe_id
    if ratio is not None:
        attrs[ATTR_RATIO] = float(ratio)
    return attrs
