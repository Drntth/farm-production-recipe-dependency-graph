# Farm Production Graph

A graph-based system for analysing Hay Day production chains, designing farm layouts around reusable production blocks, and generating capacity-aware production schedules.

The system converts locations, resources and recipes into a weighted directed graph. From this graph it identifies tightly coupled production blocks, supports expansion-friendly farm arrangement, and (using only static player data) produces practical production quantities and login schedules.

Planning is organised in two layers:

- **Functional planning** (always active) - production logic, blocks, quantities, schedules, capacities and processing order.
- **Design planning** (optional) - decorative elements, walkable paths between blocks, and aesthetic placement that still respects the functional constraints.

---

## 1. Layout Planner

### Purpose

Help the player design an efficient and expandable farm layout by discovering natural groups of buildings and fields that belong together.

### How it works

1. Loads the normalised JSON data (locations, resources, recipes).
2. Builds a weighted directed dependency graph with three edge kinds:
   - PRODUCES (location → resource)
   - CONSUMES (resource → location, weight = input/output ratio)
   - OUTPUTS (location → resource)
3. Derives a location-proximity graph (multi-level weight propagation with decay).
4. Detects **production blocks** via community detection on the proximity graph.

A production block is a movable logical unit, for example:

- 1× Dairy
- related Cow Pasture(s)
- Feed Mill
- the appropriate number of fields

### Evolution

| Horizon     | Output                                                                                                                                                                                                                             |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Short term  | Weighted graph + detected production blocks                                                                                                                                                                                        |
| Medium term | Explicit block definitions that can be placed relative to each other                                                                                                                                                               |
| Long term   | Complete farm layout with relative positions and distances, expansion-friendly so the farm does not need full rebuilds at every level. When Design planning is enabled, space is also reserved for paths and optional decorations. |

---

## 2. Production Planner

### Purpose

Produce a sustainable production plan and a practical action/login schedule for a given player level, using only static data.

### Inputs (static only)

- Player level
- Barn capacity
- Silo capacity
- Maximum available fields, animal shelters, animals and production buildings at that level
- Optional current progress (owned counts, machine star levels / unlocked slots)

Live truck, boat, town or event orders are intentionally ignored.

### Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested login frequency derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

### Data requirements

Timing data (growth time, production time), maximum counts per level, and machine slot information must be present in the data model (see Data Model section).

---

## 3. Combiner / Layout Finetuner

### Purpose

Merge the results of the Layout Planner and the Production Planner into one coordinated, usable farm plan.

### How it works

- Takes production blocks and the recommended quantities/schedule.
- Places the blocks in a logical order that respects the A→B processing flow.
- Applies expansion-friendly rules (leave room for later buildings and animals).
- When **Design planning** is enabled:
  - reserves walkable paths between blocks and key producers
  - optionally inserts decorative elements inside or around blocks
- Produces a single combined output (textual description, data file, and later visual representations).

Functional planning is always present. Design planning is a selectable option.

---

## Data Model

All identifiers are snake_case English.  
The model is kept close to 3NF so the same structure can later be loaded into PostgreSQL.

### locations.json

Everything that occupies space on the farm (production buildings, animal shelters, fields, trees, bushes, storage…).

```json
{
  "id": "dairy",
  "name": "Dairy",
  "type": "production",
  "unlock_level": 6
}
```

Allowed `type` values: `production`, `animal`, `field`, `tree`, `bush`, `storage`, `other`.

### resources.json

Crops, animal products, intermediate/processed goods and ores.

```json
{
  "id": "milk",
  "name": "Milk",
  "type": "animal_product",
  "unlock_level": 6,
  "source_location_id": "cow_pasture"
}
```

`source_location_id` is mandatory for `crop`, `animal_product` and `ore`.  
Allowed `type` values: `crop`, `animal_product`, `processed_material`, `raw_material`, `ore`.

### recipes.json

Transformations that happen inside production locations.  
Animal products and raw crops are resources, not recipes.

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

Recipes may contain zero or more inputs. External/premium inputs (vouchers, diamonds, etc.) are allowed but never become graph nodes.

