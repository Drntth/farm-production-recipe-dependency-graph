"""
Weight calculation rules for the production dependency graph.

Design goals (Layout Planner)
-----------------------------
Higher edge weight ⇒ stronger coupling ⇒ the two nodes (or their
owning locations) should be placed closer together on the farm map.

Weight model (v0.1)
-------------------
1. PRODUCES edges (location → raw resource)
   weight = BASE_PRODUCES_WEIGHT  (default 1.0)
   These edges are the foundation of every chain; a constant keeps
   them visible without overpowering recipe-driven edges.

2. CONSUMES edges (resource → location)
   weight = input_amount / output_amount
   (= recipe ratio).  A recipe that needs 3 milk for 1 cheese
   creates a stronger pull than one that needs 1 milk for 1 cream.

3. OUTPUTS edges (location → output resource)
   weight = 1.0   (the production act itself)
   Combined with the consumes edges they form the full
   resource → location → resource hop that later stages can
   collapse into location-location proximity.

Multi-level propagation (future)
--------------------------------
Once the basic graph exists, a second pass can compute *effective*
weights between any pair of locations by summing (or taking the
maximum of) the weights of all simple paths that connect them.
That effective weight will feed the clustering and layout heuristics.
"""

from __future__ import annotations

BASE_PRODUCES_WEIGHT: float = 1.0
BASE_OUTPUTS_WEIGHT: float = 1.0


def produces_weight() -> float:
    """Weight for a source_location → resource edge."""
    return BASE_PRODUCES_WEIGHT


def consumes_weight(input_amount: int, output_amount: int) -> float:
    """
    Weight for a resource → location (recipe input) edge.

    Uses the recipe stoichiometry so that heavier consumers
    pull the upstream resource (and its producing location)
    more strongly toward the processing building.
    """
    if output_amount <= 0:
        raise ValueError("output_amount must be positive")
    return float(input_amount) / float(output_amount)


def outputs_weight() -> float:
    """Weight for a location → output_resource edge."""
    return BASE_OUTPUTS_WEIGHT


def recipe_ratio(input_amount: int, output_amount: int) -> float:
    """Convenience alias used when storing the ratio attribute."""
    return consumes_weight(input_amount, output_amount)
