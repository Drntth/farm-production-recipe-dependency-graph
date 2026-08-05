# Farm Production Graph

A graph-based dependency analysis and layout planning system for farming and crafting production chains.

The project converts locations, resources, and recipes into a weighted directed graph.
The generated graph supports production dependency analysis, identification of important nodes, clustering of related production processes, and optimized farm layout planning.

The primary use case is modeling **Hay Day** production chains.
The architecture is designed so that the same data model can later power a second tool (Production Planner) and eventually a full-stack application.

---

## Project Goals (Two Complementary Tools)

### 1. Layout Planner (current focus - v0.x)

**Goal:** Help design an efficient farm layout.

- Builds a weighted dependency graph from recipes.
- Shows which locations and resources are tightly coupled.
- Suggests production “blocks” (clusters) that should be placed close to each other.
- Helps decide how many fields should be near a given location and which other locations belong to the same processing group.

Implementation stage: **JSON data + pure Python scripts**.

### 2. Production Planner (planned - later v0.x / v0.5+)

**Goal:** Calculate an optimized production schedule.

- Given a player level, barn/silo capacity and current orders (truck, boat, town, events).
- Determines what to plant, harvest and put into production machines.
- Calculates exact quantities that should be kept in the barn so that orders can be fulfilled efficiently.

Will reuse the same core data model and later share the PostgreSQL database with the Layout Planner.

### 3. Version 1.0 - Full Application Platform

Full-stack application that unifies both tools behind a web UI, with persistent storage and interactive visualization.

---

## Features

### Current features (Layout Planner - v0.x)

- JSON-based data input (locations, resources, recipes)
- Recipe-driven weighted dependency graph generation (NetworkX DiGraph)
- Three edge kinds: PRODUCES, CONSUMES, OUTPUTS (source-location edges included)
- Stoichiometry-based edge weights (input/output ratio)
- Directed graph representation ready for clustering & layout heuristics
- Multiple export formats (planned / next step):
  - JSON
  - CSV
  - GraphML
- Data loading from Hay Day Fandom Wiki via a dedicated scraper script

### Planned features

**Layout Planner enhancements**:

- Dependency clustering / production block detection
- Bottleneck detection
- Layout suggestion heuristics

**Production Planner**:

- Order-aware quantity calculation
- Barn / silo capacity constraints
- Planting & production schedule generation

**Version 1.0**:

- Interactive graph visualization
- Database-backed data management
- Web-based user interface
- Unified Layout + Production Planner experience

---

## Project Status

### Version 0.x - Layout Planner (Python)

Standalone Python application focused on the Layout Planner.

Architecture:

```text
Hay Day Fandom Wiki
        |
        v
Scraper script (parameterizable)
        |
        v
JSON data (data/*.json)
        |
        v
Python graph generator
        |
        v
Weighted dependency graph
        |
        +--> JSON export
        +--> CSV export
        +--> GraphML export
```

Purpose of the current version:

- Validate the normalized data model
- Test dependency calculation and weighting algorithms
- Generate usable production graphs for layout analysis
- Establish the foundation for the Production Planner and v1.0

Data is currently limited to **level 52** (hard-coded in the JSON files).
Level-parameterized generation (`--max-level`) will be added later when the full dataset and the Production Planner are introduced.

---

## Version 1.0 - Full Application Platform

The planned 1.0 architecture replaces the standalone scripts with a full-stack application.
Both the Layout Planner and the Production Planner will share the same PostgreSQL database.

Architecture:

```text
TypeScript Frontend
        |
        v
Java Backend API
        |
        v
PostgreSQL Database
        |
        v
Graph calculation + planning engine
```

Planned technologies:

| Component        | Technology      |
| ---------------- | --------------- |
| Frontend         | TypeScript      |
| Backend          | Java            |
| Database         | PostgreSQL      |
| API              | REST            |
| Graph / Planning | Backend service |

The goal of version 1.0 is to provide:

- Persistent shared data storage
- User interface for both planners
- Editable production graphs
- Dynamic graph calculation and layout suggestions
- Production schedule optimization
- Visualization tools
- Scalable architecture

---

## Architecture

### Current architecture (Layout Planner - v0.x)

```text
Data Layer
    |
    v
Graph Processing Layer
    |
    v
Export Layer
```

#### Data Layer

Stores production-chain entities in normalized JSON files.
These files are designed to map directly to future database tables (shared by both planners in v1.0).

Current files:

- `data/locations.json`
- `data/resources.json`
- `data/recipes.json`

Data source: **Hay Day Fandom Wiki** (scraped by a dedicated Python script).
Only the fields required by the Layout Planner are mandatory at this stage.

---

#### Graph Processing Layer

Responsible for:

- loading input data
- creating graph nodes (locations + resources)
- generating relationships from recipes
- calculating connection weights (including multi-level propagation)

