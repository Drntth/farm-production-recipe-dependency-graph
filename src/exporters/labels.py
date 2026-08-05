"""
Human-readable labels for graph nodes / edges.

Used by all exporters so that visualisation tools (yEd, Gephi, …)
and spreadsheets show meaningful text instead of bare snake_case ids.
"""

from __future__ import annotations

from typing import Any


def node_label(node_id: str, attrs: dict[str, Any]) -> str:
    """
    Build a display label for a node.

    Examples
    --------
    location  →  "Dairy [location]"
    resource with source →  "Milk ← cow_pasture [resource]"
    resource without source →  "Cream [resource]"
    """
    name = attrs.get("name") or node_id
    kind = attrs.get("kind", "")
    source = attrs.get("source_location_id")

    if kind == "resource" and source:
        base = f"{name} ← {source}"
    else:
        base = str(name)

    if kind:
        return f"{base} [{kind}]"
    return base


def edge_label(attrs: dict[str, Any]) -> str:
    """
    Short edge label: edge_type + weight, optionally recipe id.

    Examples
    --------
    "consumes w=3.0"
    "produces"
    "outputs (cream)"
    """
    edge_type = attrs.get("edge_type", "")
    weight = attrs.get("weight")
    recipe_id = attrs.get("recipe_id")

    parts: list[str] = []
    if edge_type:
        parts.append(str(edge_type))
    if weight is not None:
        parts.append(f"w={weight}")
    if recipe_id and "," not in str(recipe_id):
        parts.append(f"({recipe_id})")
    return " ".join(parts) if parts else ""
