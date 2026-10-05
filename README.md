# Farm Production Graph

A graph-based system for analysing Hay Day production chains, designing farm layouts around reusable production blocks, and generating capacity-aware production schedules.

The system converts locations, resources and recipes into a weighted directed graph. From this graph it identifies tightly coupled production blocks, supports expansion-friendly arrangement of the farm (and later the town and fishing lake), and, using only static player data, produces practical production quantities and login schedules.

Planning is organised in two layers:

- **Functional planning** (always active): production logic, blocks, quantities, schedules, capacities and processing order.
- **Design planning** (optional): decorative elements, walkable paths between blocks, and aesthetic placement that still respects the functional constraints.

---

## Architecture

Three independent tools share one core. Each tool can run on its own. The Combiner links their results when both are available.

```text
                      ┌────────────────────────────┐
                      │ Core                       │
                      │ player config · data model │
                      │ loader · dependency graph  │
                      └─────────────┬──────────────┘
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
     ┌───────────────────────┐             ┌───────────────────────┐
     │ 1. Layout Planner     │             │ 2. Production Planner │
     │ blocks, footprints,   │             │ quantities, capacity, │
     │ visual layout         │             │ schedule              │
     │ areas: farm / town /  │             │ (farm only)           │
     │ fishing lake          │             │                       │
     └───────────┬───────────┘             └───────────┬───────────┘
                 └──────────────────┬──────────────────┘
                                    ▼
                      ┌────────────────────────────┐
                      │ 3. Combiner (optional)     │
                      │ layout sized by production │
                      └────────────────────────────┘
```

Design decisions:

- **Layout without production.** The Layout Planner can produce a usable layout, including a graphical one, from the graph, the blocks and the building footprints alone. Production data only refines block sizes, for example how many fields or pastures a block needs.
- **Production without layout.** The Production Planner never needs a layout.
- **Separate UX.** Each tool has its own CLI command and its own output files. The Combiner is a third, optional step.

---

## 1. Layout Planner

### Purpose

Help the player design an efficient and expandable layout by discovering natural groups of buildings that belong together.

### Areas

The layout is planned per game area, selected with `--area` (planned for v0.8):

| Area           | Content                                                                                         | Quantity calculations                 |
| -------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------- |
| `farm`         | production buildings, animal shelters, fields, trees, bushes, storage, decorations, paths       | yes (from graph / Production Planner) |
| `town`         | service buildings, town hall, train station, sanctuary animals and shelters, decorations, paths | no                                    |
| `fishing_lake` | lake buildings, decorations, paths                                                              | no                                    |

The farm layout is driven by the dependency graph. The town and fishing lake layouts are driven by footprints, adjacency rules and the design layer only.

### How it works (farm)

1. Loads the normalised JSON data (locations, resources, recipes), filtered to the player level.
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

| Horizon     | Output                                                                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Short term  | Weighted graph + detected production blocks (done)                                                                                                                       |
| Medium term | Named blocks with footprints and a simple graphical layout, without production data                                                                                      |
| Long term   | Complete expansion-friendly layout per area, so the farm does not need a full rebuild at every level. With Design planning, space is reserved for paths and decorations. |

---

## 2. Production Planner

### Purpose

Produce a sustainable production plan and a practical action/login schedule for the player's level, using only static data. Farm only.

### Inputs (static only)

