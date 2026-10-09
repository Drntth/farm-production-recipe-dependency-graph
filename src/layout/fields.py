"""
Dedicated fields per block.

Fields are not one shared block: every block gets its own plantable fields
for the crops its buildings consume, so a crop (corn for the feed mill,
sugarcane for the sugar mill) can stay planted there permanently.

Without production data the split follows the graph: a block's crop demand is
the sum of the CONSUMES weights of field crops into its buildings, and the
fields are shared out in proportion (largest remainder, at least one field per
block that uses crops). An optional ``pool_ratio`` keeps part of the fields in
a separate "Shared fields" block for rarely used crops. The Production Planner
and the Combiner will replace the estimate with real quantities.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from .blocks import Block, crop_demand_by_location

SHARED_BLOCK_ID = "shared_fields_block"


@dataclass
class FieldShare:
    block_id: str
    count: int
    reserved: int = 0
    crops: list[str] = field(default_factory=list)  # crop ids, heaviest first


def crop_demand(G: nx.DiGraph, blocks: list[Block]) -> dict[str, dict[str, float]]:
    """block id → {crop id: summed CONSUMES weight} for crops grown on fields."""
    owner = {loc: b.id for b in blocks for loc in b.locations}
    demand: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for loc, crops in crop_demand_by_location(G).items():
        if loc in owner:
            for crop, w in crops.items():
                demand[owner[loc]][crop] += w
    return {b: dict(c) for b, c in demand.items()}


def allocate_fields(
    G: nx.DiGraph,
    blocks: list[Block],
    count: int,
    reserved: int = 0,
    *,
    pool_ratio: float = 0.0,
) -> list[FieldShare]:
    """Split *count* fields (+ *reserved* free ones) among the crop-using blocks."""
    demand = crop_demand(G, blocks)
    totals = {
        b: sum(c.values()) for b, c in sorted(demand.items()) if sum(c.values()) > 0
    }

    pool = round(count * pool_ratio) if totals else count
    owned = apportion(count - pool, totals, minimum=1)
    spare = apportion(reserved, totals, minimum=0)

    shares = [
        FieldShare(
            block_id=b,
            count=owned.get(b, 0),
            reserved=spare.get(b, 0),
            crops=sorted(demand[b], key=lambda c: (-demand[b][c], c)),
        )
        for b in totals
    ]
    if pool > 0:
        shares.append(FieldShare(SHARED_BLOCK_ID, pool))
    return [s for s in shares if s.count + s.reserved > 0]


def apportion(
    total: int, weights: dict[str, float], *, minimum: int = 0
) -> dict[str, int]:
    """
    Split *total* in proportion to *weights* (largest remainder method).

    Every key first gets *minimum* if the total allows it; otherwise the
    heaviest keys get one each.
    """
    if total <= 0 or not weights:
        return {}
    keys = sorted(weights, key=lambda k: (-weights[k], k))
    if minimum * len(keys) > total:
        return {k: 1 for k in keys[:total]}
    result = {k: minimum for k in keys}
    rest = total - minimum * len(keys)
    weight_sum = sum(weights.values())
    exact = {k: rest * weights[k] / weight_sum for k in keys}
    for k in keys:
        result[k] += math.floor(exact[k])
    left = rest - sum(math.floor(v) for v in exact.values())
    for k in sorted(
        keys, key=lambda k: (-(exact[k] - math.floor(exact[k])), keys.index(k))
    )[:left]:
        result[k] += 1
    return result
