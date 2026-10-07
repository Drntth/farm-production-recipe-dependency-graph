# Farm Production Graph

A graph-based system for analysing Hay Day production chains, designing farm layouts around reusable production blocks, and generating capacity-aware production schedules.

The system converts locations, resources and recipes into a weighted directed graph. From this graph it identifies tightly coupled production blocks, supports expansion-friendly arrangement of the farm (and later the town and fishing lake), and, using only static player data, produces practical production quantities and login schedules.

Planning is organised in two layers:

- **Functional planning** (always active): production logic, blocks, quantities, schedules, capacities and processing order.
- **Design planning** (optional): decorative elements, walkable paths between blocks, and aesthetic placement that still respects the functional constraints.

**Status:** v0.6 (standalone Layout Planner for the farm) is complete; v0.7 (Production Planner) is next. See the [Roadmap](#roadmap).

**Game knowledge** (rules, limits, measured sizes, game versions, data sources) is collected in [docs/](docs/README.md). Check there before researching the game again.

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
4. Detects **production blocks** via community detection on the proximity graph (`python -m src.main`, `analysis.json`).
5. Builds **named blocks** for placement (`python -m src.layout`, `src/layout/blocks.py`):
   - every production building is an anchor;
   - every tree, bush and animal shelter joins the anchor with the strongest direct coupling;
   - support relations pull non-production neighbours along (nectar bushes join the beehive tree);
   - a lone building merges into the block it is most coupled to (at most 3 buildings per block); a big crop user (at least 10 % of the farm's crop demand, e.g. the feed mill) is never lone, because its fields are its suppliers;
   - the block is named after its main building ("Dairy block").
6. Counts the copies per location: player profile, else everything the level allows, else one placeholder tree / bush (the Combiner will size them).
7. Gives **every block its own fields** (`src/layout/fields.py`), so crops such as corn for the feed mill or sugarcane for the sugar mill can stay planted: the fields are shared out in proportion to the block's crop demand (sum of the crop CONSUMES weights into its buildings), at least one per crop-using block. `--field-pool 0.1` keeps 10 % in a separate "Shared fields block". The counts are estimates until the Production Planner sizes them.
8. Packs each block (buildings one by one, fields / trees / bushes as patches), grows its frame by a reserve (default 20 %) and keeps unlocked but not yet owned copies as reserved space.
9. Packs the block frames on the farm map around the fixed buildings, one free tile apart, pulling coupled blocks together.
10. Writes `output/layout.svg` (isometric tile grid with every footprint), `output/layout.md` (block list, upstream → downstream order, recommended neighbourhoods) and `output/layout.json`.

A production block is a movable logical unit, for example:

- 1× Dairy
- related Cow Pasture(s)
- Feed Mill
- the appropriate number of fields

### Placement inputs (already in the data)

- **Footprints** in tiles (`footprint_width` × `footprint_height`) for every movable location at the current level. Machine sizes come from the wiki, the rest were measured in the game.
- **Fixed buildings** (`movable: false`): the mine and the fishing lake buildings stay where they are.
- **Rotation** (`rotatable`): non-square items that can be turned, e.g. the 1×2 raspberry and blackberry bushes and the 3×2 ice cream maker.
- **Copies per level** (`level_limits.json`): how many feed mills, coops, … are available.
- **Support relations** (`src/layout/support.py`): non-production neighbours, e.g. nectar bushes next to the beehive tree.

### Farm map (player data)

Every farm has its own expansions and its own spot for the farmhouse, barn, silo, mine, …, so the usable area is player data: `config/farm_map.json` (git-ignored; the committed `config/farm_map.example.json` lists the fixed farm buildings with empty positions).

```json
{
  "width": 60,
  "height": 55,
  "fixed": [
    { "id": "farmhouse", "x": 20, "y": 18, "width": 6, "height": 6 },
    { "id": "mine", "x": 52, "y": 2, "width": 4, "height": 4 },
    { "id": "silo", "x": null, "y": null, "width": null, "height": null }
  ]
}
```

The values above are only an illustration. Coordinates are tiles from the farm's top corner, with `x` along the ↘ edge and `y` along the ↙ edge. `null` means not measured yet: without `width` / `height` the layout is unbounded, and a fixed item without a position is listed in the notes but not drawn. A fixed item whose id is a location (`mine`) also pulls the coupled block (smelter) toward it.

The file can also hold a calibrated screenshot (`background`) and the farm plots (`expansions`, numbered like the wiki page Expansion/Farm, each a list of tile rectangles with an `unlocked` flag). With a background, `layout.svg` draws the screenshot under the grid. When at least one drawn plot is `unlocked` (draw the starting land as section `base`), blocks are placed only on unlocked plots; plots without rectangles are ignored.

#### Measuring with the map editor

`tools/farm_map_editor.html` is a self-contained page (open it in a browser, no server, nothing is uploaded):

1. In the game, open a **new layout slot** in Layout Edit Mode (level 37+): it starts empty, so only the fixed buildings remain. With the paintbrush, lay two rows of fields in an L shape from one corner field (one row ↘, one row ↙, 10+ fields each) as a ruler.
2. Zoom out fully, take screenshots at the same zoom, and stitch them without scaling or rotating; remove UI elements. Save the result as **PNG** in `config/farm_background.png` (git-ignored).
3. **Calibrate**: load the PNG, click A (top corner of the corner field), B (right corner of the last ↘ field), C (left corner of the last ↙ field), enter the two row lengths and apply. The grid must follow the field edges everywhere.
4. **Fixed**: pick an id (farmhouse, barn, silo, mine, …) and drag over its tiles.
5. **Expansions**: add a plot (section + wiki number, unlocked or not) and drag one or more rectangles over its tiles; Alt + click removes a rectangle.
6. **Export**: `farm_map.json` (save it as `config/farm_map.json`), the full map PNG with grid, fixed buildings and plots, or a ZIP with one cropped PNG per plot plus `index.json` (crop in pixels, tile bounds). The visible layers decide what the PNGs show; the editor keeps its state in the browser, and an exported JSON can be loaded again to continue.

The game's Layout Edit Mode shows no tile grid, so the graphical output always draws the grid and every footprint.

### Evolution

| Horizon     | Output                                                                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Short term  | Weighted graph + detected production blocks (done)                                                                                                                       |
| Medium term | Named blocks with footprints and a simple graphical layout, without production data (done, v0.6)                                                                         |
| Long term   | Complete expansion-friendly layout per area, so the farm does not need a full rebuild at every level. With Design planning, space is reserved for paths and decorations. |

---

## 2. Production Planner

### Production Planner purpose

Produce a sustainable production plan and a practical action/login schedule for the player's level, using only static data. Farm only.

### Inputs (static only)

- Player profile: level, mastery system, barn and silo capacity, and per location the slots, mastery, owned copies, animals and beehives (see [Player configuration](#player-configuration))
- Growth and production times (`growth_time_seconds`, `production_time_seconds`, `production_time_3star_seconds`)
- Fields and building / shelter copies available at that level (`level_limits.json`), animals per shelter (`animal_capacity`)
- Game rules such as slot limits and mastery effects ([docs/game-facts/](docs/README.md))

Values missing from the profile are filled with level defaults. Fields, trees and bushes left empty get a recommended count.

Live truck, boat, town or event orders are intentionally ignored.

### Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested login frequency derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

### Machine mastery

Mastery modifies production times, so it is modelled as a pluggable modifier chosen by `mastery_system` in the player config:

- `stars` (default): the classic 3-star mastery. The data holds both the base time and the full-mastery time of every recipe (`production_time_3star_seconds`).
- `workbench`: Building Mastery / Workbench, introduced in game version 1.72 (August 2026) with a gradual rollout.

---

## 3. Combiner / Layout Finetuner

### Combiner purpose

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

The config is the **player profile**: everything the player buys, upgrades or earns rather than unlocks by level. `null` means unknown; the planners then use a default derived from the level and the shared data.

```json
{
  "level": 56,
  "mastery_system": "stars",
  "barn_capacity": 675,
  "silo_capacity": 750,
  "fields_owned": 84,
  "fishing_spots_unlocked": 8,
  "locations": {
    "chicken_coop": { "owned": 3, "animals": 18 },
    "feed_mill": { "owned": 2, "slots": 12, "mastery_stars": 1 },
    "dairy": { "slots": 8, "mastery_stars": 3 },
    "apple_tree": { "owned": 9 },
    "beehive_tree": { "beehives": 2 },
    "lobster_pool": { "slots": 3 }
  }
}
```

The example file lists every configurable location unlocked at its level. Per-location fields, all optional:

| Field             | Applies to                                     | Meaning                                                     | If missing / `null`                                                               |
| ----------------- | ---------------------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `owned`           | multi-copy buildings, shelters, trees, bushes  | copies placed                                               | all copies unlocked at the level; trees / bushes: the planner recommends a number |
| `slots`           | production buildings, lobster pool, duck salon | slots unlocked, **summed over all copies**                  | base slots per copy                                                               |
| `mastery_stars`   | production buildings                           | 0-3 per building **type** (copies share production hours)   | 0                                                                                 |
| `workbench_level` | production buildings                           | with `mastery_system: "workbench"`                          | 0                                                                                 |
| `animals`         | animal shelters                                | animals in **all** shelters of the type (3 full coops = 18) | full shelters                                                                     |
| `beehives`        | beehive tree                                   | 1-4 beehives (3 bees each)                                  | 1                                                                                 |

`fields_owned` and the tree / bush counts are optional on purpose: they are tedious to count, and the planners will recommend a sensible number when they are missing.

Every CLI reads the level from this file. `--level` overrides it for a single run.  
`python -m src.main` checks the profile against the data and logs a warning for unknown ids, locations above the player level, more copies than the level allows, or more animals than `copies × animal_capacity`.  
The analysis behind the schema, including the input options (manual, defaults, presets, wizard, account sync), is in [docs/player-profile.md](docs/player-profile.md). The planners start using the profile in v0.7.

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
  "unlock_level": 6,
  "area": "farm",
  "footprint_width": 4,
  "footprint_height": 4
}
```

Allowed `type` values: `production`, `animal`, `field`, `tree`, `bush`, `storage`, `other`.  
Allowed `area` values: `farm` (default), `town`, `fishing_lake`. The scraper sets `fishing_lake` from the wiki category *Fishing Lake Buildings*.  
`movable` is `true` by default. It is `false` for fixed buildings the player cannot move (mine, fishing lake buildings).  
`rotatable` is `false` by default. It is `true` when the footprint can be turned (width and height swapped). It only matters for non-square footprints such as the 1×2 bushes or the 3×2 ice cream maker.  
Every fruit tree and bush kind is its own location (`apple_tree`, `raspberry_bush`, …), because each is placed separately and has its own footprint and fruit. Trees and bushes that produce no goods (the nectar bush) come from the wiki category *Trees and Bushes*.  
Optional fields:

- `footprint_width` / `footprint_height`: size in tiles, both or neither. The wiki lists them for production buildings only; the rest come from `data/overrides/`.
- `animal_capacity`: maximum animals per shelter (e.g. 6 for a chicken coop). The player's actual animals, beehives and lobster / duck slots are in the profile.
- `max_slots`: production slots (not filled yet; the rules are in [docs/game-facts/production-buildings.md](docs/game-facts/production-buildings.md)).

### resources.json

Crops, animal products, intermediate/processed goods and ores.

```json
{
  "id": "milk",
  "name": "Milk",
  "type": "animal_product",
  "unlock_level": 6,
  "source_location_id": "cow_pasture",
  "growth_time_seconds": 3600
}
```

`source_location_id` is mandatory for `crop`, `animal_product` and `ore`.  
Allowed `type` values: `crop`, `animal_product`, `processed_material`, `raw_material`, `ore`.  
`growth_time_seconds` is set for raw goods: crop growth, animal production, `0` for instant goods (ores, honeycomb). Processed goods carry their time on the recipe.

### recipes.json

Transformations that happen inside production locations, plus **feeding recipes** at animal shelters (`chicken_coop`: 1 `chicken_feed` → 1 `egg`), taken from the Goods List "Needs" column.  
Raw crops, ores and goods without needs (honeycomb) are resources only. The wiki names the caught animal for the lobster pool and duck salon; the normalizer maps it to the trap that catches it (`lobster` → `lobster_trap`, `duck` → `duck_trap`), so the net maker feeds the fishing-lake shelters.

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
  },
  "production_time_seconds": 7200,
  "production_time_3star_seconds": 6120
}
```

`production_time_3star_seconds` is the time with full 3-star mastery.  
Recipes may contain zero or more inputs. External/premium inputs (vouchers, diamonds, etc.) are allowed but never become graph nodes.

### meta.json

Written by the scraper. It records where and when the data came from, and is used by the [game update process](docs/game-updates.md).

```json
{
  "scraped_at": "2026-10-05T12:09:15+00:00",
  "max_level": 56,
  "known_game_version": "1.72",
  "wiki_revisions": { "Goods_List": "2026-07-29T14:20:27Z" }
}
```

### level_limits.json

Level-gated limits, as two 3NF tables:

- `field_grants`: new fields per level (from the wiki's *Experience Levels* pages). The total at a level is the sum of all grants up to that level.
- `location_instances`: one row per placeable copy of a production building or shelter, with its unlock level (e.g. the second Feed Mill at level 12).

```json
{
  "field_grants": [{ "level": 1, "count": 6 }, { "level": 3, "count": 3 }],
  "location_instances": [
    { "location_id": "feed_mill", "instance": 1, "unlock_level": 2 },
    { "location_id": "feed_mill", "instance": 2, "unlock_level": 12 }
  ]
}
```

`LevelLimits.fields_at(level)` and `LevelLimits.instances_at(location_id, level)` answer "how many at my level". Fields, trees and bushes beyond the grants can be bought, so they have no instance rows.

### overrides/

`data/overrides/{locations,resources,recipes}.json` are hand-maintained lists that the loader merges on top of the scraped data at every load:

- an entry whose `id` already exists patches only the listed fields;
- an entry with a new `id` is added as a complete entity;
- `null` means "not filled in yet" and is ignored.

Use them for data the wiki does not have, for example shelter and field footprints, or for content the wiki has not listed yet. They survive re-scraping. `load_data(..., apply_data_overrides=False)` loads the raw scraped data only.

`data/overrides/locations.json` holds the measured footprints, `movable` and `rotatable` values; it is complete for level 56. [data/overrides/README.md](data/overrides/README.md) explains how to measure footprints in the game and which edge is width and which is height.

### Timing and capacity fields

All durations are stored in seconds.  
`max_slots` (locations) and `max_in_barn` (resources) exist in the models but are not filled yet.  
Player-specific progress (owned copies, mastery, slots, animals, barn / silo capacity) lives in the player profile, not in the shared data. Game rules that apply to everyone (slot limits, mastery effects, costs) are documented in [docs/game-facts/](docs/README.md).

### External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect layout decisions.

---

## Graph Model

The system builds a directed weighted dependency graph (NetworkX `DiGraph`).

### Nodes

Every Location and every Resource becomes a node.

| Attribute             | Present on       | Description                       |
| --------------------- | ---------------- | --------------------------------- |
| `kind`                | all              | `"location"` or `"resource"`      |
| `id`                  | all              | Original entity id                |
| `name`                | all              | Human-readable name               |
| `type`                | all              | LocationType / ResourceType value |
| `unlock_level`        | all              | Player level required             |
| `source_location_id`  | resources (raw)  | Producing location                |
| `area`                | locations        | `farm` / `town` / `fishing_lake`  |
| `movable`             | locations        | `false` for fixed buildings       |
| `rotatable`           | locations        | footprint can be turned           |
| `footprint_width`     | locations (opt.) | Width in tiles                    |
| `footprint_height`    | locations (opt.) | Height in tiles                   |
| `animal_capacity`     | locations (opt.) | Animals per shelter               |
| `max_slots`           | locations (opt.) | Production slots                  |
| `max_in_barn`         | resources (opt.) | Storage limit for the resource    |
| `growth_time_seconds` | resources (opt.) | Growth / animal production time   |

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
   Skipped for feeding recipes, whose output already has a PRODUCES edge (`cow_feed ─CONSUMES→ cow_pasture ─PRODUCES→ milk`).

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

Hay Day changes regularly. After each game update, follow [docs/game-updates.md](docs/game-updates.md). It has the step-by-step process, the table mapping each game mechanic to the affected code and data, the known game versions, and the known wiki gaps.

In short: read the update notes → compare with `data/meta.json` → update the affected parts → `python -m src.scraper --game-version <version>` → `python -m pytest`.

Data in the repository: game version 1.72, level 56, scraped 2026-10-05. The 1.72 Building Mastery / Workbench is not on the wiki yet, so the data holds 3-star times only.

---

## Roadmap

**Current status:** v0.6 is complete (113 tests passing). Next milestone: v0.7 (Production Planner).  
Current data set (level 56): 46 locations (8 tree / bush kinds incl. the nectar bush, 6 fixed, 5 on the fishing lake), 167 resources, 135 recipes (incl. 9 animal feeding recipes), 84 fields over 28 levels, 52 building / shelter copies. Every raw good has a growth time, every recipe has a base time (and a 3-star time where mastery applies), and every movable location has a footprint.  
The Layout Planner (`python -m src.layout`) arranges 14 named blocks for level 56. Measuring the fixed buildings into `config/farm_map.json` makes the layout fit the real farm.  
Next step: start v0.7 with the capacity model and the profile defaults.

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

### v0.5 - Data foundation (done)

- [x] Review the relevant wiki pages (production buildings, animal shelters, goods, experience levels, barn, silo, town, fishing lake)
- [x] `footprint_width` / `footprint_height` and `area` on locations; `animal_capacity` on shelters
- [x] `growth_time_seconds`, `production_time_seconds` and `production_time_3star_seconds` filled by the scraper
- [x] `level_limits.json`: field grants per level and building / shelter copies with unlock levels
- [x] Barn / silo capacity moved to the player config (upgraded with supplies, not level-gated)
- [x] `data/overrides/` merged by the loader (`null` = not filled in yet); footprints measured in the game
- [x] Fruit trees and bushes as separate locations per kind, plus goods-less ones (nectar bush) from the wiki category; `movable` flag for fixed buildings
- [x] Player profile analysis ([docs/player-profile.md](docs/player-profile.md)) and schema (`PlayerConfig.locations`), validated against the data
- [x] `rotatable` flag for non-square footprints
- [x] Scraper tests with saved HTML fixtures
- [x] Game knowledge collected in [docs/](docs/README.md): game facts by category, game updates, data sources, player profile

### v0.6 - Standalone Layout Planner (farm) (done)

- [x] Support relations outside the production graph: nectar bushes near the beehive tree (the wiki says distance slows the bees)
- [x] Fixed buildings (`movable: false`) kept in place; only movable items are arranged
- [x] Non-square items placed in both orientations when `rotatable` is true, otherwise only as stored
- [x] Usable farm area: free space and the fixed non-production buildings (farmhouse, barn, silo, …; see [docs/game-facts/farm.md](docs/game-facts/farm.md)), measured by the player in `config/farm_map.json`
- [x] Named production blocks (Dairy block, Bakery block, Feed mill block, …) with footprints
- [x] Expansion-friendly placement heuristics (reserve space for later unlocks): reserved copies plus a configurable free margin per block
- [x] Simple graphical layout (SVG with coloured block frames and labels), without production data
- [x] Always draw the isometric tile grid, with every item's footprint, because the game's Layout Edit Mode shows none
- [x] Textual layout description: block list, recommended neighbourhoods and relative order
- [x] Animal feeding recipes scraped from the Goods List (feed mill → shelters in the graph); lobster / duck needs mapped to the lobster / duck trap
- [x] Dedicated fields per block, shared out by crop demand (optional shared pool)
- [x] Farm map editor (`tools/farm_map_editor.html`): screenshot calibration, fixed buildings, farm plots; exports JSON, full map PNG and per-plot pieces
- [x] Screenshot under the SVG grid; blocks only on unlocked plots
- [x] External recipe inputs logged once, as one summary line

### v0.7 - Production Planner

- [ ] Capacity model (barn, silo, fields, animals, machine slots)
- [ ] Steady-state quantity calculation tuned to barn/silo limits
- [ ] Mastery modifier: `stars` (default), `workbench` pluggable
- [ ] Use the player profile (option B of [docs/player-profile.md](docs/player-profile.md)): resolve every `null` to its level default, then apply the player's values
- [ ] Scrape base slots per building (wiki infobox `slots`) for the profile defaults; maximum is 9 per copy, 6 for the lobster pool and duck salon (wiki)
- [ ] Recommend field, tree and bush counts when the profile leaves them empty
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
- [ ] Game fact checker: a script that reads every row of `docs/game-facts/*.md` (`Source` = `wiki:<Page>`), fetches the page through the wiki API and reports rows whose value is no longer found or whose page changed after `Checked`. It can be pulled forward if game updates make manual checks too slow.
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

# farm layout: named blocks, isometric SVG, text description
# optional: measure config/farm_map.json with tools/farm_map_editor.html (see "Farm map")
python -m src.layout
python -m src.layout --level 30 --reserve 0.3 --gap 1 --field-pool 0.1
```

Output lands in `output/`:

```text
output/
├── graph.json
├── graph_nodes.csv
├── graph_edges.csv
├── graph.graphml
├── analysis.json
├── layout.json                        # python -m src.layout
├── layout.md
└── layout.svg
```

Later versions will add `schedule.json` to the same directory.

Update data from the wiki (level from the player config):

```bash
python -m src.scraper --game-version 1.72
```

---

## Project Structure

```text
farm-production-recipe-dependency-graph/
├── docs/                              # project knowledge, see docs/README.md
│   ├── README.md                      # index, where knowledge lives, fact table format
│   ├── game-facts/                    # game rules by category (wiki + in-game)
│   │   ├── animals.md
│   │   ├── farm.md
│   │   ├── fishing-lake.md
│   │   ├── production-buildings.md
│   │   ├── storage.md
│   │   └── town.md
│   ├── data-sources.md                # what is scraped, from where; what is manual
│   ├── game-updates.md                # update process, known versions, wiki gaps
│   └── player-profile.md              # player-specific settings and profile schema
├── config/
│   ├── player.example.json            # example player config (committed)
│   ├── player.json                    # your own config (git-ignored)
│   ├── farm_map.example.json          # fixed farm buildings, positions empty (committed)
│   ├── farm_map.json                  # your measured farm map (git-ignored)
│   └── farm_background.png            # your stitched farm screenshot (git-ignored)
├── data/
│   ├── locations.json                 # locations (buildings, fields, animals…)
│   ├── resources.json                 # crops, animal products, processed goods, ores
│   ├── recipes.json                   # production transformations inside locations
│   ├── meta.json                      # scrape date, level, wiki revisions, game version
│   ├── level_limits.json              # field grants + building / shelter copies per level
│   ├── overrides/                     # hand-maintained patches merged by the loader
│   │   ├── README.md                  # what to fill in and how to measure it
│   │   ├── locations.json
│   │   ├── resources.json
│   │   └── recipes.json
│   └── examples/
│       ├── locations.example.json
│       ├── resources.example.json
│       └── recipes.example.json
├── output/                            # generated exports land here
├── src/
│   ├── config.py                      # player profile: model, loader, validation
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
│   │   ├── level_limits.py
│   │   ├── location.py
│   │   ├── recipe.py
│   │   └── resource.py
│   ├── layout/                        # Layout Planner (farm)
│   │   ├── blocks.py                  # named blocks (anchor method), flow order
│   │   ├── cli.py                     # python -m src.layout
│   │   ├── describe.py                # layout.md / layout.json
│   │   ├── farm_map.py                # config/farm_map*.json model and loader
│   │   ├── fields.py                  # dedicated fields per block (crop demand)
│   │   ├── inventory.py               # copies per location (profile → level)
│   │   ├── packing.py                 # greedy rectangle packing on the tile grid
│   │   ├── planner.py                 # plan_layout(): blocks → frames → farm
│   │   ├── render_svg.py              # isometric SVG with tile grid
│   │   └── support.py                 # support relations (nectar bush → beehive tree)
│   ├── planner/                       # (planned, v0.7) Production Planner
│   ├── scraper/
│   │   ├── parsers/
│   │   │   ├── level_limits.py        # field grants from Experience Levels pages
│   │   │   ├── locations.py
│   │   │   ├── recipes.py
│   │   │   └── resources.py
│   │   ├── cli.py
│   │   ├── durations.py               # "1 d 3 h" / "★★★" → seconds
│   │   ├── normalizer.py
│   │   ├── wiki_client.py
│   │   └── writer.py
│   └── main.py
├── tools/
│   └── farm_map_editor.html           # screenshot calibration → config/farm_map.json, PNG exports
├── tests/
│   ├── fixtures/wiki/                 # trimmed wiki HTML for scraper tests
│   ├── test_analysis.py
│   ├── test_config.py
│   ├── test_exporters.py
│   ├── test_farm_map_editor.py        # editor JS core via node (skipped without node)
│   ├── test_graph_builder.py
│   ├── test_graph_quality.py
│   ├── test_json_loader.py
│   ├── test_layout.py
│   ├── test_level_limits.py
│   ├── test_models.py
│   └── test_scraper.py
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
