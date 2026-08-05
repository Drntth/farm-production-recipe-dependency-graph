"""
Graph analysis for the Layout Planner (v0.3).

Provides:

1. **Location proximity graph** - undirected weighted graph of locations only,
   with multi-level dependency propagation so that e.g. field and dairy are
   coupled through feed_mill → cow_pasture → milk → dairy.

2. **Production block detection** - community detection (Louvain) on the
   proximity graph to suggest clusters that should be placed close together.

3. **Basic analysis** - degree / betweenness centrality, bottleneck ranking,
   and dependency path queries on the full production DiGraph.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx
from networkx.algorithms.community import louvain_communities

from .relationship import ATTR_EDGE_TYPE, ATTR_WEIGHT, EdgeType

logger = logging.getLogger(__name__)

DEFAULT_MAX_HOPS = 3
DEFAULT_DECAY = 0.5


# ---------------------------------------------------------------------------
# Location proximity (multi-level weighted dependencies)
# ---------------------------------------------------------------------------


def location_proximity_graph(
    G: nx.DiGraph,
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
    decay: float = DEFAULT_DECAY,
) -> nx.Graph:
    """
    Build an undirected weighted graph of **locations only**.

    Direct coupling
    ---------------
    For every CONSUMES edge ``resource → location_B``:

    - if the resource has ``source_location_id = location_A``, add weight
      between A and B (raw producer → consumer building);
    - if the resource is produced via an OUTPUTS edge ``location_A → resource``,
      add weight between A and B (processing chain step).

    Multi-level propagation
    -----------------------
    Effective weights are then diffused up to *max_hops* on the location
    graph: a path A-X-B contributes ``w(A,X) * w(X,B) * decay`` to (A, B).
    This pulls upstream fields/pastures toward downstream buildings even
    when they are not directly adjacent in the recipe graph.
    """
    loc_ids = {n for n, d in G.nodes(data=True) if d.get("kind") == "location"}
    P = nx.Graph()
    P.add_nodes_from((n, dict(G.nodes[n])) for n in loc_ids)

    resource_producers: dict[str, set[str]] = defaultdict(set)
    for n, d in G.nodes(data=True):
        if d.get("kind") != "resource":
            continue
        src = d.get("source_location_id")
        if src and src in loc_ids:
            resource_producers[n].add(src)

    for u, v, d in G.edges(data=True):
        if d.get(ATTR_EDGE_TYPE) == EdgeType.OUTPUTS.value and u in loc_ids:
            resource_producers[v].add(u)

    for u, v, d in G.edges(data=True):
        if d.get(ATTR_EDGE_TYPE) != EdgeType.CONSUMES.value:
            continue
        if v not in loc_ids:
            continue
        weight = float(d.get(ATTR_WEIGHT, 1.0))
        for producer in resource_producers.get(u, ()):
            if producer == v:
                continue
            _add_undirected_weight(P, producer, v, weight)

    if max_hops > 1 and P.number_of_edges() > 0:
        _propagate_weights(P, max_hops=max_hops, decay=decay)

    logger.info(
        "Location proximity graph: %d locations, %d edges",
        P.number_of_nodes(),
        P.number_of_edges(),
    )
    return P


def _add_undirected_weight(P: nx.Graph, a: str, b: str, w: float) -> None:
    if a == b:
        return
    if P.has_edge(a, b):
        P[a][b]["weight"] = P[a][b].get("weight", 0.0) + w
    else:
        P.add_edge(a, b, weight=w)


def _propagate_weights(P: nx.Graph, *, max_hops: int, decay: float) -> None:
    """Diffuse edge weights along paths up to max_hops (in-place)."""
    current = {(u, v): d["weight"] for u, v, d in P.edges(data=True)}

    for hop in range(2, max_hops + 1):
        additions: dict[tuple[str, str], float] = defaultdict(float)
        for (a, b), w_ab in list(current.items()):
            for neighbor in P.neighbors(b):
                if neighbor == a:
                    continue
                w_bn = P[b][neighbor]["weight"]
                key = tuple(sorted((a, neighbor)))
                additions[key] += w_ab * w_bn * (decay ** (hop - 1))
            for neighbor in P.neighbors(a):
                if neighbor == b:
                    continue
                w_an = P[a][neighbor]["weight"]
                key = tuple(sorted((b, neighbor)))
                additions[key] += w_ab * w_an * (decay ** (hop - 1))

        for (u, v), w in additions.items():
            _add_undirected_weight(P, u, v, w)
            current[(u, v)] = current.get((u, v), 0.0) + w


# ---------------------------------------------------------------------------
# Clustering / production blocks
# ---------------------------------------------------------------------------


def detect_production_blocks(
    G: nx.DiGraph,
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
    decay: float = DEFAULT_DECAY,
    resolution: float = 1.0,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """
    Detect production blocks (clusters of tightly coupled locations).

    Returns a list of block dicts sorted by size (largest first)::

        {
          "id": 0,
          "locations": ["dairy", "cow_pasture", "feed_mill", ...],
          "size": 4,
        }
    """
    P = location_proximity_graph(G, max_hops=max_hops, decay=decay)
    if P.number_of_nodes() == 0:
        return []

    communities = louvain_communities(
        P, weight="weight", resolution=resolution, seed=seed
    )

    blocks: list[dict[str, Any]] = []
    for idx, community in enumerate(
        sorted(communities, key=lambda c: (-len(c), min(c) if c else ""))
    ):
        locs = sorted(community)
        blocks.append({"id": idx, "locations": locs, "size": len(locs)})

    logger.info("Detected %d production blocks", len(blocks))
    return blocks


# ---------------------------------------------------------------------------
# Centrality & path analysis
# ---------------------------------------------------------------------------


def centrality_report(G: nx.DiGraph, *, top_n: int = 10) -> dict[str, Any]:
    """
    Degree and betweenness centrality on the full production graph.

    Betweenness highlights bottleneck resources / locations that lie on
    many dependency paths - useful for layout (keep them central) and for
    the future Production Planner.
    """
    if G.number_of_nodes() == 0:
        return {"degree": [], "betweenness": []}

    degree = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, normalized=True)

    def _top(scores: dict[str, float]) -> list[dict[str, Any]]:
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_n]
        result = []
        for node_id, score in ranked:
            attrs = G.nodes[node_id]
            result.append(
                {
                    "id": node_id,
                    "name": attrs.get("name", node_id),
                    "kind": attrs.get("kind"),
                    "score": round(score, 6),
                }
            )
        return result

    return {
        "degree": _top(degree),
        "betweenness": _top(betweenness),
    }


def dependency_path(G: nx.DiGraph, source: str, target: str) -> list[str] | None:
    """
    Shortest dependency path from *source* to *target*, or None if unreachable.
    """
    if source not in G or target not in G:
        return None
    try:
        return nx.shortest_path(G, source, target)
    except nx.NetworkXNoPath:
        return None


def has_dependency_path(G: nx.DiGraph, source: str, target: str) -> bool:
    """Return True if a directed path exists from source to target."""
    if source not in G or target not in G:
        return False
    return nx.has_path(G, source, target)


def analysis_summary(
    G: nx.DiGraph,
    *,
    top_n: int = 8,
    max_hops: int = DEFAULT_MAX_HOPS,
) -> dict[str, Any]:
    """
    Full analysis payload suitable for JSON export or CLI printing.
    """
    blocks = detect_production_blocks(G, max_hops=max_hops)
    centrality = centrality_report(G, top_n=top_n)
    proximity = location_proximity_graph(G, max_hops=max_hops)

    return {
        "production_blocks": blocks,
        "centrality": centrality,
        "proximity_graph": {
            "location_count": proximity.number_of_nodes(),
            "edge_count": proximity.number_of_edges(),
            "top_couplings": _top_couplings(proximity, top_n=top_n),
        },
    }


def _top_couplings(P: nx.Graph, top_n: int = 8) -> list[dict[str, Any]]:
    edges = [
        {
            "source": u,
            "target": v,
            "weight": round(d.get("weight", 0.0), 4),
        }
        for u, v, d in P.edges(data=True)
    ]
    edges.sort(key=lambda e: -e["weight"])
    return edges[:top_n]