- Player config: level, mastery system (see [Player configuration](#player-configuration))
- Barn and silo capacity
- Maximum available fields, animal shelters, animals and production buildings at that level (`level_limits.json`)
- Optional current progress: owned counts, machine mastery (stars or Workbench level), unlocked slots

Live truck, boat, town or event orders are intentionally ignored.

### Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested login frequency derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

### Machine mastery

Mastery modifies production times, so it is modelled as a pluggable modifier chosen by `mastery_system` in the player config:

- `stars` (default): the classic 3-star mastery (production time bonus at full mastery).
- `workbench`: Building Mastery / Workbench, introduced in game version 1.72 (August 2026) with a gradual rollout.

---

## 3. Combiner / Layout Finetuner

### Purpose

Merge the results of the Layout Planner and the Production Planner into one coordinated, usable farm plan.

### How it works

- Takes production blocks and the recommended quantities/schedule.
- Sizes the blocks from the quantities (number of fields, pastures, machines).
- Places the blocks in a logical order that respects the A→B processing flow.
- Applies expansion-friendly rules (leave room for later buildings and animals).
- When **Design planning** is enabled:
  - reserves walkable paths between blocks and key producers
  - optionally inserts decorative elements inside or around blocks
- Produces a single combined output (textual description, data file and visual representation).

Functional planning is always present. Design planning is a selectable option.

---

## Player configuration

Player-specific, static settings live in `config/`:

- `config/player.example.json`: committed example.
- `config/player.json`: your own copy. It is git-ignored and takes precedence when present.

```json
{
  "level": 56,
  "mastery_system": "stars"
}
```

Every CLI reads the level from this file. `--level` overrides it for a single run.  
Owned counts, mastery progress and unlocked slots will be added here in later versions (v0.7).

---

## Data Model

All identifiers are snake_case English.  
The model is kept close to 3NF so the same structure can later be loaded into PostgreSQL.

### locations.json

Everything that occupies space (production buildings, animal shelters, fields, trees, bushes, storage…).

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

### meta.json

Written by the scraper. It records where and when the data came from, and is used by the [Game update checklist](#game-update-checklist).

```json
{
  "scraped_at": "2026-10-05T12:09:15+00:00",
  "max_level": 56,
  "known_game_version": "1.72",
  "wiki_revisions": { "Goods_List": "2026-07-29T14:20:27Z" }
}
```

### Planned data (v0.5)

- `level_limits.json`: maximum number of fields, animal shelters, animals and production buildings per player level, plus the barn and silo upgrade tables. It is kept in a separate file to preserve 3NF.
- `size` on locations: footprint in tiles (e.g. `2x2`, `3x3`), taken from the wiki.
- `area` on locations: `farm`, `town` or `fishing_lake`.
- `growth_time_seconds` on resources (crops, animal products, ores).
- `data/overrides/`: manually maintained additions for content the game already has but the wiki does not list yet. The normalizer merges them, and they are recorded in `meta.json`.

### Timing and capacity fields

Already in the models (optional, not yet filled by the scraper):

- `production_time_seconds` on recipes
- `max_slots` on locations
- `max_in_barn` on resources

All durations are stored in seconds.  
Player-specific progress (owned counts, mastery, unlocked slots) lives in the player config, not in the shared data.

### External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect layout decisions.

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
| `max_in_barn`        | resources (opt.) | Storage limit for the resource    |

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

## Game update checklist

Hay Day changes regularly. After each game update, check which mechanics changed and update the matching part of the project.

### Process

1. Read the update notes: [Fandom Update page](https://hayday.fandom.com/wiki/Update) and the official in-game / Supercell announcements.
2. Compare them with `data/meta.json`: game version and wiki revision dates.
3. Work through the table below for every changed mechanic.
4. Re-scrape: `python -m src.scraper --game-version <version>`. Run `python -m pytest`.
5. If the wiki does not list new content yet, add it to `data/overrides/` (v0.5+) and note it.

### Mechanic → affected part

| Game change                                   | What to update                                                              |
| --------------------------------------------- | --------------------------------------------------------------------------- |
| New building, good, crop or animal            | scraper parsers, normalizer, re-scrape, quality tests                       |
| Changed unlock levels or new level cap        | re-scrape, player config                                                    |
| Mastery system (3 stars ↔ Workbench)          | planner mastery modifier, `mastery_system` in the player config             |
| Production / growth times, machine slots      | timing fields, `max_slots`, Production Planner                              |
| Barn / silo capacity, upgrade tables          | `level_limits.json`, capacity model                                         |
| Building sizes, expansion, map size           | location `size`, area dimensions, Layout Planner                            |
| Town, sanctuary, fishing lake                 | area modes (`--area`), area-specific data                                   |
| Decorations, paths                            | Design layer                                                                |
| Wiki lags behind the game                     | `data/overrides/`, `known_game_version` in `meta.json`                      |

### Known state (checked 2026-10-05, game version 1.72)

- 1.72 (2026-08): Building Mastery / Workbench replaces the 3-star mastery, rolled out gradually. Not on the wiki yet.
- 1.71 (2026-06): new machines Balloon Maker and Kebab Machine. Not on the wiki's production building list yet.

---

## Roadmap

**Current status:** v0.4 is complete. Next milestone: v0.5 (Data foundation).  
Current data set (level 56): 40 locations, 167 resources, 126 recipes. It contains no timing, capacity or footprint values yet.  
Next step: review the wiki pages for sizes, timing and per-level limits, then extend the models and the scraper.

### v0.3 - Graph and block analysis (done)

- [x] Weighted multi-level proximity
- [x] Production-block detection
- [x] Centrality and path analysis
- [x] JSON / CSV / GraphML exporters
- [x] Wiki scraper (locations, resources, recipes)

### v0.4 - Re-foundation (done)

- [x] Player config (`config/player.json`) with level and mastery system; `--level` on every CLI
- [x] No hard-coded player level; level-independent quality tests
- [x] Scraper runnable as `python -m src.scraper`; writes `data/meta.json`
- [x] Data re-scraped for level 56
- [x] Separated architecture: Layout and Production as independent tools, Combiner optional
- [x] Game update checklist

### v0.5 - Data foundation (next)

- [ ] Review all relevant wiki pages (production buildings, animals, crops, barn, silo, town, fishing lake)
- [ ] Footprint `size` and `area` fields on locations
- [ ] `production_time_seconds` and `growth_time_seconds` filled by the scraper
- [ ] `level_limits.json`: buildings, fields and animals per level, barn and silo upgrade tables
- [ ] `data/overrides/` for content missing from the wiki (e.g. Balloon Maker, Kebab Machine)
- [ ] Scraper tests with saved HTML fixtures

### v0.6 - Standalone Layout Planner (farm)

- [ ] Named production blocks (Dairy block, Bakery block, Feed + Animals block, …) with footprints
- [ ] Expansion-friendly placement heuristics (reserve space for later unlocks)
- [ ] Simple graphical layout (SVG grid with coloured block frames and labels), without production data
- [ ] Textual layout description: block list, recommended neighbourhoods and relative order

### v0.7 - Production Planner

- [ ] Capacity model (barn, silo, fields, animals, machine slots)
- [ ] Steady-state quantity calculation tuned to barn/silo limits
- [ ] Mastery modifier: `stars` (default), `workbench` pluggable
- [ ] Player progress in the player config (owned buildings/animals, mastery, slots)
- [ ] Ordered action list and suggested login frequency
- [ ] `output/schedule.json` export

### v0.8 - Area modes and Design layer

- [ ] `--area town`: service buildings, town hall, train station, sanctuary animals and shelters
- [ ] `--area fishing_lake`
- [ ] Design layer for every area: walkable paths, decorations, fences
- [ ] No quantity calculations outside the farm

### v0.9 - Combiner

- [ ] Block sizes from Production Planner quantities
- [ ] Respect A→B processing order in the physical arrangement
- [ ] Functional plan always present; Design plan applied only when requested
- [ ] Single combined report / data file
- [ ] Expansion-friendly full-farm suggestion

### v1.0 - Local usable platform

- [ ] Unified CLI (`--area`, `--design`, `--level`)
- [ ] Visual outputs (block frames, block collages, optional whole-map collage)
- [ ] Ready-to-use player-config examples for common levels
- [ ] Documentation

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
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# personal player config (optional; otherwise the example is used)
cp config/player.example.json config/player.json

# run tests
python -m pytest

# build graph + analysis for the configured player level
python -m src.main

# override the level for one run
python -m src.main --level 30

# choose formats
python -m src.main --formats json graphml csv

# custom paths
python -m src.main --data-dir data --output-dir output

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

Update data from the wiki (level from the player config):

```bash
python -m src.scraper --game-version 1.72
```

---

## Project Structure

```text
farm-production-recipe-dependency-graph/
├── config/
│   ├── player.example.json            # example player config (committed)
│   └── player.json                    # your own config (git-ignored)
├── data/
│   ├── locations.json                 # locations (buildings, fields, animals…)
│   ├── resources.json                 # crops, animal products, processed goods, ores
│   ├── recipes.json                   # production transformations inside locations
│   ├── meta.json                      # scrape date, level, wiki revisions, game version
│   ├── level_limits.json              # (planned, v0.5) max counts per player level
│   ├── overrides/                     # (planned, v0.5) content missing from the wiki
│   └── examples/
│       ├── locations.example.json
│       ├── resources.example.json
│       └── recipes.example.json
├── output/                            # generated exports land here
├── src/
│   ├── config.py                      # player config loader
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
│   ├── layout/                        # (planned, v0.6) Layout Planner
│   ├── planner/                       # (planned, v0.7) Production Planner
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
│   ├── test_config.py
│   ├── test_exporters.py
│   ├── test_graph_builder.py
│   ├── test_graph_quality.py
│   └── test_json_loader.py
├── AGENTS.md                          # instructions for coding agents
├── CLAUDE.md -> AGENTS.md             # symlink
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
