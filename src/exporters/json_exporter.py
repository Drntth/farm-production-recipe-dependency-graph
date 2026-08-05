"""
Export a production dependency graph to JSON.

Format
------
{
  "nodes": [
    {"id": "...", "label": "...", "kind": "location"|"resource", ...},
    ...
  ],
  "edges": [
    {"source": "...", "target": "...", "label": "...", "edge_type": "...", ...},
    ...
  ],
  "meta": { ... }
}

The ``label`` field is a human-readable string suitable for visualisation
(e.g. ``"Milk ← cow_pasture [resource]"``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from .labels import edge_label, node_label


def export_json(G: nx.DiGraph, path: Path | str) -> Path:
    """
    Write *G* to a JSON file at *path*.

    Returns the resolved Path of the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    nodes: list[dict[str, Any]] = []
    for node_id, attrs in G.nodes(data=True):
        entry = {"id": node_id, "label": node_label(node_id, attrs), **attrs}
        nodes.append(entry)

    edges: list[dict[str, Any]] = []
    for u, v, attrs in G.edges(data=True):
        entry = {
            "source": u,
            "target": v,
            "label": edge_label(attrs),
            **attrs,
        }
        edges.append(entry)

    loc_count = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "location")
    res_count = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "resource")

    payload = {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "location_count": loc_count,
            "resource_count": res_count,
        },
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return path.resolve()
