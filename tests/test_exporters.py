"""
Unit tests for JSON / CSV / GraphML exporters.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import networkx as nx
import pytest

from src.exporters import export_csv, export_graphml, export_json
from src.graph import build_graph
from src.graph.relationship import EdgeType
from src.loaders.json_loader import DataSet
from src.models import (
    Location,
    LocationType,
    Recipe,
    RecipeInput,
    RecipeOutput,
    Resource,
    ResourceType,
)


@pytest.fixture
def small_graph() -> nx.DiGraph:
    locations = [
        Location(id="field", name="Field", type=LocationType.FIELD, unlock_level=1),
        Location(
            id="dairy", name="Dairy", type=LocationType.PRODUCTION, unlock_level=6
        ),
    ]
    resources = [
        Resource(
            id="wheat",
            name="Wheat",
            type=ResourceType.CROP,
            unlock_level=1,
            source_location_id="field",
        ),
        Resource(
            id="cream",
            name="Cream",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=6,
        ),
        Resource(
            id="milk",
            name="Milk",
            type=ResourceType.ANIMAL_PRODUCT,
            unlock_level=6,
            source_location_id="dairy",
        ),
    ]
    recipes = [
        Recipe(
            id="cream",
            name="Cream",
            location_id="dairy",
            unlock_level=6,
            inputs=[RecipeInput(resource_id="milk", amount=1)],
            output=RecipeOutput(resource_id="cream", amount=1),
        ),
    ]
    return build_graph(DataSet(locations, resources, recipes))


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_export_json_structure(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    out = export_json(small_graph, tmp_path / "graph.json")
    assert out.exists()

    data = json.loads(out.read_text(encoding="utf-8"))
    assert "nodes" in data
    assert "edges" in data
    assert "meta" in data

    assert data["meta"]["node_count"] == small_graph.number_of_nodes()
    assert data["meta"]["edge_count"] == small_graph.number_of_edges()
    assert data["meta"]["location_count"] == 2
    assert data["meta"]["resource_count"] == 3

    node_ids = {n["id"] for n in data["nodes"]}
    assert node_ids == set(small_graph.nodes)

    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "edge_type" in edge
        assert "weight" in edge


def test_export_json_labels(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    out = export_json(small_graph, tmp_path / "graph.json")
    data = json.loads(out.read_text(encoding="utf-8"))

    by_id = {n["id"]: n for n in data["nodes"]}
    assert "label" in by_id["dairy"]
    assert "Dairy" in by_id["dairy"]["label"]
    assert "location" in by_id["dairy"]["label"]

    assert "Milk" in by_id["milk"]["label"]
    assert "dairy" in by_id["milk"]["label"]
    assert "resource" in by_id["milk"]["label"]

    for edge in data["edges"]:
        assert "label" in edge


def test_export_json_creates_parent_dirs(
    small_graph: nx.DiGraph, tmp_path: Path
) -> None:
    nested = tmp_path / "a" / "b" / "graph.json"
    out = export_json(small_graph, nested)
    assert out.exists()


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_export_csv_files(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    nodes_p, edges_p = export_csv(small_graph, tmp_path / "graph.csv")
    assert nodes_p.exists()
    assert edges_p.exists()
    assert nodes_p.name == "graph_nodes.csv"
    assert edges_p.name == "graph_edges.csv"


def test_export_csv_node_columns(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    nodes_p, _ = export_csv(small_graph, tmp_path / "g.csv")
    with nodes_p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert reader.fieldnames is not None
        assert "id" in reader.fieldnames
        assert "label" in reader.fieldnames
        assert "kind" in reader.fieldnames
        assert "unlock_level" in reader.fieldnames

    ids = {r["id"] for r in rows}
    assert ids == set(small_graph.nodes)

    milk = next(r for r in rows if r["id"] == "milk")
    assert "Milk" in milk["label"]
    assert "dairy" in milk["label"]


def test_export_csv_edge_columns(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    _, edges_p = export_csv(small_graph, tmp_path / "g.csv")
    with edges_p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert reader.fieldnames is not None
        assert "source" in reader.fieldnames
        assert "target" in reader.fieldnames
        assert "label" in reader.fieldnames
        assert "edge_type" in reader.fieldnames
        assert "weight" in reader.fieldnames

    assert len(rows) == small_graph.number_of_edges()
    types = {r["edge_type"] for r in rows}
    assert EdgeType.PRODUCES.value in types


# ---------------------------------------------------------------------------
# GraphML
# ---------------------------------------------------------------------------


def test_export_graphml_readable(small_graph: nx.DiGraph, tmp_path: Path) -> None:
    out = export_graphml(small_graph, tmp_path / "graph.graphml")
    assert out.exists()
    assert out.stat().st_size > 0

    text = out.read_text(encoding="utf-8")
    assert "yworks.com/xml/graphml" in text
    assert "NodeLabel" in text
    assert "Dairy" in text
    assert "Milk" in text


def test_export_graphml_preserves_attributes(
    small_graph: nx.DiGraph, tmp_path: Path
) -> None:
    out = export_graphml(small_graph, tmp_path / "graph.graphml")
    text = out.read_text(encoding="utf-8")
    assert "edge_type" in text
    assert "produces" in text or "consumes" in text
    assert "source_location_id" in text
