"""
Validate graph quality on representative Hay Day production chains.

These tests lock in level-independent structural invariants:
node/edge consistency, PRODUCES coverage for raw resources, known
dependency paths, stoichiometry weights, and exclusion of external inputs.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from src.graph import build_graph, edges_of_type
from src.graph.relationship import ATTR_EDGE_TYPE, ATTR_WEIGHT, EdgeType
from src.graph.weighting import consumes_weight
from src.loaders.json_loader import DataSet, load_data
from src.models import (
    Location,
    LocationType,
    Recipe,
    RecipeInput,
    RecipeOutput,
    Resource,
    ResourceType,
)

DATA_DIR = Path("data")
HAS_REAL_DATA = (DATA_DIR / "locations.json").exists()


# ---------------------------------------------------------------------------
# Shared fixture – classic dairy / bakery chains (always available)
# ---------------------------------------------------------------------------


@pytest.fixture
def chain_dataset() -> DataSet:
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
    return DataSet(locations, resources, recipes)


@pytest.fixture
def chain_graph(chain_dataset: DataSet) -> nx.DiGraph:
    return build_graph(chain_dataset)


# ---------------------------------------------------------------------------
# Structural invariants (fixture graph)
# ---------------------------------------------------------------------------


def test_node_count_matches_entities(
    chain_dataset: DataSet, chain_graph: nx.DiGraph
) -> None:
    assert chain_graph.number_of_nodes() == (
        len(chain_dataset.locations) + len(chain_dataset.resources)
    )


def test_produces_edges_for_every_raw_resource(chain_graph: nx.DiGraph) -> None:
    produces = {(u, v) for u, v, _ in edges_of_type(chain_graph, EdgeType.PRODUCES)}
    assert ("field", "soybean") in produces
    assert ("field", "wheat") in produces
    assert ("cow_pasture", "milk") in produces


def test_known_dependency_paths(chain_graph: nx.DiGraph) -> None:
    assert nx.has_path(chain_graph, "field", "cow_feed")
    assert nx.has_path(chain_graph, "cow_pasture", "cream")
    assert nx.has_path(chain_graph, "field", "bread")
    # full dairy-side chain pieces
    assert nx.has_path(chain_graph, "milk", "cream")
    assert nx.has_path(chain_graph, "dairy", "cream")


def test_stoichiometry_weights(chain_graph: nx.DiGraph) -> None:
    # soybean(2) → feed_mill for cow_feed(1) ⇒ weight 2.0
    assert chain_graph["soybean"]["feed_mill"][ATTR_WEIGHT] == pytest.approx(
        consumes_weight(2, 1)
    )
    # wheat(3) → bakery for bread(1) ⇒ weight 3.0
    assert chain_graph["wheat"]["bakery"][ATTR_WEIGHT] == pytest.approx(
        consumes_weight(3, 1)
    )
    # milk(1) → dairy for cream(1) ⇒ weight 1.0
    assert chain_graph["milk"]["dairy"][ATTR_WEIGHT] == pytest.approx(
        consumes_weight(1, 1)
    )


def test_external_inputs_not_nodes() -> None:
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
            inputs=[RecipeInput(resource_id="voucher", amount=1)],
            output=RecipeOutput(resource_id="red_lure", amount=1),
        )
    ]
    G = build_graph(DataSet(locations, resources, recipes))
    assert "voucher" not in G
    assert G.has_edge("lure_workbench", "red_lure")


def test_edge_types_only_allowed_values(chain_graph: nx.DiGraph) -> None:
    allowed = {e.value for e in EdgeType}
    for _, _, d in chain_graph.edges(data=True):
        assert d.get(ATTR_EDGE_TYPE) in allowed


# ---------------------------------------------------------------------------
# Real data integration (skipped if data/ not present in CI / sandbox)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_loads_and_builds() -> None:
    ds = load_data(DATA_DIR)
    G = build_graph(ds)

    assert G.number_of_nodes() == len(ds.locations) + len(ds.resources)
    assert G.number_of_edges() > 0

    loc = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "location")
    res = sum(1 for _, d in G.nodes(data=True) if d.get("kind") == "resource")
    assert loc == len(ds.locations)
    assert res == len(ds.resources)


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_level_filter_is_monotonic() -> None:
    """A higher player level never removes nodes or edges from the graph."""
    full = load_data(DATA_DIR)
    top = max(loc.unlock_level for loc in full.location_list)
    previous: nx.DiGraph | None = None
    for level in (10, 25, 40, top):
        G = build_graph(full.filter_by_max_level(level))
        if previous is not None:
            assert set(previous.nodes) <= set(G.nodes)
            assert set(previous.edges) <= set(G.edges)
        previous = G


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_known_paths() -> None:
    G = build_graph(load_data(DATA_DIR))

    # Dairy cluster
    assert nx.has_path(G, "cow_pasture", "cream")
    assert nx.has_path(G, "milk", "dairy")
    # Bakery
    assert nx.has_path(G, "field", "bread") or nx.has_path(G, "wheat", "bread")
    # Feed mill produces feed via recipe OUTPUTS (feeds are processed materials)
    assert "feed_mill" in G
    feed_outputs = [
        v
        for u, v, d in G.edges(data=True)
        if u == "feed_mill" and d.get(ATTR_EDGE_TYPE) == EdgeType.OUTPUTS.value
    ]
    assert feed_outputs, "feed_mill should have OUTPUTS edges to feed products"
    assert any(
        "feed" in v or v.endswith("_feed") or "bucket" in v for v in feed_outputs
    )


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_produces_coverage() -> None:
    """PRODUCES edges exist only for raw resources (crop / animal_product / ore)."""
    ds = load_data(DATA_DIR)
    G = build_graph(ds)
    produces_targets = {
        v
        for u, v, d in G.edges(data=True)
        if d.get(ATTR_EDGE_TYPE) == EdgeType.PRODUCES.value
    }
    raw_types = {
        ResourceType.CROP,
        ResourceType.ANIMAL_PRODUCT,
        ResourceType.ORE,
    }
    for res in ds.resource_list:
        if res.type in raw_types and res.source_location_id:
            assert res.id in produces_targets, (
                f"Raw resource {res.id} missing PRODUCES edge"
            )
        if res.type not in raw_types:
            assert res.id not in produces_targets, (
                f"Processed resource {res.id} should not have PRODUCES edge"
            )


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_real_data_no_external_nodes() -> None:
    G = build_graph(load_data(DATA_DIR))
    for external in ("voucher", "diamond"):
        assert external not in G
