"""
Dedicated fields per block.

Fields are not one shared block: every block gets its own plantable fields
for the crops its buildings consume, so a crop (corn for the feed mill,
sugarcane for the sugar mill) can stay planted there permanently.

Without production data the split follows the graph: a block's crop demand is
the sum of the CONSUMES weights of field crops into its buildings, and the
fields are shared out in proportion (largest remainder, at least one field per
block that uses crops). An optional ``pool_ratio`` keeps part of the fields in
a separate "Shared fields" block for rarely used crops.

With production quantities (``allocate_fields_by_use``, from the Combiner)
every crop's fields are split among the blocks in proportion to how much of
the crop their buildings use; fields of crops no block uses (sold or delivered)
and owned fields the plan leaves empty go to the "Shared fields" block.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from .blocks import Block, crop_demand_by_location

SHARED_BLOCK_ID = "shared_fields_block"
MIN_CROP_FIELDS = 0.5  # a crop is listed for a block from half a field on


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


def allocate_fields_by_use(
    blocks: list[Block],
    crop_fields: dict[str, int],
    crop_use: dict[str, dict[str, float]],
    count: int,
    reserved: int = 0,
) -> list[FieldShare]:
    """Split *count* fields by the crop use of the blocks' buildings."""
    owner = {loc: b.id for b in blocks for loc in b.locations}
    by_block: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for crop, n in sorted(crop_fields.items()):
        if n <= 0:
            continue
        users: dict[str, float] = defaultdict(float)
        for loc, use in crop_use.get(crop, {}).items():
            if loc in owner and use > 0:
                users[owner[loc]] += use
        total = sum(users.values())
        if total <= 0:  # sold or delivered only
            by_block[SHARED_BLOCK_ID][crop] += n
            continue
        for b, use in users.items():
            by_block[b][crop] += n * use / total

    weights = {b: sum(c.values()) for b, c in by_block.items()}
    planned = min(sum(max(n, 0) for n in crop_fields.values()), count)
    owned = apportion(planned, weights)
    left = count - planned  # owned but not needed by the plan: spare fields
    if left > 0:
        owned[SHARED_BLOCK_ID] = owned.get(SHARED_BLOCK_ID, 0) + left
    # no planned crop at all: the reserved fields still need a place
    spare = apportion(reserved, weights or {SHARED_BLOCK_ID: 1.0})

    shares = [
        FieldShare(
            block_id=b,
            count=owned.get(b, 0),
            reserved=spare.get(b, 0),
            crops=_main_crops(by_block.get(b, {})),
        )
        for b in sorted(
            set(owned) | set(spare), key=lambda b: (b == SHARED_BLOCK_ID, b)
        )
    ]
    return [s for s in shares if s.count + s.reserved > 0]


def _main_crops(fields: dict[str, float]) -> list[str]:
    """Crops with at least ``MIN_CROP_FIELDS`` fields, heaviest first (at least one)."""
    ranked = sorted(fields, key=lambda c: (-fields[c], c))
    return [c for c in ranked if fields[c] >= MIN_CROP_FIELDS] or ranked[:1]


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