### level_limits.json

Maximum number of fields, animal shelters, animals and production buildings available at each player level.  
Kept in a separate file to preserve 3NF.

### Timing and capacity fields

- `growth_time_minutes` on resources (crops)
- `production_time_minutes` on recipes
- `max_slots` / slot-related data on locations
- Player-specific progress (owned counts, star levels, unlocked slots) lives in a separate player-config file, not in the shared data.

### External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect farm-layout decisions.

---

## Graph Model

The system builds a directed weighted dependency graph (NetworkX `DiGraph`).

### Nodes

Every Location and every Resource becomes a node.

| Attribute            | Present on       | Description                       |
| -------------------- | ---------------- | --------------------------------- |
| `kind`               | all              | `"location"` or `"resource"`      |
| `id`                 | all              | Original entity id                |
| `name`               | all              | Human-readable name               |
| `type`               | all              | LocationType / ResourceType value |
| `unlock_level`       | all              | Player level required             |
| `source_location_id` | resources (raw)  | Producing location                |
| `max_slots`          | locations (opt.) | Production slots                  |

### Edges - three semantic kinds

```text
location  ──PRODUCES──►  resource  ──CONSUMES──►  location  ──OUTPUTS──►  resource
(field)                  (soybean)                (feed_mill)             (cow_feed)
```

1. **PRODUCES** (`location → resource`)  
   Created for every resource that has a `source_location_id`.  
   Captures “this field / animal shelter / mine produces this raw good”.

2. **CONSUMES** (`resource → location`)  
   Created for every recipe input that exists in `resources.json`.  
   Weight = `input_amount / output_amount` (stoichiometry).  
   Captures “this resource is consumed at this production building”.

3. **OUTPUTS** (`location → resource`)  
   Created for every recipe output.  
   Captures “this building produces this (processed) good”.

### Weighting rules

| Edge kind | Weight formula               | Default  |
| --------- | ---------------------------- | -------- |
| PRODUCES  | constant                     | 1.0      |
| CONSUMES  | input_amount / output_amount | e.g. 3.0 |
| OUTPUTS   | constant                     | 1.0      |

Higher weight means stronger coupling → the two locations should be placed closer together on the farm.

### Why this model supports layout planning

- High-weight CONSUMES edges give direct proximity signals.
- Community detection on the undirected location-proximity graph yields natural production blocks.
- Shortest-path lengths and multi-level weights become the “desired distance” cost for later placement heuristics.
- The same builder accepts a level-filtered `DataSet`, so different player levels produce different graphs.
- The identical graph (plus quantity annotations) is later reused by the Production Planner and the Combiner.

### Analysis capabilities (already implemented)

- Location proximity graph with multi-level hop propagation and decay
- Production-block detection (Louvain / community detection)
- Degree and betweenness centrality (bottleneck ranking)
- Dependency path queries
- Full analysis payload written to `output/analysis.json`

---

## Roadmap

### v0.3 - Layout Planner usable (done)

- [x] Weighted multi-level proximity
- [x] Production-block detection
- [x] Centrality and path analysis
- [x] JSON / CSV / GraphML exporters
- [x] Wiki scraper (level 52)

### v0.5 - Production Planner foundation

- [ ] Review all relevant wiki data
- [ ] Extend the JSON model with timing and capacity fields while keeping 3NF
- [ ] Introduce `level_limits.json`
- [ ] Capacity model (barn, silo, fields, animals, machine slots)
- [ ] Steady-state quantity calculation tuned to barn/silo limits
- [ ] Basic ordered action list
- [ ] Suggested login frequency from critical growth/processing times
- [ ] `output/schedule.json` export
- [ ] Unit tests for the new planner modules

### v0.6 - Richer Production Planner

- [ ] Machine star-level and unlocked-slot awareness
- [ ] Improved critical-path timing
- [ ] Support for player-config files (owned buildings/animals, current stars)
- [ ] Additional tests and validation against known level-52 chains

### v0.7 - Production blocks as first-class units