---

#### Export Layer

Generates:

- JSON
- CSV
- GraphML

The export layer is separated from graph generation to allow future integrations.

---

## Data Model

The system uses three main entities.  
All identifiers are **snake_case English**.

All goods (including intermediate items such as Bread and final items such as cakes) are modeled as **resources**.  
Whether an item is intermediate or final is derived from the dependency graph (presence of outgoing edges).

### Locations

Everything that occupies space on the farm (production locations, animal shelters, fields, trees, bushes, storage…).
Mandatory fields:

```json
{
  "id": "dairy",
  "name": "Dairy",
  "type": "production",
  "unlock_level": 6
}
```

Allowed `type` values: `production`, `animal`, `field`, `tree`, `bush`, `storage`, `other`.

### Resources

Crops, animal products, intermediate/processed goods and ores.
Mandatory fields:

```json
{
  "id": "milk",
  "name": "Milk",
  "type": "animal_product",
  "unlock_level": 6,
  "source_location_id": "cow_pasture"
}
```

`source_location_id` is **mandatory** for `crop`, `animal_product` and `ore`.
Allowed `type` values: `crop`, `animal_product`, `processed_material`, `raw_material`, `ore`.

### External Resources

Some recipe inputs from the wiki represent external dependencies rather than farm-produced resources (for example vouchers or premium materials).

These items are allowed as recipe inputs but are not required to exist in `resources.json`, because they do not participate in the internal farm production dependency chain.

### Recipes

Only transformations that happen inside production locations.
Animal products and raw crops are resources (produced by their source location), not recipes.

Recipes may contain zero or more inputs.
Most production recipes consume resources, but some wiki-defined production entries (such as lure crafting) have no explicit input requirements.

Mandatory fields:

```json
{
  "id": "cream",
  "name": "Cream",
  "location_id": "dairy",
  "unlock_level": 6,
  "inputs": [
    {
      "resource_id": "milk",
      "amount": 1
    }
  ],
  "output": {
    "resource_id": "cream",
    "amount": 1
  }
}
```

### Graph Generation

The system creates a **directed weighted dependency graph** (NetworkX `DiGraph`) that includes both production transformations and the origin of raw resources.

#### Technology choice

| Decision              | Choice                         | Rationale                                                                                                                                                                                      |
| --------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Graph library         | **NetworkX** (`DiGraph`)       | Mature, pure-Python, rich algorithm suite (shortest paths, centrality, community detection), native GraphML export, spring/Kamada-Kawai layouts usable later for visual proximity suggestions. |
| Node identity         | Original snake_case entity ids | Locations and resources already have unique ids; collisions are detected at build time.                                                                                                        |
| Edge multiplicity     | Single edge per ordered pair   | If several recipes would create the same edge, weights are summed and recipe ids collected.                                                                                                    |
| External dependencies | Silently omitted               | Vouchers / premium items never become nodes; they do not participate in farm-layout decisions.                                                                                                 |

#### Node model

Every `Location` and every `Resource` becomes a node.

| Attribute            | Present on       | Description                           |
| -------------------- | ---------------- | ------------------------------------- |
| `kind`               | all              | `"location"` or `"resource"`          |
| `id`                 | all              | Original entity id                    |
| `name`               | all              | Human-readable name                   |
| `type`               | all              | `LocationType` / `ResourceType` value |
| `unlock_level`       | all              | Player level required                 |
| `source_location_id` | resources (raw)  | Producing location                    |
| `max_slots`          | locations (opt.) | Production slots                      |

#### Edge model - three semantic kinds

```text
                    ┌──────────────────────────────────────────────┐
                    │                                              │
   location  ──PRODUCES──►  resource  ──CONSUMES──►  location  ──OUTPUTS──►  resource …
   (field)                  (soybean)                (feed_mill)             (cow_feed)
```

1. **PRODUCES** (`location → resource`)  
   Created for every resource that has a `source_location_id`.  
   Captures “this field / animal shelter / mine produces this raw good”.

2. **CONSUMES** (`resource → location`)  
   Created for every recipe input that exists in `resources.json`.  
   Captures “this resource is consumed at this production building”.

3. **OUTPUTS** (`location → resource`)  
   Created for every recipe output.  
   Captures “this building produces this (processed) good”.

Together they form continuous dependency paths, e.g.:

```text
field ─PRODUCES→ soybean ─CONSUMES→ feed_mill ─OUTPUTS→ cow_feed
     ─CONSUMES→ cow_pasture ─OUTPUTS→ milk ─CONSUMES→ dairy
     ─OUTPUTS→ cream / butter / cheese
     ─CONSUMES→ ice_cream_maker / cake_oven …
```

#### Weighting rules (v0.1)

