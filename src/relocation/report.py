"""Relocation plan as ``relocation.json`` and ``relocation.md``."""

from __future__ import annotations

from typing import Any

from src.layout.farm_map import CurrentItem

from .relocate import RelocationPlan, Target


def _target(t: Target) -> dict[str, Any]:
    x, y, w, h = t.rect
    return {
        "location_id": t.location_id,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "rotated": t.rotated,
    }


def _current(c: CurrentItem) -> dict[str, Any]:
    if not c.is_placed:
        return {"location_id": c.id, "count": c.count}
    return {
        "location_id": c.id,
        "x": c.x,
        "y": c.y,
        "width": c.width,
        "height": c.height,
    }


def _by_block(plan: RelocationPlan, targets: list[Target]) -> list[dict[str, Any]]:
    """Targets grouped by block, in the layout's block order."""
    return [
        {"block": bid, "name": name, "items": items}
        for bid, name in plan.blocks
        if (items := [_target(t) for t in targets if t.block_id == bid])
    ]


def new_slot_note(plan: RelocationPlan) -> str | None:
    if not plan.new_slot_simpler:
        return None
    return (
        f"Only {len(plan.keep)} item(s) stay and {plan.stored_placed} have to be "
        "stored: a new layout slot is simpler. It starts empty (only fixed buildings "
        "remain), so place every item of the keep and place lists there."
    )


def relocation_to_dict(plan: RelocationPlan, layout_file: str) -> dict[str, Any]:
    return {
        "layout_file": layout_file,
        "level": plan.level,
        "summary": {
            "current_copies": plan.current_copies,
            "keep": len(plan.keep),
            "store": sum(c.count for c in plan.store),
            "place": len(plan.place),
            "reserved": len(plan.reserved),
            "not_in_layout": sum(plan.surplus.values()),
            "not_owned": sum(plan.missing.values()),
        },
        "new_slot_simpler": plan.new_slot_simpler,
        "note": new_slot_note(plan),
        "keep": [_target(t) | {"block": t.block_id} for t in plan.keep],
        "store": [_current(c) for c in plan.store],
        "place": _by_block(plan, plan.place),
        "reserved": _by_block(plan, plan.reserved),
        "not_in_layout": [
            {"location_id": k, "count": n} for k, n in plan.surplus.items()
        ],
        "not_owned": [{"location_id": k, "count": n} for k, n in plan.missing.items()],
    }


def _pos(x: int, y: int, w: int, h: int) -> str:
    return f"({x}, {y}) {w}x{h}"


# summary key → column of the Markdown summary table
SUMMARY_COLUMNS = {
    "keep": "Keep",
    "store": "Store",
    "place": "Place",
    "reserved": "Reserved",
    "not_in_layout": "Not in layout",
    "not_owned": "Not owned",
}
NO_CURRENT_NOTE = (
    "The farm map has no current farm, so every item is listed under Place. "
    "Measure it in tools/farm_map_editor.html (step 8) for keep / store lists."
)


def relocation_to_markdown(plan: RelocationPlan, layout_file: str) -> str:
    level = f", level {plan.level}" if plan.level is not None else ""
    d = relocation_to_dict(plan, layout_file)["summary"]
    lines = [
        "# Relocation plan",
        "",
        f"From the current farm (`current` in the farm map) to `{layout_file}`{level}.",
        "Positions are tiles `(x, y) width x height`, as in the farm map.",
        "",
        "| " + " | ".join(SUMMARY_COLUMNS.values()) + " |",
        "|" + "|".join(" ---: " for _ in SUMMARY_COLUMNS) + "|",
        "| " + " | ".join(str(d[k]) for k in SUMMARY_COLUMNS) + " |",
        "",
    ]
    if not plan.current_copies:
        lines += [f"> {NO_CURRENT_NOTE}", ""]
    if note := new_slot_note(plan):
        lines += [f"> {note}", ""]
    names = dict(plan.blocks)

    lines += [
        "## Keep",
        "",
        (
            "Already at their target; leave them. Counted items (fields, trees, "
            "bushes without a position) are never kept: they are stored and placed "
            "again."
        ),
        "",
    ]
    if plan.keep:
        lines += ["| Item | Position | Block |", "| ---- | -------- | ----- |"]
        lines += [
            f"| {t.location_id} | {_pos(*t.rect)} | {names[t.block_id]} |"
            for t in plan.keep
        ]
    else:
        lines.append("Nothing stays where it is.")

    lines += [
        "",
        "## Store",
        "",
        "In Layout Edit Mode, store these one by one or by group.",
        "",
    ]
    if plan.store:
        lines += ["| Item | Copies | Position |", "| ---- | -----: | -------- |"]
        lines += [
            f"| {c.id} | {c.count} | "
            f"{_pos(c.x, c.y, c.width, c.height) if c.is_placed else '-'} |"
            for c in plan.store
        ]
    else:
        lines.append("Nothing to store.")

    lines += ["", "## Place", "", "Take these from storage, block by block.", ""]
    lines += _block_tables(plan, plan.place, "Nothing to place.")

    lines += [
        "",
        "## Reserved space",
        "",
        "Copies the layout plans for later levels: keep these tiles free.",
        "",
    ]
    lines += _block_tables(plan, plan.reserved, "No reserved space.")

    lines += [
        "",
        "## Not in the layout",
        "",
        "Current copies the layout has no place for: they stay in storage.",
        "",
    ]
    lines += _counts(plan.surplus)
    lines += [
        "",
        "## Not owned yet",
        "",
        (
            "Layout copies the current farm does not have (buy or build them, or "
            "complete the current farm in the map editor)."
        ),
        "",
    ]
    lines += _counts(plan.missing)
    return "\n".join(lines) + "\n"


def _block_tables(plan: RelocationPlan, targets: list[Target], empty: str) -> list[str]:
    lines: list[str] = []
    for bid, name in plan.blocks:
        items = [t for t in targets if t.block_id == bid]
        if not items:
            continue
        lines += [f"### {name}", "", "| Item | Position | Rotated |"]
        lines.append("| ---- | -------- | ------- |")
        lines += [
            f"| {t.location_id} | {_pos(*t.rect)} | {'yes' if t.rotated else ''} |"
            for t in items
        ]
        lines.append("")
    return lines[:-1] if lines else [empty]


def _counts(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["None."]
    return ["| Item | Copies |", "| ---- | -----: |"] + [
        f"| {k} | {n} |" for k, n in counts.items()
    ]
