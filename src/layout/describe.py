"""Textual layout description (Markdown) and the JSON payload of a layout."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .inventory import CountSource
from .planner import Layout, PlacedBlock


def layout_to_dict(layout: Layout) -> dict[str, Any]:
    """JSON-ready payload: blocks, items, fixed buildings, relations."""
    fm = layout.farm_map
    return {
        "level": layout.level,
        "map": {
            "bounded": fm.bounded,
            "width": fm.width,
            "height": fm.height,
            "extent": _rect(layout.extent()),
        },
        "reserve_ratio": layout.reserve_ratio,
        "reserve_requested": layout.reserve_requested,
        "strategy": layout.strategy,
        "flow_order": layout.flow_order,
        "blocks": [
            {
                "id": pb.block.id,
                "name": pb.block.name,
                "anchor": pb.block.anchor,
                "locations": pb.block.locations,
                "frame": _rect(pb.frame) if pb.frame else None,
                "fields": (
                    {
                        "count": pb.fields.count,
                        "reserved": pb.fields.reserved,
                        "crops": pb.fields.crops,
                    }
                    if pb.fields
                    else None
                ),
                "used_tiles": pb.used_tiles,
                "reserved_tiles": pb.reserved_tiles,
                "items": [
                    {
                        "location_id": i.location_id,
                        **_rect(i.rect),
                        "rotated": i.rotated,
                        "reserved": i.reserved,
                    }
                    for i in pb.items
                ],
            }
            for pb in layout.blocks
        ],
        "fixed": [
            {"id": f.id, "name": f.label, **(_rect_xywh(f) if f.is_placed else {})}
            for f in fm.fixed
        ],
        "fixed_unplaced": layout.fixed_unplaced,
        "neighbourhoods": [
            {"a": n.a, "b": n.b, "weight": round(n.weight, 4), "reason": n.reason}
            for n in layout.neighbourhoods
        ],
        "support_relations": [
            {"source": r.source, "target": r.target, "reason": r.reason}
            for r in layout.support
        ],
        "counts": [
            {
                "location_id": s.location.id,
                "count": s.count,
                "reserved": s.reserved,
                "source": s.source.value,
            }
            for s in layout.stock
        ],
        "missing_footprint": layout.missing_footprint,
    }


def layout_to_markdown(layout: Layout) -> str:
    names = {pb.block.id: pb.block.name for pb in layout.blocks}
    stock = {s.location.id: s for s in layout.stock}
    fm = layout.farm_map
    ext = layout.extent()
    requested = layout.reserve_requested
    lowered = (
        f" (lowered from {requested:.0%} so that the blocks fit)"
        if requested is not None and layout.reserve_ratio < requested
        else ""
    )
    lines = [
        f"# Farm layout - level {layout.level}",
        "",
        (
            f"Farm map: {fm.width} x {fm.height} tiles."
            if fm.bounded
            else f"Farm map: unbounded (no `config/farm_map.json` size); layout spans "
            f"{ext.w} x {ext.h} tiles."
        ),
        (
            f"Block order: {layout.strategy}. "
            f"Each block keeps {layout.reserve_ratio:.0%} extra area for later "
            f"unlocks{lowered}. "
            "Coordinates are tiles: x along the ↘ edge, y along the ↙ edge."
        ),
        "",
        "## Blocks",
        "",
        "| Block | Items | Frame (w x h) | Position (x, y) | Used / reserved tiles |",
        "| --- | --- | --- | --- | --- |",
    ]
    for pb in layout.blocks:
        lines.append(
            f"| {pb.block.name} | {_items(pb, stock, layout.crop_names)} | "
            + (
                f"{pb.frame.w} x {pb.frame.h} | ({pb.frame.x}, {pb.frame.y})"
                if pb.frame
                else "- | not placed"
            )
            + f" | {pb.used_tiles} / {pb.reserved_tiles} |"
        )

    lines += ["", "## Relative order (upstream → downstream)", ""]
    lines += [f"{i}. {names[b]}" for i, b in enumerate(layout.flow_order, 1)]

    lines += ["", "## Recommended neighbourhoods", ""]
    for n in layout.neighbourhoods:
        a = names.get(n.a, n.a)
        b = names.get(n.b, n.b)
        lines.append(f"- {a} ↔ {b} ({n.reason}, coupling {n.weight:g})")
    for r in layout.support:
        lines.append(f"- {r.source} next to {r.target}: {r.reason}")

    notes = [
        (
            "Field counts per block are estimates from recipe weights (crop demand of "
            "the block's buildings); the Production Planner will size them from real "
            "quantities."
        )
    ]
    placeholders = sorted(
        s.location.name for s in layout.stock if s.source == CountSource.PLACEHOLDER
    )
    if placeholders:
        notes.append(
            "One placeholder copy (count not in the profile): "
            + ", ".join(placeholders)
        )
    if layout.fixed_unplaced:
        notes.append(
            "Fixed, position unknown (add to `config/farm_map.json`): "
            + ", ".join(layout.fixed_unplaced)
        )
    if layout.unplaced_blocks:
        notes.append(
            "Did not fit on the map: "
            + ", ".join(names[b] for b in layout.unplaced_blocks)
        )
    if layout.missing_footprint:
        notes.append("No footprint (skipped): " + ", ".join(layout.missing_footprint))
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def _items(pb: PlacedBlock, stock, crop_names: dict[str, str]) -> str:
    counts = Counter(i.location_id for i in pb.items if not i.reserved)
    reserved = Counter(i.location_id for i in pb.items if i.reserved)
    parts = []
    if pb.fields is not None:
        crops = ", ".join(crop_names.get(c, c) for c in pb.fields.crops) or "shared"
        part = f"{pb.fields.count}× Field ({crops})"
        if pb.fields.reserved:
            part += f" (+{pb.fields.reserved} reserved)"
        parts.append(part)
    for loc_id in pb.block.locations:
        if (
            pb.fields is not None
            and stock.get(loc_id)
            and stock[loc_id].location.type.value == "field"
        ):
            continue
        if loc_id not in counts and loc_id not in reserved:
            continue
        name = stock[loc_id].location.name if loc_id in stock else loc_id
        part = f"{counts[loc_id]}× {name}"
        if reserved[loc_id]:
            part += f" (+{reserved[loc_id]} reserved)"
        parts.append(part)
    return ", ".join(parts)


def _rect(r) -> dict[str, int]:
    return {"x": r.x, "y": r.y, "width": r.w, "height": r.h}


def _rect_xywh(f) -> dict[str, int]:
    return {"x": f.x, "y": f.y, "width": f.width, "height": f.height}