Higher weight ⇒ stronger coupling ⇒ the two nodes (or their owning locations) should be placed closer together on the farm map.

| Edge kind | Weight formula                                | Default                               |
| --------- | --------------------------------------------- | ------------------------------------- |
| PRODUCES  | constant                                      | `1.0`                                 |
| CONSUMES  | `input_amount / output_amount` (recipe ratio) | e.g. 3 milk → 1 cheese ⇒ weight `3.0` |
| OUTPUTS   | constant                                      | `1.0`                                 |

Rationale for the stoichiometry-based CONSUMES weight: a recipe that consumes three units of an upstream good pulls that good’s producing location more strongly toward the processing building than a 1-to-1 recipe.

Edge attributes stored on every edge:

- `edge_type` - one of `produces` / `consumes` / `outputs`
- `weight` - float (see table above)
- `amount` - the recipe quantity (or 1 for PRODUCES)
- `recipe_id` - present on CONSUMES / OUTPUTS edges
- `ratio` - present on CONSUMES edges (`input/output`)

#### Why this model supports farm-layout planning

- **Direct proximity signals** - high-weight CONSUMES edges tell the layout engine that a resource’s source location and the consuming building belong together.
- **Cluster detection** - community-detection algorithms (Louvain, label propagation …) run on the undirected projection of the graph will surface natural production blocks (Dairy cluster, Bakery cluster, Feed + Animal cluster, etc.).
- **Distance usable by later optimisers** - shortest-path lengths or effective multi-level weights between location pairs become the “desired distance” cost term in a placement heuristic.
- **Level-aware** - the same builder accepts a `DataSet` already filtered by `--max-level`, so a level-30 farm and a level-52 farm produce different graphs.
- **Reusable by Production Planner** - the identical graph (plus quantity annotations) will later drive schedule optimisation.

#### Future extensions (already designed for)

- Multi-level weight propagation (sum / max of path weights between any two locations).
- Collapse of resource nodes into a pure location-location proximity graph for the placement solver.
- Bottleneck detection via betweenness centrality on the weighted graph.
- Integration with force-directed layouts (`spring_layout`, `kamada_kawai_layout`) for interactive visualisation.

#### Usage (code)

```python
from pathlib import Path
from src.loaders import load_data
from src.graph import build_graph, graph_summary

ds = load_data(Path("data"), max_level=52)
G = build_graph(ds)
print(graph_summary(G))
# DiGraph(nodes=… [locations=…, resources=…], edges=…)
```

---

### Data Source & Scraper

All production data is sourced from the Hay Day Fandom Wiki:

- <https://hayday.fandom.com/wiki/Goods_List>
- <https://hayday.fandom.com/wiki/Production_locations_List>
- Individual location and product pages

A dedicated Python scraper script (located under `src/scraper/`) is responsible for:

- fetching the relevant wiki pages
- extracting locations, resources and recipes
- normalizing the data into the JSON format expected by the Layout Planner
- writing the files into `data/`

The scraper is parameterizable (target level, which entity types to extract, etc.).
Current data files are limited to **level 52**.

---

### Export Formats

Supported:

#### JSON

Used for:

- web visualization
- application communication

#### CSV

Used for:

- spreadsheet analysis
- manual inspection

#### GraphML

Used for:

- Gephi
- yEd
- Cytoscape
- NetworkX

### Installation

Requirements:

- Python 3.11+

Install dependencies:

```bash
pip install -r requirements.txt
```

---

### Testing

Run the full test suite:

```bash
python -m pytest tests/
```

Or individually:

```bash
python -m pytest tests/test_json_loader.py
python -m pytest tests/test_graph_builder.py
```

**Loader tests** verify:

- JSON files can be loaded
- Pydantic models validate the data
- Referential integrity rules are applied
- External recipe inputs are handled correctly

**Graph-builder tests** verify:

- Correct node counts and attributes for locations & resources
- PRODUCES edges for every raw resource (`source_location_id`)
- CONSUMES / OUTPUTS edges derived from recipes
- Stoichiometry weights (`input_amount / output_amount`)
- Continuous dependency paths (e.g. field → … → cream)
- External inputs are skipped without creating nodes

---

### Usage

Example:

```bash
python -m src.main
```

Filter by maximum unlock level:

```bash
python -m src.main --max-level 52
```

Only locations, resources and recipes whose `unlock_level <= 52` are included in the generated graph.

Update data from the wiki (example):

```bash
python -m src.scraper --max-level 52
```

Output:

```bash
output/
├── graph.json
├── graph.csv
└── graph.graphml
```

### Project Structure

