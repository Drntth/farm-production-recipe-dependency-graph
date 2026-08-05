"""
Unit tests for the graph builder.

Uses a minimal in-memory DataSet that mirrors the classic dairy chain:

    field (soybean) → feed_mill → cow_feed → cow_pasture → milk → dairy → cream
"""

from __future__ import annotations

import networkx as nx
import pytest

from src.graph import (
    EdgeType,
    build_graph,
    edges_of_type,
    graph_summary,
    location_nodes,
    resource_nodes,
)
from src.graph.relationship import ATTR_EDGE_TYPE, ATTR_WEIGHT
from src.graph.weighting import consumes_weight, produces_weight
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
def dairy_dataset() -> DataSet:
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
            id="cow_feed",
            name="Cow Feed",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=3,
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
    ]

    recipes = [
        Recipe(
            id="cow_feed",
            name="Cow Feed",
            location_id="feed_mill",
            unlock_level=3,
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
    ]

    return DataSet(locations, resources, recipes)


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_build_graph_node_counts(dairy_dataset: DataSet) -> None:
    G = build_graph(dairy_dataset)
    assert G.number_of_nodes() == 8
    assert set(location_nodes(G)) == {
        "field",
        "feed_mill",
        "cow_pasture",
        "dairy",
    }
    assert set(resource_nodes(G)) == {"soybean", "cow_feed", "milk", "cream"}


def test_node_attributes(dairy_dataset: DataSet) -> None:
    G = build_graph(dairy_dataset)
    assert G.nodes["dairy"]["kind"] == "location"
    assert G.nodes["dairy"]["type"] == "production"
    assert G.nodes["dairy"]["unlock_level"] == 6

    assert G.nodes["milk"]["kind"] == "resource"
    assert G.nodes["milk"]["type"] == "animal_product"
    assert G.nodes["milk"]["source_location_id"] == "cow_pasture"


def test_produces_edges(dairy_dataset: DataSet) -> None:
    G = build_graph(dairy_dataset)
    produces = edges_of_type(G, EdgeType.PRODUCES)

    pairs = {(u, v) for u, v, _ in produces}
    assert pairs == {("field", "soybean"), ("cow_pasture", "milk")}
    for _, _, d in produces:
        assert d[ATTR_WEIGHT] == produces_weight()


def test_consumes_and_outputs_edges(dairy_dataset: DataSet) -> None:
    G = build_graph(dairy_dataset)

    consumes = edges_of_type(G, EdgeType.CONSUMES)
    consume_pairs = {(u, v) for u, v, _ in consumes}
    assert ("soybean", "feed_mill") in consume_pairs
    assert ("milk", "dairy") in consume_pairs

    assert G["soybean"]["feed_mill"][ATTR_WEIGHT] == pytest.approx(
        consumes_weight(2, 1)
    )
    assert G["milk"]["dairy"][ATTR_WEIGHT] == pytest.approx(consumes_weight(1, 1))

    outputs = edges_of_type(G, EdgeType.OUTPUTS)
    output_pairs = {(u, v) for u, v, _ in outputs}
    assert ("feed_mill", "cow_feed") in output_pairs
    assert ("dairy", "cream") in output_pairs


def test_full_dependency_path_exists(dairy_dataset: DataSet) -> None:

    G = build_graph(dairy_dataset)

    assert nx.has_path(G, "field", "cow_feed")

    assert nx.has_path(G, "cow_pasture", "cream")


def test_external_input_skipped() -> None:
    """Recipe inputs that are not present in resources.json are ignored."""
    locations = [
        Location(
            id="lure_workbench",
            name="Lure Workbench",
            type=LocationType.PRODUCTION,
            unlock_level=27,
        )
    ]
    resources = [
        Resource(
            id="red_lure",
            name="Red Lure",
            type=ResourceType.PROCESSED_MATERIAL,
            unlock_level=27,
        )
    ]
    recipes = [
        Recipe(
            id="red_lure",
            name="Red Lure",
            location_id="lure_workbench",
            unlock_level=27,
            inputs=[
                RecipeInput(resource_id="voucher", amount=1),
            ],
            output=RecipeOutput(resource_id="red_lure", amount=1),
        )
    ]

    ds = DataSet(locations, resources, recipes)
    G = build_graph(ds)

    assert "voucher" not in G
    assert G.has_edge("lure_workbench", "red_lure")
    assert not any(
        d.get(ATTR_EDGE_TYPE) == EdgeType.CONSUMES.value
        for _, _, d in G.edges(data=True)
    )


def test_graph_summary(dairy_dataset: DataSet) -> None:
    G = build_graph(dairy_dataset)
    s = graph_summary(G)
    assert "locations=4" in s
    assert "resources=4" in s
    assert "edges=" in s


def test_empty_dataset() -> None:
    G = build_graph(DataSet([], [], []))
    assert G.number_of_nodes() == 0
    assert G.number_of_edges() == 0
