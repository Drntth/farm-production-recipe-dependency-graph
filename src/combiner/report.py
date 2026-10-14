"""Combined report: combined.json and combined.md."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.layout.describe import layout_to_dict, layout_to_markdown
from src.loaders.json_loader import DataSet
from src.planner.schedule import schedule_to_markdown

from .combine import CombinedPlan

_TOP_LINKS = 15
_KIND_TEXT = {"new": "new unlock", "copies": "more copies", "fields": "more fields"}


def block_rows(combined: CombinedPlan, dataset: DataSet) -> list[dict[str, Any]]:
    """Per block (upstream → downstream): copies, fields, busy share, output."""
    layout, plan = combined.layout, combined.run.chosen
    stock = {s.location.id: s for s in layout.stock}
    made: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for rp in plan.recipes.values():
        good = dataset.recipes[rp.recipe_id].output.resource_id
        made[rp.location_id][good] += rp.per_hour
    for fp in plan.fruits.values():
        made[fp.location_id][fp.resource_id] += fp.per_hour
    rank = {b: i for i, b in enumerate(layout.flow_order)}
    rows = []
    for pb in sorted(layout.blocks, key=lambda b: rank.get(b.block.id, len(rank))):
        locations = []
        for loc_id in pb.block.locations:
            s = stock.get(loc_id)
            if s is None:
                continue
            locations.append(
                {
                    "id": loc_id,
                    "name": s.location.name,
                    "copies": s.count,
                    "reserved": s.reserved,
                    "source": s.source.value,
                    "busy": plan.utilization.get(loc_id),
                    "per_hour": {
                        g: round(v, 3) for g, v in sorted(made[loc_id].items())
                    },
                }
            )
        rows.append(
            {
                "id": pb.block.id,
                "name": pb.block.name,
                "placed": pb.frame is not None,
                "locations": locations,
                "fields": (
                    {
                        "count": pb.fields.count,
                        "reserved": pb.fields.reserved,
                        "crops": pb.fields.crops,
                    }
                    if pb.fields
                    else None
                ),
            }
        )
    return rows


def combined_to_dict(combined: CombinedPlan, dataset: DataSet) -> dict[str, Any]:
    plan, layout = combined.run.chosen, combined.layout
    return {
        "level": combined.level,
        "summary": {
            "login_interval_hours": plan.interval_hours,
            "production_hours_per_hour": round(plan.busy_hours_per_hour, 2),
            "fields_used": round(plan.fields_used, 2),
            "blocks": len(layout.blocks),
            "blocks_not_placed": layout.unplaced_blocks,
            "strategy": layout.strategy,
            "reserve_ratio": layout.reserve_ratio,
            "design": layout.design is not None,
        },
        "blocks": block_rows(combined, dataset),
        "flow_links": [
            {
                "source": link.source,
                "target": link.target,
                "per_hour": round(link.per_hour, 3),
                "tiles_apart": link.distance,
            }
            for link in combined.flow_links
        ],
        "expansion": {
            "lookahead_levels": combined.lookahead,
            "upcoming": [
                {
                    "location_id": u.location_id,
                    "kind": u.kind,
                    "unlock_level": u.unlock_level,
                    "count": u.count,
                    "tiles": u.tiles,
                }
                for u in combined.upcoming
            ],
            "reserved_in_blocks": {
                s.location.id: s.reserved for s in layout.stock if s.reserved
            },
            "free_tiles": combined.free_tiles,
            "new_building_tiles": combined.new_building_tiles,
        },
        "warnings": combined.warnings,
        "layout": layout_to_dict(layout),
        "schedule": combined.run.schedule,
    }


def combined_to_markdown(combined: CombinedPlan, dataset: DataSet) -> str:
    plan, layout = combined.run.chosen, combined.layout
    names = {pb.block.id: pb.block.name for pb in layout.blocks}
    placed = len(layout.blocks) - len(layout.unplaced_blocks)
    lines = [
        f"# Combined farm plan - level {combined.level}",
        "",
        (
            "The farm layout sized by the production plan: every block holds the "
            "copies, fields, trees and bushes its share of the plan needs, and the "
            "blocks are placed along the processing order (upstream first)."
        ),
        "",
        (
            f"- Login every {plan.interval_hours:g} h; "
            f"{plan.busy_hours_per_hour:.1f} production hours per hour; "
            f"{round(plan.fields_used)} fields in use."
        ),
        (
            f"- {placed} of {len(layout.blocks)} blocks placed; block order "
            f"{layout.strategy}; {layout.reserve_ratio:.0%} extra area per block."
        ),
        "- Design layer: "
        + ("included (see below)." if layout.design else "not requested."),
        "",
        "## Blocks (upstream → downstream)",
        "",
        "| Block | Buildings, trees, bushes (copies, busy) | Fields (crops) |",
        "| --- | --- | --- |",
    ]
    for row in block_rows(combined, dataset):
        items = []
        for loc in row["locations"]:
            text = f"{loc['name']} x{loc['copies']}"
            if loc["reserved"]:
                text += f" (+{loc['reserved']} reserved)"
            if loc["busy"] is not None:
                text += f", {loc['busy']:.0%}"
            items.append(text)
        f = row["fields"]
        fields = (
            f"{f['count']}"
            + (f" (+{f['reserved']} reserved)" if f["reserved"] else "")
            + (f": {', '.join(f['crops'][:4])}" if f["crops"] else "")
            if f
            else "-"
        )
        name = row["name"] + ("" if row["placed"] else " (not placed)")
        lines.append(f"| {name} | {'; '.join(items) or '-'} | {fields} |")

    if combined.flow_links:
        lines += [
            "",
            "## Goods flows between blocks",
            "",
            (
                f"The {_TOP_LINKS} heaviest of {len(combined.flow_links)} (all in "
                "combined.json). Tiles apart: free tiles between the two block "
                "frames."
            ),
            "",
            "| From | To | Goods / h | Tiles apart |",
            "| --- | --- | --- | --- |",
        ]
        for link in combined.flow_links[:_TOP_LINKS]:
            apart = "-" if link.distance is None else str(link.distance)
            lines.append(
                f"| {names[link.source]} | {names[link.target]} | "
                f"{link.per_hour:.2f} | {apart} |"
            )

    lines += ["", "## Expansion", ""]
    reserved = sorted((s.location.name, s.reserved) for s in layout.stock if s.reserved)
    if reserved:
        lines.append(
            "- Space kept in the blocks for copies not owned yet or unlocked within "
            f"{combined.lookahead} levels: "
            + ", ".join(f"{n} {r}" for n, r in reserved)
        )
    for u in combined.upcoming:
        lines.append(
            f"- Level {u.unlock_level}: {u.name}, {_KIND_TEXT[u.kind]} "
            f"({u.count}, about {u.tiles} tiles)"
        )
    if not combined.upcoming:
        lines.append(
            f"- No unlocks in the data for the next {combined.lookahead} levels."
        )
    if combined.free_tiles is not None:
        lines.append(
            f"- Free usable tiles outside the blocks: {combined.free_tiles}; new "
            f"buildings need about {combined.new_building_tiles}."
        )
    if combined.warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in combined.warnings]

    lines += ["", _demote(layout_to_markdown(layout))]
    lines += ["", _demote(schedule_to_markdown(combined.run.schedule, dataset))]
    return "\n".join(lines).rstrip("\n") + "\n"


def _demote(markdown: str) -> str:
    """Move every heading one level down, so a report fits under this one."""
    out = []
    fenced = False
    for line in markdown.rstrip("\n").split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        out.append("#" + line if line.startswith("#") and not fenced else line)
    return "\n".join(out)