```bash
farm-production-recipe-dependency-graph/
├── data/
│   ├── locations.json                 # farm locations (buildings, fields, animals…)
│   ├── resources.json                 # crops, animal products, processed goods, ores
│   ├── recipes.json                   # production transformations inside locations
│   └── examples/
│       ├── locations.example.json     # minimal example data for tests / docs
│       ├── resources.example.json
│       └── recipes.example.json
├── output/                            # generated graph exports land here
├── src/
│   ├── exporters/
│   │   ├── csv_exporter.py
│   │   ├── graphml_exporter.py
│   │   └── json_exporter.py
│   ├── graph/
│   │   ├── graph_builder.py           # build_graph(DataSet) → nx.DiGraph
│   │   ├── relationship.py            # EdgeType enum + edge attribute helpers
│   │   └── weighting.py               # weight calculation rules (stoichiometry)
│   ├── loaders/
│   │   └── json_loader.py             # load_data() → validated DataSet
│   ├── models/
│   │   ├── location.py                # Location + LocationType (Pydantic)
│   │   ├── recipe.py                  # Recipe, RecipeInput, RecipeOutput (Pydantic)
│   │   └── resource.py                # Resource + ResourceType (Pydantic)
│   ├── scraper/                       # Hay Day Fandom Wiki scraper
│   │   ├── parsers/
│   │   │   ├── locations.py           # parse production locations list pages
│   │   │   ├── recipes.py             # parse recipe / goods pages
│   │   │   └── resources.py           # parse resource / goods pages
│   │   ├── cli.py                     # scraper CLI argument parsing
│   │   ├── normalizer.py              # normalize raw wiki data → schema
│   │   ├── wiki_client.py             # HTTP client for Fandom wiki pages
│   │   └── writer.py                  # write normalized JSON into data/
│   └── main.py                        # CLI entry: load → build graph
├── tests/
│   ├── test_json_loader.py            # loader + referential integrity tests
│   └── test_graph_builder.py          # graph construction & weighting tests
├── LICENSE
├── README.md
└── requirements.txt
```

### Implemented: Data models & loaders

The core entities are defined as **Pydantic v2** models under `src/models/`:

| Module        | Class                                   | Notes                                                          |
| ------------- | --------------------------------------- | -------------------------------------------------------------- |
| `location.py` | `Location`, `LocationType`              | Enum-validated type, snake_case id                             |
| `resource.py` | `Resource`, `ResourceType`              | `source_location_id` mandatory for crop / animal_product / ore |
| `recipe.py`   | `Recipe`, `RecipeInput`, `RecipeOutput` | Supports recipes with zero or more inputs                      |

The loader (`src/loaders/json_loader.py`) provides:

- `load_data(data_dir, max_level=None) → DataSet`
- Automatic Pydantic validation
- Referential integrity validation
  - location references must exist
  - recipe outputs must exist as resources
  - external recipe inputs (e.g. vouchers, premium items) are allowed
- Optional `--max-level` filtering
- Fast id-based lookup via `DataSet.locations / .resources / .recipes`

Example usage:

```python
from pathlib import Path
from src.loaders import load_data

ds = load_data(Path("data"), max_level=52)
print(ds.summary())
# DataSet(locations=…, resources=…, recipes=…)
```

### Development Priorities (current phase)

- [x] Finalize minimal JSON data model for Layout Planner (`locations`, `resources`, `recipes`)
- [x] Make `source_location_id` mandatory for raw resources
- [x] Implement data models + JSON loaders (`src/models/`, `src/loaders/`)
- [x] Implement / refine the wiki scraper according to the final schema
- [x] Implement graph generation that includes source-location → resource edges
- [ ] Add exporters (JSON, CSV, GraphML)
- [ ] Validate graph quality with real Hay Day production chains up to level 52
- Keep JSON files in 3NF-ready shape for later shared PostgreSQL usage

### Roadmap

#### v0.1 - Layout Planner foundation

- [x] Initial Python project structure
- [x] Pydantic data models (`Location`, `Resource`, `Recipe`)
- [x] JSON data loading + referential integrity (`src/loaders`)
- [x] Support recipes without explicit inputs
- [x] Support external recipe dependencies
- [x] Basic graph generation (NetworkX DiGraph, PRODUCES / CONSUMES / OUTPUTS edges, stoichiometry weights)
- [x] Wiki scraper (level 52)

#### v0.3 - Layout Planner usable

- Weighted multi-level dependencies
- Clustering / production block detection
- Graph exports and basic analysis

#### v0.5 - Production Planner (script level)

- Full (or significantly extended) dataset
- Level-parameterized generation
- Quantity & capacity aware planning scripts
- Shared data model preparation

#### v1.0 - Full Application Platform

- Java backend + PostgreSQL (shared DB for both planners)
- TypeScript frontend
- Interactive visualization
- Unified Layout + Production Planner experience
- Persistent data management

### License

MIT License

### Disclaimer

This project is an independent fan-made analysis tool.

Hay Day and related assets are properties of Supercell.
