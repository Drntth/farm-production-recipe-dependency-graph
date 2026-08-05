"""
Tests for multi-level proximity, production-block clustering and centrality.
"""

from __future__ import annotations

import networkx as nx
import pytest

from src.graph import build_graph
from src.graph.analysis import (
    analysis_summary,
    centrality_report,
    dependency_path,
    detect_production_blocks,
    has_dependency_path,
    location_proximity_graph,
)
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
def dairy_graph() -> nx.DiGraph:
    """field → soybean → feed_mill → cow_feed; cow_pasture → milk → dairy → cream."""
    locations = [
        Location(id="field", name="Field", type=LocationType.FIELD, unlock_level=1),
        Location(
            id="feed_mill",
            name="Feed Mill",
            type=LocationType.PRODUCTION,
            unlock_level=3,
        ),
        Location(
            id="cow_pasture",
            name="Cow Pasture",
            type=LocationType.ANIMAL,
            unlock_level=6,
        ),
        Location(
            id="dairy", name="Dairy", type=LocationType.PRODUCTION, unlock_level=6
        ),
        Location(
            id="bakery", name="Bakery", type=LocationType.PRODUCTION, unlock_level=4
        ),
    ]
    resources = [
        Resource(
            id="soybean",
            name="Soybean",
            type=ResourceType.CROP,
            unlock_level=5,
            source_location_id="field",
        ),
        Resource(
            id="wheat",
            name="Wheat",
            type=ResourceType.CROP,
            unlock_level=1,
            source_location_id="field",
        ),
        Resource(
            id="cow_feed",
            name="Cow Feed",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=6,
        ),
        Resource(
            id="milk",
            name="Milk",
            type=ResourceType.ANIMAL_PRODUCT,
            unlock_level=6,
            source_location_id="cow_pasture",
        ),
        Resource(
            id="cream",
            name="Cream",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=6,
        ),
        Resource(
            id="bread",
            name="Bread",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=4,
        ),
    ]
    recipes = [
        Recipe(
            id="cow_feed",
            name="Cow Feed",
            location_id="feed_mill",
            unlock_level=6,
            inputs=[RecipeInput(resource_id="soybean", amount=2)],
            output=RecipeOutput(resource_id="cow_feed", amount=1),
        ),
        Recipe(
            id="cream",
            name="Cream",
            location_id="dairy",
            unlock_level=6,
            inputs=[RecipeInput(resource_id="milk", amount=1)],
            output=RecipeOutput(resource_id="cream", amount=1),
        ),
        Recipe(
            id="bread",
            name="Bread",
            location_id="bakery",
            unlock_level=4,
            inputs=[RecipeInput(resource_id="wheat", amount=3)],
            output=RecipeOutput(resource_id="bread", amount=1),
        ),
    ]
    return build_graph(DataSet(locations, resources, recipes))


def test_proximity_graph_has_only_locations(dairy_graph: nx.DiGraph) -> None:
    P = location_proximity_graph(dairy_graph, max_hops=1)
    assert all(P.nodes[n].get("kind") == "location" for n in P.nodes)
    assert "soybean" not in P
    assert "milk" not in P


def test_proximity_direct_couplings(dairy_graph: nx.DiGraph) -> None:
    P = location_proximity_graph(dairy_graph, max_hops=1)
    assert P.has_edge("field", "feed_mill")
    assert P.has_edge("cow_pasture", "dairy")
    assert P.has_edge("field", "bakery")


def test_proximity_multi_level_adds_edges(dairy_graph: nx.DiGraph) -> None:
    P1 = location_proximity_graph(dairy_graph, max_hops=1)
    P3 = location_proximity_graph(dairy_graph, max_hops=3)
    assert P3.number_of_edges() >= P1.number_of_edges()


def test_detect_production_blocks(dairy_graph: nx.DiGraph) -> None:
    blocks = detect_production_blocks(dairy_graph, max_hops=2)
    assert len(blocks) >= 1
    all_locs = set()
    for b in blocks:
        assert b["size"] == len(b["locations"])
        all_locs.update(b["locations"])
    expected = {"field", "feed_mill", "cow_pasture", "dairy", "bakery"}
    assert expected.issubset(all_locs)


def test_centrality_report(dairy_graph: nx.DiGraph) -> None:
    report = centrality_report(dairy_graph, top_n=5)
    assert "degree" in report and "betweenness" in report
    assert len(report["degree"]) <= 5
    assert report["degree"][0]["score"] >= report["degree"][-1]["score"]


def test_dependency_path(dairy_graph: nx.DiGraph) -> None:
    path = dependency_path(dairy_graph, "field", "cow_feed")
    assert path is not None
    assert path[0] == "field"
    assert path[-1] == "cow_feed"
    assert has_dependency_path(dairy_graph, "cow_pasture", "cream")
    assert dependency_path(dairy_graph, "dairy", "field") is None


def test_analysis_summary_structure(dairy_graph: nx.DiGraph) -> None:
    summary = analysis_summary(dairy_graph, top_n=5)
    assert "production_blocks" in summary
    assert "centrality" in summary
    assert "proximity_graph" in summary
    assert summary["proximity_graph"]["location_count"] == 5
