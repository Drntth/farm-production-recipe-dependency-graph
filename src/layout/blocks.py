"""
Named production blocks for the farm (anchor method).

1. Every production building is an *anchor*.
2. Every supplier (tree, bush, animal shelter) joins the anchor with the
   strongest direct coupling in the location proximity graph; a support
   relation (nectar bush → beehive tree) makes the source follow its target.
   Fields are no member of any block: ``fields.py`` gives every block its own
   share, because almost every building uses crops.
3. A block that is a lone building (no suppliers, less than
   ``min_crop_share`` of the farm's crop demand) merges into the block it is
   most strongly coupled to, as long as that block holds fewer than
   ``max_anchors`` buildings. A big crop user (the feed mill) keeps its own
   block: its fields are its suppliers.
4. A block is named after its main anchor: the building with the highest
   coupling inside the block, the earlier unlock on a tie ("Dairy block").

The method only needs the graph, so new levels update the blocks by
themselves. Fixed buildings (``movable: false``) never join a block.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from src.graph.analysis import location_proximity_graph

from .packing import neg_key
from .support import active_relations

DEFAULT_MAX_ANCHORS = 3
DEFAULT_MIN_CROP_SHARE = 0.1
STORAGE_BLOCK_ID = "storage_block"
STORAGE_BLOCK_ANCHOR = "barn"


@dataclass
class Block:
    id: str
    name: str
    anchor: str
    locations: list[str] = field(default_factory=list)  # anchor first


def farm_locations(G: nx.DiGraph) -> dict[str, dict]:
    """Movable farm locations of the graph with their node attributes."""
    return {
        n: d
        for n, d in G.nodes(data=True)
        if d.get("kind") == "location"
        and d.get("area") == "farm"
        and d.get("movable", True)
    }


def direct_coupling(G: nx.DiGraph, location_ids: set[str]) -> nx.Graph:
    """Direct (one-hop) location coupling, restricted to *location_ids*, plus support relations."""
    P = location_proximity_graph(G, max_hops=1).subgraph(location_ids).copy()
    P.add_nodes_from(location_ids)
    for rel in active_relations(location_ids):
        w = (
            P[rel.source][rel.target]["weight"]
            if P.has_edge(rel.source, rel.target)
            else 0.0
        )
        P.add_edge(rel.source, rel.target, weight=w + rel.weight, support=True)
    return P


def crop_demand_by_location(G: nx.DiGraph) -> dict[str, dict[str, float]]:
    """location id → {crop id: summed CONSUMES weight} for crops grown on fields."""
    field_locs = {
        n
        for n, d in G.nodes(data=True)
        if d.get("kind") == "location" and d.get("type") == "field"
    }
    demand: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for crop, d in G.nodes(data=True):
        if d.get("kind") != "resource" or d.get("source_location_id") not in field_locs:
            continue
        for _, consumer, e in G.out_edges(crop, data=True):
            if e.get("edge_type") == "consumes":
                demand[consumer][crop] += float(e.get("weight", 0.0))
    return {loc: dict(c) for loc, c in demand.items()}


def detect_named_blocks(
    G: nx.DiGraph,
    *,
    max_anchors: int = DEFAULT_MAX_ANCHORS,
    min_crop_share: float = DEFAULT_MIN_CROP_SHARE,
) -> list[Block]:
    """Group the movable farm locations of *G* into named blocks."""
    # fields are shared out per block afterwards (fields.py), never as a member
    locs = {n: d for n, d in farm_locations(G).items() if d.get("type") != "field"}
    if not locs:
        return []
    P = direct_coupling(G, set(locs))
    is_anchor = {n: d.get("type") == "production" for n, d in locs.items()}

    def w(a: str, b: str) -> float:
        return P[a][b]["weight"] if P.has_edge(a, b) else 0.0

    # 1-2. anchors and their suppliers; storage (barn, silo) is one block of its own
    members: dict[str, set[str]] = {a: {a} for a in sorted(locs) if is_anchor[a]}
    storage = sorted(n for n, d in locs.items() if d.get("type") == "storage")
    storage_anchor = STORAGE_BLOCK_ANCHOR if STORAGE_BLOCK_ANCHOR in storage else None
    storage_anchor = storage_anchor or (storage[0] if storage else None)
    if storage_anchor:
        members[storage_anchor] = set(storage)
    support_targets = {r.source: r.target for r in active_relations(set(locs))}
    orphans: list[str] = []
    for n in sorted(locs):
        if is_anchor[n] or n in support_targets or n in storage:
            continue
        best = max(
            (a for a in members if w(n, a) > 0),
            key=lambda a: (w(n, a), neg_key(a)),
            default=None,
        )
        if best is None:
            orphans.append(n)
        else:
            members[best].add(n)
    for n in orphans:
        members[n] = {n}
    for source, target in sorted(support_targets.items()):
        owner = next(k for k, m in members.items() if target in m)
        members[owner].add(source)

    # 3. merge lone buildings (big crop users are never lone)
    crops = {loc: sum(c.values()) for loc, c in crop_demand_by_location(G).items()}
    crop_total = sum(v for loc, v in crops.items() if loc in locs) or 1.0
    big_crop_user = {
        n for n in locs if crops.get(n, 0.0) / crop_total >= min_crop_share
    }

    def coupling(a: set[str], b: set[str]) -> float:
        return sum(w(x, y) for x in a for y in b)

    def anchor_count(m: set[str]) -> int:
        return sum(1 for x in m if is_anchor[x])

    changed = True
    while changed:
        changed = False
        lonely = sorted(
            k
            for k, m in members.items()
            if len(m) == 1 and is_anchor[k] and k not in big_crop_user
        )
        candidates = []
        for k in lonely:
            for other, m in members.items():
                if other == k or anchor_count(m) >= max_anchors:
                    continue
                c = coupling(members[k], m)
                if c > 0:
                    candidates.append((c, k, other))
        if candidates:
            c, k, other = max(
                candidates, key=lambda t: (t[0], neg_key(t[1]), neg_key(t[2]))
            )
            members[other] |= members.pop(k)
            changed = True

    # 4. name the blocks
    blocks = []
    for m in members.values():
        anchors = [x for x in m if is_anchor[x]] or list(m)
        main = max(
            anchors,
            key=lambda a: (
                sum(w(a, x) for x in m),
                -locs[a].get("unlock_level", 0),
                neg_key(a),
            ),
        )
        name = locs[main].get("name", main)
        block_id = f"{main}_block"
        if storage_anchor in m:
            main, name, block_id = storage_anchor, "Storage", STORAGE_BLOCK_ID
        blocks.append(
            Block(
                id=block_id,
                name=f"{name} block",
                anchor=main,
                locations=[main] + sorted(m - {main}),
            )
        )
    blocks.sort(key=lambda b: (-len(b.locations), b.id))
    return blocks


def block_coupling(P: nx.Graph, blocks: list[Block]) -> dict[tuple[str, str], float]:
    """Summed direct coupling between every pair of blocks (keys sorted)."""
    owner = {loc: b.id for b in blocks for loc in b.locations}
    result: dict[tuple[str, str], float] = defaultdict(float)
    for u, v, d in P.edges(data=True):
        bu, bv = owner.get(u), owner.get(v)
        if bu is None or bv is None or bu == bv:
            continue
        result[tuple(sorted((bu, bv)))] += d.get("weight", 0.0)
    return dict(result)


def block_flow_order(G: nx.DiGraph, blocks: list[Block]) -> list[str]:
    """
    Block ids from upstream to downstream along the resource flow.

    Block A feeds block B if a location of B consumes a resource that a
    location of A produces. Cycles are collapsed; on a tie the block that feeds
    more blocks comes first, then the larger block.
    """
    owner = {loc: b.id for b in blocks for loc in b.locations}
    F = nx.DiGraph()
    F.add_nodes_from(b.id for b in blocks)
    for u, v, d in G.edges(data=True):
        if d.get("edge_type") != "consumes" or v not in owner:
            continue
        for producer in G.predecessors(u):
            ed = G[producer][u].get("edge_type")
            if ed in ("produces", "outputs") and producer in owner:
                a, b = owner[producer], owner[v]
                if a != b:
                    F.add_edge(a, b)
    rank = {b.id: i for i, b in enumerate(blocks)}
    C = nx.condensation(F)
    order: list[str] = []
    for comp in nx.lexicographical_topological_sort(
        C,
        key=lambda c: (
            -max(F.out_degree(m) for m in C.nodes[c]["members"]),
            min(rank[m] for m in C.nodes[c]["members"]),
        ),
    ):
        order.extend(sorted(C.nodes[comp]["members"], key=rank.__getitem__))
    return order
