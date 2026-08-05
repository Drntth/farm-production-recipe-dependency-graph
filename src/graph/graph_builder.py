"""
Build a directed weighted dependency graph from a validated DataSet.

Node model
----------
Every Location and every Resource becomes a node.
Node identifiers keep the original snake_case ids; collisions are
impossible because the loader already guarantees unique ids inside
each entity type and the two namespaces do not overlap in practice.
(If a future data set ever collides, the builder raises.)

Node attributes (always present)
--------------------------------
- kind          : "location" | "resource"
- id            : original entity id
- name          : human-readable name
- unlock_level  : int
- type          : LocationType / ResourceType value (str)

Additional attributes for locations: max_slots (optional)
Additional attributes for resources: source_location_id (optional)

Edge model
----------
Three edge kinds (see relationship.EdgeType):

1. PRODUCES  location  → resource
   Created for raw resources only (crop, animal_product, ore) that have a
   source_location_id. Processed goods are linked via OUTPUTS from recipes
   so the two edge kinds do not collide / merge.

2. CONSUMES  resource  → location
   Created for every recipe input.
   Captures “this resource is consumed at this production building”.

3. OUTPUTS   location  → resource
   Created for every recipe output.
   Captures “this building produces this (processed) good”.

Together they form continuous dependency paths, e.g.:

    field ─PRODUCES→ soybean ─CONSUMES→ feed_mill ─OUTPUTS→ cow_feed
         ─CONSUMES→ cow_pasture ─OUTPUTS→ milk ─CONSUMES→ dairy
         ─OUTPUTS→ cream …

External recipe inputs (vouchers, premium items …) that are absent
from resources.json are silently skipped; they never become nodes.

The returned object is a networkx.DiGraph with a single edge between
any ordered pair of nodes (if multiple recipes would create the same
edge, weights are summed and the recipe_ids are collected).
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from src.loaders.json_loader import DataSet
from src.models.resource import ResourceType

from .relationship import (
    ATTR_AMOUNT,
    ATTR_EDGE_TYPE,
    ATTR_RECIPE_ID,
    ATTR_WEIGHT,
    EdgeType,
    edge_attrs,
)
from .weighting import consumes_weight, outputs_weight, produces_weight, recipe_ratio

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_graph(dataset: DataSet) -> nx.DiGraph:
    """
    Construct the production dependency graph from a validated DataSet.

    Parameters
    ----------
    dataset:
        Already-validated collection of locations, resources and recipes
        (optionally filtered by max_level).

    Returns
    -------
    networkx.DiGraph
        Directed weighted graph ready for analysis and export.
    """
    G = nx.DiGraph()

    _add_location_nodes(G, dataset)
    _add_resource_nodes(G, dataset)
    _add_produces_edges(G, dataset)
    _add_recipe_edges(G, dataset)

    logger.info(
        "Graph built: %d nodes, %d edges",
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    return G


def graph_summary(G: nx.DiGraph) -> str:
    """Human-readable one-line summary."""
    loc = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "location")
    res = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "resource")
    return (
        f"DiGraph(nodes={G.number_of_nodes()} "
        f"[locations={loc}, resources={res}], "
        f"edges={G.number_of_edges()})"
    )


# ---------------------------------------------------------------------------
# Node construction
# ---------------------------------------------------------------------------


def _add_location_nodes(G: nx.DiGraph, dataset: DataSet) -> None:
    for loc in dataset.location_list:
        if loc.id in G:
            raise ValueError(f"Duplicate node id detected: {loc.id!r}")
        attrs: dict[str, Any] = {
            "kind": "location",
            "id": loc.id,
            "name": loc.name,
            "type": loc.type.value,
            "unlock_level": loc.unlock_level,
        }
        if loc.max_slots is not None:
            attrs["max_slots"] = loc.max_slots
        if loc.description is not None:
            attrs["description"] = loc.description
        G.add_node(loc.id, **attrs)


def _add_resource_nodes(G: nx.DiGraph, dataset: DataSet) -> None:
    for res in dataset.resource_list:
        if res.id in G:
            raise ValueError(
                f"Node id collision between location and resource: {res.id!r}"
            )
        attrs: dict[str, Any] = {
            "kind": "resource",
            "id": res.id,
            "name": res.name,
            "type": res.type.value,
            "unlock_level": res.unlock_level,
        }
        if res.source_location_id is not None:
            attrs["source_location_id"] = res.source_location_id
        if res.description is not None:
            attrs["description"] = res.description
        if res.max_in_barn is not None:
            attrs["max_in_barn"] = res.max_in_barn
        G.add_node(res.id, **attrs)


# ---------------------------------------------------------------------------
# Edge construction
# ---------------------------------------------------------------------------


_RAW_RESOURCE_TYPES = {
    ResourceType.CROP,
    ResourceType.ANIMAL_PRODUCT,
    ResourceType.ORE,
}


def _add_produces_edges(G: nx.DiGraph, dataset: DataSet) -> None:
    """location ─PRODUCES→ resource  for raw resources only (crop / animal / ore)."""
    for res in dataset.resource_list:
        if res.type not in _RAW_RESOURCE_TYPES:
            continue
        if not res.source_location_id:
            continue
        if res.source_location_id not in G:
            logger.warning(
                "Skipping produces edge: source location %r missing for resource %r",
                res.source_location_id,
                res.id,
            )
            continue
        w = produces_weight()
        _add_or_merge_edge(
            G,
            res.source_location_id,
            res.id,
            edge_attrs(EdgeType.PRODUCES, w, amount=1),
        )


def _add_recipe_edges(G: nx.DiGraph, dataset: DataSet) -> None:
    """resource ─CONSUMES→ location ─OUTPUTS→ resource  for every recipe."""
    for rec in dataset.recipe_list:
        loc_id = rec.location_id
        out_id = rec.output.resource_id
        out_amount = rec.output.amount

        if loc_id not in G or out_id not in G:
            logger.warning(
                "Skipping recipe %r: location or output resource missing", rec.id
            )
            continue

        # --- OUTPUTS edge (location → output resource) ---
        _add_or_merge_edge(
            G,
            loc_id,
            out_id,
            edge_attrs(
                EdgeType.OUTPUTS,
                outputs_weight(),
                amount=out_amount,
                recipe_id=rec.id,
            ),
        )

        # --- CONSUMES edges (input resource → location) ---
        for inp in rec.inputs:
            if inp.resource_id not in G:
                logger.debug(
                    "Recipe %r skips external input %r", rec.id, inp.resource_id
                )
                continue

            ratio = recipe_ratio(inp.amount, out_amount)
            w = consumes_weight(inp.amount, out_amount)
            _add_or_merge_edge(
                G,
                inp.resource_id,
                loc_id,
                edge_attrs(
                    EdgeType.CONSUMES,
                    w,
                    amount=inp.amount,
                    recipe_id=rec.id,
                    ratio=ratio,
                ),
            )


def _add_or_merge_edge(
    G: nx.DiGraph,
    u: str,
    v: str,
    attrs: dict[str, Any],
) -> None:
    """
    Add edge u→v.  If the edge already exists, accumulate weight and
    keep a comma-separated list of recipe_ids (when present).
    """
    if G.has_edge(u, v):
        existing = G[u][v]
        existing[ATTR_WEIGHT] = existing.get(ATTR_WEIGHT, 0.0) + attrs[ATTR_WEIGHT]
        old_rid = existing.get(ATTR_RECIPE_ID)
        new_rid = attrs.get(ATTR_RECIPE_ID)
        if new_rid:
            if old_rid:
                ids = {x.strip() for x in str(old_rid).split(",") if x.strip()}
                ids.add(new_rid)
                existing[ATTR_RECIPE_ID] = ",".join(sorted(ids))
            else:
                existing[ATTR_RECIPE_ID] = new_rid
        if attrs.get(ATTR_AMOUNT, 0) > existing.get(ATTR_AMOUNT, 0):
            existing[ATTR_AMOUNT] = attrs[ATTR_AMOUNT]
        if "ratio" in attrs:
            existing["ratio"] = max(existing.get("ratio", 0.0), attrs["ratio"])
    else:
        G.add_edge(u, v, **attrs)


# ---------------------------------------------------------------------------
# Convenience helpers used by tests / main / future analysis
# ---------------------------------------------------------------------------


def location_nodes(G: nx.DiGraph) -> list[str]:
    return [n for n, d in G.nodes(data=True) if d.get("kind") == "location"]


def resource_nodes(G: nx.DiGraph) -> list[str]:
    return [n for n, d in G.nodes(data=True) if d.get("kind") == "resource"]


def edges_of_type(G: nx.DiGraph, edge_type: EdgeType) -> list[tuple[str, str, dict]]:
    return [
        (u, v, d)
        for u, v, d in G.edges(data=True)
        if d.get(ATTR_EDGE_TYPE) == edge_type.value
    ]
