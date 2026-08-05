"""
Export a production dependency graph to CSV files.

Produces two files side-by-side:

- ``<stem>_nodes.csv``  - one row per node (includes human-readable ``label``)
- ``<stem>_edges.csv``  - one row per edge (includes human-readable ``label``)

Column sets are stable and include all attributes used by the Layout Planner.
Missing optional attributes appear as empty cells.
"""

from __future__ import annotations

import csv
from pathlib import Path

import networkx as nx

from .labels import edge_label, node_label

_NODE_COLUMNS = [
    "id",
    "label",
    "kind",
    "name",
    "type",
    "unlock_level",
    "source_location_id",
    "max_slots",
    "max_in_barn",
    "description",
]

_EDGE_COLUMNS = [
    "source",
    "target",
    "label",
    "edge_type",
    "weight",
    "amount",
    "recipe_id",
    "ratio",
]


def export_csv(G: nx.DiGraph, path: Path | str) -> tuple[Path, Path]:
    """
    Write *G* as two CSV files derived from *path*.

    If *path* is ``output/graph.csv``, the files will be
    ``output/graph_nodes.csv`` and ``output/graph_edges.csv``.

    Returns ``(nodes_path, edges_path)``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    stem = path.with_suffix("")
    nodes_path = Path(f"{stem}_nodes.csv")
    edges_path = Path(f"{stem}_edges.csv")

    _write_nodes(G, nodes_path)
    _write_edges(G, edges_path)

    return nodes_path.resolve(), edges_path.resolve()


def _write_nodes(G: nx.DiGraph, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_NODE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for node_id, attrs in sorted(G.nodes(data=True), key=lambda x: x[0]):
            row = {
                "id": node_id,
                "label": node_label(node_id, attrs),
                **attrs,
            }
            writer.writerow({col: row.get(col, "") for col in _NODE_COLUMNS})


def _write_edges(G: nx.DiGraph, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_EDGE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for u, v, attrs in sorted(G.edges(data=True), key=lambda x: (x[0], x[1])):
            row = {
                "source": u,
                "target": v,
                "label": edge_label(attrs),
                **attrs,
            }
            writer.writerow({col: row.get(col, "") for col in _EDGE_COLUMNS})