- [ ] Explicit, named production-block definitions (Dairy block, Bakery block, Feed+Animals block, …)
- [ ] Expansion-friendly placement heuristics (reserve space for later unlocks)
- [ ] Textual layout description: block list + recommended neighbourhoods and relative order
- [ ] Alignment of block sizes with Production Planner quantities

### v0.8 - Visual output and optional Design planning

- [ ] Coloured frames + labels on a blank farm map
- [ ] Simple diagram export of individual blocks
- [ ] Design-planning switch:
  - reserve walkable paths between blocks and key producers
  - optional inclusion of decorative elements inside/around blocks
- [ ] Independent outputs from both planners still available

### v0.9 - Combiner (third tool)

- [ ] Merge Layout + Production results into one coordinated plan
- [ ] Respect A→B processing order in the physical arrangement
- [ ] Functional plan always present; Design plan applied only when requested
- [ ] Single combined report / data file
- [ ] Expansion-friendly full-farm suggestion

### v1.0 - Local usable platform

- [ ] Unified CLI with Functional / Design toggle (e.g. `--design`)
- [ ] Expansion-friendly complete farm layout
- [ ] Visual outputs (frames, block collages, optional whole-map collage)
- [ ] Ready-to-use configuration examples for common player levels
- [ ] Documentation and example player-config files

### v2.0+ - Full application (future)

- Web UI
- Persistent database (PostgreSQL)
- Interactive drag-and-drop layout editor
- Real-time visualisation
- Optional live-order import (still secondary to the static capacity-driven core)

---

## Usage

```bash
# install
pip install -r requirements.txt

# build graph + analysis
python -m src.main --max-level 52

# choose formats
python -m src.main --formats json graphml csv

# custom paths
python -m src.main --data-dir data --output-dir output --max-level 30

# skip analysis if only the graph is needed
python -m src.main --no-analysis
```

Output lands in `output/`:

```text
output/
├── graph.json
├── graph_nodes.csv
├── graph_edges.csv
├── graph.graphml
└── analysis.json
```

Later versions will add `schedule.json`, layout descriptions and visual files to the same directory.  
A future flag (e.g. `--design`) will enable the optional Design planning layer.

Update data from the wiki:

```bash
python -m src.scraper --max-level 52
```

---

## Project Structure

```text
farm-production-recipe-dependency-graph/
├── data/
│   ├── locations.json                 # farm locations (buildings, fields, animals…)
│   ├── resources.json                 # crops, animal products, processed goods, ores
│   ├── recipes.json                   # production transformations inside locations
│   ├── level_limits.json              # (planned) max counts per player level
│   └── examples/
│       ├── locations.example.json
│       ├── resources.example.json
│       └── recipes.example.json
├── output/                            # generated exports land here
├── src/
│   ├── exporters/
│   │   ├── csv_exporter.py
│   │   ├── graphml_exporter.py
│   │   ├── json_exporter.py
│   │   └── labels.py
│   ├── graph/
│   │   ├── analysis.py                # proximity, clustering, centrality, paths
│   │   ├── graph_builder.py
│   │   ├── relationship.py
│   │   └── weighting.py
│   ├── loaders/
│   │   └── json_loader.py
│   ├── models/
│   │   ├── location.py
│   │   ├── recipe.py
│   │   └── resource.py
│   ├── planner/                       # (v0.5+) Production Planner
│   │   ├── capacity.py
│   │   ├── quantities.py
│   │   └── schedule.py
│   ├── scraper/
│   │   ├── parsers/
│   │   │   ├── locations.py
│   │   │   ├── recipes.py
│   │   │   └── resources.py
│   │   ├── cli.py
│   │   ├── normalizer.py
│   │   ├── wiki_client.py
│   │   └── writer.py
│   └── main.py
├── tests/
│   ├── test_analysis.py
│   ├── test_exporters.py
│   ├── test_graph_builder.py
│   ├── test_graph_quality.py
│   └── test_json_loader.py
├── LICENSE
├── README.md
└── requirements.txt
```

---

## License

MIT License

## Disclaimer

This project is an independent fan-made analysis tool.

Hay Day and related assets are properties of Supercell.
