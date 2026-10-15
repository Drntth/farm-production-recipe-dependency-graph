# Farm Production Graph

A graph-based system for analysing Hay Day production chains, designing farm layouts around reusable production blocks, and generating capacity-aware production schedules.

The system converts locations, resources and recipes into a weighted directed graph. From this graph it identifies tightly coupled production blocks, supports expansion-friendly arrangement of the farm, the town and the fishing lake, and, using only static player data, produces practical production quantities and login schedules.

Planning is organised in two layers:

- **Functional planning** (always active): production logic, blocks, quantities, schedules, capacities and processing order.
- **Design planning** (optional): decorative elements, walkable paths between blocks, and aesthetic placement that still respects the functional constraints.

**Status:** v1.0 is done: one command line (`python -m src`) for the layout, the production plan and the Combiner, settings in config files, design options, block images, a profile wizard, example profiles and a game fact checker. **New here? Start with the [user guide](docs/user-guide.md).** See the [Roadmap](#roadmap).

**Game knowledge** (rules, limits, measured sizes, game versions, data sources, wiki gaps) is collected in [docs/](docs/README.md). Check there before researching the game again.

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

The layout is planned per game area, selected with `--area` (default `farm`):

| Area           | Content                                                                                   | Quantity calculations                 |
| -------------- | ----------------------------------------------------------------------------------------- | ------------------------------------- |
| `farm`         | production buildings, animal shelters, fields, trees, bushes, storage, decorations, paths | yes (from graph / Production Planner) |
| `town`         | service buildings, town hall, train station, sanctuary entrance, decorations, paths       | no                                    |
| `fishing_lake` | lake buildings, decorations, paths                                                        | no                                    |

The farm layout is driven by the dependency graph. The town and fishing lake layouts use only the measured area map (`config/<area>_map.json`, same schema and editor as the farm map) and the design layer:

- **town** (`src/layout/area.py`): items marked `movable` in the map (the service buildings) keep their measured size and are rearranged around the fixed items, largest first, pulled toward the town hall. Output: `output/layout_town.*`.
- **fishing_lake**: every lake building is fixed, so the layout only adds the design layer. Output: `output/layout_fishing_lake.*`.

### Design layer (optional, every area)

`design_layer: true` in [`config/design.json`](#settings) adds walkable paths and a decoration band on top of the functional layout (`src/layout/design.py`):

- Paths (1 tile wide) connect every block and the key buildings into one network: on the farm the farmhouse, barn, silo, truck, roadside shop and riverboat (hub: the farmhouse, else the Storage block); in the town and on the lake every measured building (hub: town hall / fisherman's hut). The network grows from the hub, each time by the shortest path on free tiles to the nearest building not reached yet.
- A key building with no reachable free tile next to it gets a path to its **connection point**, the reachable free tile nearest to it. On the farm the riverboat and the leaderboard stand behind a paved strip that is not buildable (mark it as a `blocked` zone): the path ends at the edge of the buildable land, and the notes give the tiles left in between. A building more than 5 tiles beyond the reachable land stays unreachable.
- The decoration band is the free tiles within `decor_band` tiles of a path (default 1): room for decorations and fences, not for buildings.
- With the design layer the blocks keep at least one free tile between them (`gap` ≥ 1), so a path always fits. Buildings no path can reach are listed in the notes.
- `path_style`: `shortest` (default) takes any shortest path; `straight` adds a cost to every change of direction, so paths have fewer corners and detours (on the measured farm 12 corners instead of 17).
- `path_targets` (farm): `blocks` (default) connects the blocks and the key buildings; `buildings` connects every building and every field / tree / bush patch inside the blocks; the paths may cross the free part of a block frame, but the decoration band stays out of it (it is the reserve for later unlocks). With the design layer on it needs `item_gap` ≥ 1, so a path fits between the buildings.
- `item_gap` (farm, default 0): free tiles between the buildings of a block, so blocks look less packed; patches stay whole. Placing every block comes first, looks second: when the blocks do not fit, the item gap is lowered step by step (at the requested reserve) before the reserve is; with no gap left, `path_targets: buildings` falls back to `blocks`. The report shows the gap used and the one asked for (on the measured farm `item_gap: 1` drops to 0).
- Design zones (`design` zones of the area map, `design_zones`, default on): existing decorations; no block is placed there, paths may cross them, and the decoration band leaves them alone.
- Figures in `layout.md` / `layout.json` (`design.figures`) to compare settings: path tiles, corners (turns and junctions), detour ratio (tiles walked per tile of grid distance), free tiles per block, unreachable buildings, design zone tiles.

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
6. Counts the copies per location: player profile, else everything the level allows, else one placeholder tree / bush (the Combiner sizes them from the plan).
7. Gives **every block its own fields** (`src/layout/fields.py`), so crops such as corn for the feed mill or sugarcane for the sugar mill can stay planted: the fields are shared out in proportion to the block's crop demand (sum of the crop CONSUMES weights into its buildings), at least one per crop-using block. `field_pool: 0.1` keeps 10 % in a separate "Shared fields block". The counts are estimates; the Combiner sizes them from the production plan.
8. Packs each block (buildings one by one, fields / trees / bushes as patches), grows its frame by a reserve (default 20 %; when a block would not fit on the map, the blocks are also tried largest first, then the reserve is lowered in 1 % steps down to 0) and keeps unlocked but not yet owned copies as reserved space.
9. Packs the block frames on the farm map around the fixed buildings, `gap` free tiles apart (default 1), pulling coupled blocks together. `strategy` sets the block order: `coupling`, `size` (largest first), `flow` (upstream first along the processing order), `auto` (coupling, then size; default) or `all` (one output set per order).
10. With `design_layer: true`, adds the design layer (see below).
11. Writes `output/layout.svg` (isometric tile grid with every footprint; paths sand-coloured, decoration band light green), `output/layout.md` (block list, design summary, upstream → downstream order, recommended neighbourhoods) and `output/layout.json`.

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

The file can also hold a calibrated screenshot (`background`) and the farm plots (`expansions`, numbered like the wiki page Expansion/Farm, each a list of tile rectangles with an `unlocked` flag). With a background, `layout.svg` draws the screenshot under the grid. When at least one drawn plot is `unlocked` (draw the starting land as section `base`), blocks are placed only on unlocked plots; plots without rectangles are ignored. Plots of section `base` (the starting land) always count as unlocked. The barn and silo are movable: without a position in `fixed` the planner places them as the Storage block. An item with `"movable": true` is measured but not an obstacle: the planner places it itself (on the farm like an item without a position, but only for locations the planner places, such as the barn and silo; any other movable farm item stays fixed and is reported; in the town it keeps the measured size). `zones` are hand-marked tile rectangles: blocks stay inside the `buildable` zones (if any) and never touch `blocked` ones (water, road, forest, …).

#### Measuring with the map editor

`tools/farm_map_editor.html` is a self-contained page (open it in a browser, no server, nothing is uploaded). Pick the **Area** first (farm, town, fishing lake): each area has its own default ids, is kept separately in the browser and is saved as `<area>_map.json` (save it as `config/<area>_map.json`). In the town, use path tiles as the calibration ruler, and tick **movable** for the service buildings (default for their ids). The steps below are for the farm; the town and the lake work the same way without plots. The toolbar holds the area, opening files, saving and zoom; the side panel lists the steps with their progress, can be resized by dragging its edge and hidden with `\`; the buildings and plots lists can be filtered; `?` shows every shortcut (`1`-`6` steps, `Ctrl+S` save, `Ctrl+Z` undo).

1. In the game, open a **new layout slot** in Layout Edit Mode (level 37+): it starts empty, so only the fixed buildings remain. With the paintbrush, lay two rows of fields in an L shape from one corner field (one row ↘, one row ↙, 10+ fields each) as a ruler.
2. Zoom out fully, take screenshots at the same zoom, and stitch them without scaling or rotating; remove UI elements. Save the result as **PNG** in `config/farm_background.png` (git-ignored). Keep the GIMP file (`.xcf`) and the raw screenshots in `config/screenshots/`, and the wiki plot maps used on the Reference tab in `config/reference/`; both folders are git-ignored (player data, wiki licence, file size). Manual stitching in GIMP:
   - Take all screenshots in **one session**, with overlap between neighbours. After closing the game the same zoom cannot be reproduced, and details of locked plots (e.g. stone wall textures) change, so later shots do not match.
   - **File → Open as Layers** loads all screenshots at once; enlarge the canvas with **Image → Canvas Size** (resize layers: none), then move each layer into place by hand.
   - Small black gaps where no screenshot covers the farm are acceptable, as long as the ruler fields and the fixed buildings are visible.
   - Tile accuracy is enough: an error of a few pixels does not matter for the calibration.
3. **Calibrate**: load the PNG, click A (top corner of the corner field), B (right corner of the last ↘ field), C (left corner of the last ↙ field), enter the two row lengths and apply. The grid must follow the field edges everywhere. A placed point can be dragged to a better spot; apply again afterwards.
4. **Fixed**: pick an id (farmhouse, barn, silo, mine, …) and drag over its tiles.
5. **Reference** (optional): overlay the wiki plot map (Expansion/Farm) to trace plot borders that unlocked plots no longer show. Zoom to the part of the farm the overlay shows, then load it: it starts fitted into the visible area. Click 3 point pairs far apart, each first on the overlay and then on the same spot of the farm (r1, m1, r2, m2, r3, m3). After each pair the overlay snaps closer (1 pair: moved, 2 pairs: scaled and rotated, 3 pairs: fully fitted), so the later points need less zoom. Placed points can be dragged; where an r and an m point overlap, the drag takes the m point (Shift: the r point). The overlay is not saved in the JSON.
6. **Expansions**: add a plot (section + wiki number, unlocked or not) and drag one or more rectangles over its tiles; touching rectangles of one plot merge into one shape, Alt + drag erases tiles.
7. **Zones**: mark the farm sections as **buildable** (green), water, roads, forest, paved strips (e.g. in front of the riverboat), … as **blocked** (red), and existing decorations the layout should keep as **design** (violet), each as tile rectangles.
8. **Export**: `farm_map.json` (save it as `config/farm_map.json`; by default the map is cropped to the farm with a 5-tile margin, so the outline follows the real farm), the full map PNG with grid, fixed buildings and plots, or a ZIP with one cropped PNG per plot plus `index.json` (crop in pixels, tile bounds). The visible layers decide what the PNGs show; the editor keeps its state in the browser, and an exported JSON can be loaded again to continue.

The game's Layout Edit Mode shows no tile grid, so the graphical output always draws the grid and every footprint.

### Evolution

| Horizon     | Output                                                                                                                                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Short term  | Weighted graph + detected production blocks (done)                                                                                                                                                         |
| Medium term | Named blocks with footprints and a simple graphical layout, without production data (v0.6, measured farm map)                                                                                              |
| Long term   | Complete expansion-friendly layout per area, so the farm does not need a full rebuild at every level. With Design planning, space is reserved for paths and decorations (v0.8: paths and decoration band). |

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

### How it works

`python -m src.planner` (package `src/planner/`, never imports `src.layout`):

1. **Profile** (`profile.py`, option B of [docs/player-profile.md](docs/player-profile.md)): every `null` gets its level default (all unlocked copies, base slots × copies, 0 stars, full shelters, 1 beehive). Fields, trees and bushes without a count are left to the plan.
2. **Mastery** (`mastery.py`, see [Machine mastery](#machine-mastery)): the player's production time of every recipe.
3. **Capacity** (`capacity.py`): barn and silo, fields, and per location what runs in parallel and what queues. A machine produces one item at a time, so copies run in parallel and slots only queue; every animal produces on its own; the lobster pool and duck salon run one animal per slot. A planted crop gives two, so one planting adds one crop net. A tree / bush gives `lifetime_yield` goods over `lifetime_harvests` harvests, and every beehive one honeycomb per cycle. Values the wiki lacks are estimates for now, listed with their basis in [docs/wiki-gaps.md](docs/wiki-gaps.md).
4. **Quantities** (`quantities.py`): a linear program (scipy, HiGHS) over the rates per hour. Fields, animals and trees are only served at a login, so their cycle is the growth time rounded up to whole login intervals; machines keep running through their queue. The goods made between two logins must fit into `storage_share` of the barn and silo (default 50 %, the rest is stock). Four solves, each keeping the previous result:
   1. every good gets the same spare amount per hour (`balance`);
   2. goods without a production model (ores from the mine, fish) are used only as much as that balance needs, because their supply is unknown;
   3. idle machines and animals are filled (maximum production hours);
   4. the fewest fields and recommended trees / bushes for that plan.
5. **Schedule** (`schedule.py`): the plan is solved for logins every 0.5-12 h; the suggested interval is the longest one that keeps 80 % of the best production time (`min_efficiency`), or `login_interval` fixes it (both in [`config/planner.json`](#settings)). For that interval it lists the recommendations (fields, trees / bushes, nectar bushes per day for the honeycomb; 5 honeycomb per bush) and the actions of every login: collect → feed animals → plant fields → fill the machine queues, upstream machines first → sell or deliver the surplus. Items rarer than one per login are given as "1 every N logins".
6. Writes `output/capacity.json`, `output/schedule.json` and `output/schedule.md`.

Recipes with inputs that are not goods (vouchers, diamonds, lures, fishing spots) are not planned; `schedule.json` lists them under `plan.skipped_recipes`.

### Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested login frequency derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

### Machine mastery

Mastery modifies production times, so it is modelled as a pluggable modifier chosen by `mastery_system` in the player config:

- `stars` (default): the classic 3-star mastery. The data holds both the base time and the full-mastery time of every recipe (`production_time_3star_seconds`). At three stars the planner uses that time; below three it applies the building's speed-up from `data/mastery_bonuses.json` (the feed mill, lure workbench and net maker are 5 % / 10 % faster at one / two stars, other machines only get coin and XP bonuses there).
- `workbench`: Building Mastery / Workbench, introduced in game version 1.72 (August 2026) with a gradual rollout. Its bonuses are not known yet, so the planner uses the base times and logs a warning.

---

## 3. Combiner / Layout Finetuner

### Combiner purpose

Merge the results of the Layout Planner and the Production Planner into one coordinated, usable farm plan. Farm only.

### How the Combiner works

`python -m src.combiner` (package `src/combiner/`, the only code that imports both planners):

1. **Production plan**: runs the Production Planner for the profile (same `production` settings in `config/planner.json`).
2. **Block sizes from the quantities** (`sizing_from_plan`): the plan becomes a layout `Sizing` (`src/layout/sizing.py`), so the Layout Planner itself never imports the Production Planner:
   - every crop's fields are split among the blocks in proportion to how much of the crop their buildings use; fields of crops that are only sold and owned fields the plan leaves empty go to the Shared fields block;
   - trees and bushes the profile leaves open get the recommended count;
   - the goods flows between locations (goods per hour) strengthen the pull between the blocks that exchange the most.
3. **Expansion-friendly** (`combiner.lookahead`, default 5 levels): more copies of placed buildings and more fields unlocked within the lookahead get reserved space in their blocks; new buildings are listed with the tiles they will need, and the report warns when the free land is too small for them.
4. **A→B processing order**: the blocks are placed upstream first (`combiner.strategy: flow`, default; it overrides the farm `strategy` of `design.json`), each pulled toward the blocks it exchanges goods with. When a block does not fit, the reserve is lowered first; only if a block does not fit even without reserve, the size order takes over.
5. **Functional plan always, design on request**: `design_layer: true` (farm section of `design.json`) adds the paths and the decoration band of the Layout Planner. Gap and reserve also come from the farm section.
6. Writes `output/combined.json` (settings used, summary, blocks with copies, fields, busy share and output per hour, goods flows between blocks with the tiles between them, expansion, the full layout and schedule), `output/combined.md` (one report: blocks upstream → downstream, the heaviest flows, expansion, then the layout and the schedule sections) and `output/combined.svg`.

The sizes inherit the estimates of the Production Planner (tree / bush yield, honeycomb rate; see [docs/wiki-gaps.md](docs/wiki-gaps.md)): measuring them changes the counts, not the method. Nectar bushes are not sized: the plan gives the bushes to plant per day, but how long a bush stands is unknown, so their count stays the profile's.

---

## Settings

How the tools work is set in config files, never on the command line: the CLI only says what to run (`--area`, `--level`, `--player-config`, `--map`, `--design-config`, `--planner-config`, `--data-dir`, `--output-dir`). Each file has a committed example and a local, git-ignored copy that wins; without either, the built-in defaults of `src/settings.py` apply. Every run logs the file it used, and `layout*.json`, `schedule.json` and `combined.json` record the settings in a `settings` key.

`config/design.json` (Layout Planner, design layer, Combiner layout): a `default` section, and `farm` / `town` / `fishing_lake` sections that set only what differs.

```json
{
  "default": {
    "gap": 1,
    "design_layer": false,
    "decor_band": 1,
    "path_style": "shortest",
    "design_zones": true
  },
  "farm": {
    "reserve": 0.2,
    "strategy": "auto",
    "field_pool": 0.0,
    "item_gap": 0,
    "path_targets": "blocks"
  },
  "town": { "design_layer": true },
  "fishing_lake": {}
}
```

| Key            | Areas | Meaning                                                                                           | Default  |
| -------------- | ----- | ------------------------------------------------------------------------------------------------- | -------- |
| `gap`          | all   | free tiles between blocks                                                                         | 1        |
| `design_layer` | all   | paths and decoration band (gap is then at least 1)                                                | false    |
| `decor_band`   | all   | decoration band width next to the paths                                                           | 1        |
| `reserve`      | farm  | extra free area per block for later unlocks                                                       | 0.2      |
| `strategy`     | farm  | block order: `auto`, `coupling`, `size`, `flow`, or `all` (one output set per order)              | auto     |
| `field_pool`   | farm  | share of the fields in a separate Shared fields block (without production sizing)                 | 0        |
| `item_gap`     | farm  | free tiles between the buildings of a block; patches stay whole; lowered if the blocks do not fit | 0        |
| `path_style`   | all   | `shortest`, or `straight` (fewer corners and detours)                                             | shortest |
| `path_targets` | farm  | `blocks` (blocks and key buildings) or `buildings` (every building; needs `item_gap` ≥ 1)         | blocks   |
| `design_zones` | all   | keep the map's `design` zones free of blocks (paths may cross them)                               | true     |
| `block_images` | farm  | one SVG per block (`blocks/`, `combined_blocks/`) and a collage of every block                    | true     |

Farm-only keys are rejected in the town and fishing lake sections; in the `default` section they apply to the farm only.

`config/planner.json` (farm only):

```json
{
  "production": { "login_interval": null, "storage_share": 0.5, "min_efficiency": 0.8 },
  "combiner": { "lookahead": 5, "strategy": "flow" }
}
```

| Key                         | Meaning                                                                       | Default |
| --------------------------- | ----------------------------------------------------------------------------- | ------- |
| `production.login_interval` | hours between logins; `null` = suggested                                      | null    |
| `production.storage_share`  | share of barn and silo the goods of one interval may fill (the rest is stock) | 0.5     |
| `production.min_efficiency` | the suggested interval keeps at least this share of the best production time  | 0.8     |
| `combiner.lookahead`        | levels ahead whose unlocks get space now (0 = none)                           | 5       |
| `combiner.strategy`         | block order of the combined layout (overrides the farm `strategy`)            | flow    |

---

## Player configuration

Player-specific, static settings live in `config/`:

- `config/player.example.json`: committed example.
- `config/player.json`: your own copy. It is git-ignored and takes precedence when present.
- `python -m src wizard`: answers a few questions and writes `config/player.json` with only the values that differ from the level defaults (Enter keeps a default; per location e.g. `slots=5 stars=3`; asks before overwriting).
- `config/examples/player_level_<N>.json` (levels 10, 20, 30, 40, 50): a player who bought nothing beyond the level, every value written out as its level default (all fields and copies, base slots, 0 mastery, full shelters, one beehive; trees / bushes left to the planner; barn, silo and fishing spots `null`, because supplies upgrade them, not the level). Copy one to `config/player.json` and edit what differs, or pass it with `--player-config`. `python -m src examples` regenerates them after a re-scrape.

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
The analysis behind the schema, including the input options (manual, defaults, presets, wizard, account sync), is in [docs/player-profile.md](docs/player-profile.md). The Production Planner resolves it with level defaults (`python -m src.planner`); it also checks that `slots` stay within 9 per copy (6 for the lobster pool and duck salon).

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
Allowed `area` values: `farm` (default), `town`, `fishing_lake`. The scraper sets `fishing_lake` from the wiki category _Fishing Lake Buildings_.  
`movable` is `true` by default. It is `false` for fixed buildings the player cannot move (mine, fishing lake buildings).  
`rotatable` is `false` by default. It is `true` when the footprint can be turned (width and height swapped). It only matters for non-square footprints such as the 1×2 bushes or the 3×2 ice cream maker.  
Every fruit tree and bush kind is its own location (`apple_tree`, `raspberry_bush`, …), because each is placed separately and has its own footprint and fruit. Trees and bushes that produce no goods (the nectar bush) come from the wiki category _Trees and Bushes_.  
Optional fields:

- `footprint_width` / `footprint_height`: size in tiles, both or neither. The wiki lists them for production buildings only; the rest come from `data/overrides/`.
- `animal_capacity`: maximum animals per shelter (e.g. 6 for a chicken coop). The player's actual animals, beehives and lobster / duck slots are in the profile.
- `base_slots` / `max_slots`: slots per copy at purchase and at most (see [Timing and capacity fields](#timing-and-capacity-fields); the rules are in [docs/game-facts/production-buildings.md](docs/game-facts/production-buildings.md)).
- `lifetime_yield` / `lifetime_harvests`: goods and harvests of a tree / bush over its life, incl. a revive (estimates, see [docs/wiki-gaps.md](docs/wiki-gaps.md)).

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
  "scraped_at": "2026-10-14T08:54:12+00:00",
  "max_level": 56,
  "known_game_version": "1.72",
  "wiki_revisions": { "Goods_List": "2026-07-29T14:20:27Z" }
}
```

### level_limits.json

Level-gated limits, as two 3NF tables:

- `field_grants`: new fields per level (from the wiki's _Experience Levels_ pages). The total at a level is the sum of all grants up to that level.
- `location_instances`: one row per placeable copy of a production building or shelter, with its unlock level (e.g. the second Feed Mill at level 12).

```json
{
  "field_grants": [
    { "level": 1, "count": 6 },
    { "level": 3, "count": 3 }
  ],
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
`base_slots` (locations) is the slot count per copy at purchase (wiki infobox; lobster pool and duck salon from the overrides). `max_slots` is the maximum per copy where it differs from the default 9 (lobster pool, duck salon: 6). `max_in_barn` (resources) exists in the model but is not filled yet.  
`mastery_bonuses.json` holds one row per building and star level with the total production time reduction (`location_id`, `stars`, `time_reduction_percent`); only speed-ups are stored, not coin or XP bonuses.  
Player-specific progress (owned copies, mastery, slots, animals, barn / silo capacity) lives in the player profile, not in the shared data. Game rules that apply to everyone (slot limits, mastery effects, costs) are documented in [docs/game-facts/](docs/README.md).

### External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect layout decisions.

---

## Graph Model

The system builds a directed weighted dependency graph (NetworkX `DiGraph`).

### Nodes

Every Location and every Resource becomes a node.

| Attribute             | Present on       | Description                             |
| --------------------- | ---------------- | --------------------------------------- |
| `kind`                | all              | `"location"` or `"resource"`            |
| `id`                  | all              | Original entity id                      |
| `name`                | all              | Human-readable name                     |
| `type`                | all              | LocationType / ResourceType value       |
| `unlock_level`        | all              | Player level required                   |
| `source_location_id`  | resources (raw)  | Producing location                      |
| `area`                | locations        | `farm` / `town` / `fishing_lake`        |
| `movable`             | locations        | `false` for fixed buildings             |
| `rotatable`           | locations        | footprint can be turned                 |
| `footprint_width`     | locations (opt.) | Width in tiles                          |
| `footprint_height`    | locations (opt.) | Height in tiles                         |
| `animal_capacity`     | locations (opt.) | Animals per shelter                     |
| `base_slots`          | locations (opt.) | Slots per copy at purchase              |
| `max_slots`           | locations (opt.) | Maximum slots per copy (default 9)      |
| `lifetime_yield`      | locations (opt.) | Goods a tree / bush gives in its life   |
| `lifetime_harvests`   | locations (opt.) | Harvests of a tree / bush, incl. revive |
| `max_in_barn`         | resources (opt.) | Storage limit for the resource          |
| `growth_time_seconds` | resources (opt.) | Growth / animal production time         |

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

Hay Day changes regularly. After each game update, follow [docs/game-updates.md](docs/game-updates.md). It has the step-by-step process, the table mapping each game mechanic to the affected code and data, and the known game versions. Data the wiki lacks, with the estimates in use, is in [docs/wiki-gaps.md](docs/wiki-gaps.md).

In short: read the update notes → compare with `data/meta.json` → update the affected parts → `python -m src.scraper --game-version <version>` → `python -m pytest`.

Data in the repository: game version 1.72, level 56, scraped 2026-10-14. The 1.72 Building Mastery / Workbench is not on the wiki yet, so the data holds 3-star times only.

---

## Roadmap

**Current status:** v1.0 (local usable platform) is done (238 tests passing). Next: the [In-game TODO](#in-game-todo) measurements, then v1.x (design templates).  
Current data set (level 56): 48 locations (8 tree / bush kinds incl. the nectar bush, 2 storage: barn and silo, 6 fixed, 5 on the fishing lake), 167 resources, 135 recipes (incl. 9 animal feeding recipes), 84 fields over 28 levels, 52 building / shelter copies. Every raw good has a growth time, every recipe has a base time (and a 3-star time where mastery applies), and every movable location has a footprint.  
The Layout Planner (`python -m src.layout`) arranges 15 named blocks for level 56 (including the Storage block with the barn and silo) on the unlocked plots of the measured farm.  
The Production Planner (`python -m src.planner`) suggests a login interval for the profile and writes the quantities, recommendations and actions per login to `output/schedule.json` / `schedule.md`.  
The design layer adds paths and a decoration band (123 path tiles on the measured farm, the riverboat reached at its connection point); `--area town` / `--area fishing_lake` lay out the measured town and lake maps (`config/town_map.json`, `config/fishing_lake_map.json`, measured with the map editor).  
The Combiner (`python -m src.combiner`) sizes the 15 blocks by the plan and places them upstream first (16 % reserve on the measured farm) in `output/combined.*`.  
Values the wiki lacks (tree / bush yield per harvest, honeycomb rate, Workbench bonuses, town building sizes) are estimates or player measurements collected in [docs/wiki-gaps.md](docs/wiki-gaps.md); measuring them refines the plans but does not block the roadmap.  
Next step: the [In-game TODO](#in-game-todo) measurements, to check the results against the game; then v1.x.

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
- [x] Stitched farm screenshot finalised in the editor: calibration, fixed buildings and farm plots saved to `config/farm_map.json`; layout checked against the real farm
- [x] Editor: reference overlay (wiki plot map, 3-point alignment), zones (buildable / blocked), merged plot outlines, crop to the farm on save
- [x] Barn and silo as movable storage locations (Storage block); the block reserve shrinks until every block fits
- [x] Placement strategies (`strategy`: `coupling | size | auto | all`); `all` writes one output set per strategy in one run

### v0.7 - Production Planner (done)

- [x] Capacity model (barn, silo, fields, animals, machine slots, trees / bushes): parallel lines, queues, maximum rates
- [x] Steady-state quantity calculation tuned to barn/silo limits (linear program, login-driven cycles)
- [x] Mastery modifier: `stars` (default, per-star speed-ups from the Masteries page), `workbench` pluggable (placeholder until its bonuses are known)
- [x] Use the player profile (option B of [docs/player-profile.md](docs/player-profile.md)): resolve every `null` to its level default, then apply the player's values
- [x] Scrape base slots per building (wiki infobox `slots`) for the profile defaults; maximum is 9 per copy, 6 for the lobster pool and duck salon (wiki), checked by the profile validation
- [x] Recommend field, tree and bush counts when the profile leaves them empty (plus nectar bushes per day for the honeycomb)
- [x] Ordered action list and suggested login frequency
- [x] `output/schedule.json` export (plus `schedule.md`)

### v0.8 - Area modes and Design layer (done)

- [x] `--area town`: service buildings rearranged with their measured size around the town hall, train station and sanctuary entrance (fixed)
- [x] `--area fishing_lake`: fixed lake buildings, design layer only
- [x] Map editor and map file per area (`area`, `movable` items, `config/<area>_map*.json`)
- [x] Design layer for every area (`design_layer`): walkable paths between blocks and key buildings, decoration band for decorations and fences (`decor_band`)
- [x] No quantity calculations outside the farm

### v0.9 - Combiner (done)

- [x] Block sizes from Production Planner quantities (fields per crop by use, recommended trees / bushes)
- [x] Respect A→B processing order in the physical arrangement (`flow` strategy, goods flows as coupling)
- [x] Functional plan always present; Design plan applied only when requested (`design_layer`)
- [x] Single combined report / data file (`output/combined.md`, `.json`, `.svg`)
- [x] Expansion-friendly full-farm suggestion (lookahead: reserved copies and fields, space check for new buildings)

### v1.0 - Local usable platform (done)

- [x] Settings only in config files: `config/design.json` (layout and design, `default` plus per-area sections) and `config/planner.json` (production, Combiner); the CLI only says what to run (`--area`, `--level`, file paths), and every output records the settings it used
- [x] Unified CLI: `python -m src <command>` (`graph`, `layout`, `plan`, `combine`, `scrape`, `all`); the tools' own entry points keep working
- [x] Game fact checker: `python -m src check-facts` reads every row of `docs/game-facts/*.md` with a `wiki:<Page>` source, fetches each page once through the wiki API and reports rows whose page changed after `Checked` or whose numbers are no longer in the page (`output/fact_check.md` / `.json`)
- [x] Visual outputs: one SVG per block (the block on its own grid with the paths around it, legend with its map position) and a collage of every block (`output/blocks/`, `output/combined_blocks/`; setting `block_images`); the whole map stays `layout.svg` / `combined.svg`
- [x] Ready-to-use player-config examples for common levels (`config/examples/`, level defaults only; `python -m src examples`)
- [x] Interactive profile wizard (option D of [docs/player-profile.md](docs/player-profile.md)): `python -m src wizard` asks only about items unlocked at the level and writes the sparse profile
- [x] Documentation: [user guide](docs/user-guide.md) (profile, map, settings, commands, outputs, typical situations)
- [x] Design options: every design option below is off by default and is switched on or tuned in `config/design.json` (per area), so a chosen style is kept between runs
- [x] Nicer paths (option): `path_style` `shortest` (default) or `straight` (a cost per turn: fewer corners and detours); `path_targets` `blocks` (blocks and key buildings, default) or `buildings` (every building; needs `item_gap` ≥ 1)
- [x] Space inside blocks (option): `item_gap` free tiles between the buildings of a block (default 0), so blocks look less packed; field, tree and bush patches stay together. Every block must fit first: the gap is lowered before the reserve, and the report shows it
- [x] Reserved design zones (option): a `design` zone kind in the map editor for existing decorations; no block is placed there, paths may cross it, it is not part of the decoration band (`design_zones`, default on; no effect without such zones)
- [x] Design figures in the report whenever the design layer is on: path tiles, corners, detour ratio, free tiles per block, unreachable buildings, to compare settings

### v1.x - Design templates (after v1.0)

- [ ] Path network from the farmhouse: main paths and side paths, with more styles (straight, curved with stepped corners, mixed)
- [ ] Design templates per block: load an existing design (buildings and decorations on the grid, drawn or loaded in the map editor), pick the blocks it applies to, and let the layout either keep room for it or arrange the block around it
- [ ] Template import from a screenshot: the editor finds the grid and the buildings on an image of an existing design (image recognition), the player corrects the result

### v2.0+ - Full application (future)

- Web UI
- Persistent database (PostgreSQL)
- Interactive drag-and-drop layout editor
- Real-time visualisation
- Optional live-order import (still secondary to the static capacity-driven core)

### In-game TODO

Tasks that need the real game, because the wiki does not give the values. Until they are done the code uses an estimate or an empty map, so **none of them blocks the next versions**; they make the results more accurate. They are planned after v1.0, to check the finished tools against the game. Basis and status of every estimate: [docs/wiki-gaps.md](docs/wiki-gaps.md).

| Task                                                                                                                    | Needed for                                                                                      | Until then                                | Blocks a version?                            | Record the result in                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| [ ] Yield of every tree and bush kind per harvest (1st, 2nd, 3rd, after a revive), incl. blueberry and coffee bush      | v0.7 Production Planner (fruit rates, tree / bush recommendations), v0.9 Combiner (patch sizes) | estimate 2 / 3 / 4 / 4 per harvest        | no                                           | `data/overrides/locations.json` (`lifetime_yield`, `lifetime_harvests`), `docs/game-facts/farm.md`, `docs/wiki-gaps.md` |
| [ ] Honeycomb rate per beehive, with close and with distant nectar bushes                                               | v0.7 Production Planner (honeycomb, nectar bushes per day)                                      | estimate one per 35 min                   | no                                           | `data/overrides/resources.json` (`growth_time_seconds`), `docs/game-facts/animals.md`                                   |
| [ ] Measure the town map with the editor (screenshot, calibration, every building, `movable` for the service buildings) | v0.8 `--area town`                                                                              | the layout lists what is not measured     | no; needed for a usable town layout          | `config/town_map.json`                                                                                                  |
| [ ] Check which town buildings can be moved in Layout Edit Mode                                                         | v0.8 `--area town`                                                                              | service buildings movable, the rest fixed | no                                           | `config/town_map.example.json`, map editor defaults, `docs/wiki-gaps.md`                                                |
| [ ] Measure the fishing lake map with the editor                                                                        | v0.8 `--area fishing_lake`                                                                      | the layout lists what is not measured     | no; needed for a usable lake layout          | `config/fishing_lake_map.json`                                                                                          |
| [ ] Workbench (Building Mastery) bonuses, once the rollout reaches the account                                          | v0.7 mastery modifier (`mastery_system: workbench`)                                             | base production times                     | no; only matters after the switch from stars | `src/planner/mastery.py`, `docs/game-facts/production-buildings.md`                                                     |
| [ ] Real 3-star time of one machine (e.g. chicken feed: 4 min or 4 min 15 s)                                            | v0.7 mastery modifier (precision)                                                               | the scraped Goods List time               | no                                           | `docs/wiki-gaps.md`                                                                                                     |
| [ ] Whether fields are limited by level (wiki: "no limit" vs. the per-level grants)                                     | v0.7 field recommendation, v0.6 layout field count                                              | the per-level grants                      | no                                           | `docs/game-facts/farm.md`, `docs/wiki-gaps.md`                                                                          |
| [ ] Barn footprint at the other barn appearance stages                                                                  | v0.6 layout (Storage block)                                                                     | 3x3, measured at capacity 675             | no                                           | `data/overrides/locations.json`, `docs/game-facts/storage.md`                                                           |

---

## Usage

```bash
# install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional: ruff

# personal player config (optional; otherwise the example is used)
cp config/player.example.json config/player.json

# run tests
python -m pytest

# unified CLI: one entry point, one command per tool
python -m src                       # list the commands
python -m src all                   # graph, farm layout, plan and combined plan in one run
python -m src layout --area town    # any tool: python -m src <graph|layout|plan|combine|scrape> [options]
python -m src wizard                # questions → config/player.json (sparse profile)
python -m src examples              # regenerate config/examples/player_level_<N>.json
python -m src check-facts           # docs/game-facts vs. the wiki → output/fact_check.md (network)

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
# settings (gap, reserve, strategy, design layer): config/design.json, see "Settings"
python -m src.layout
python -m src.layout --level 30
python -m src.layout --area town           # config/town_map.json → layout_town.*
python -m src.layout --area fishing_lake   # config/fishing_lake_map.json
python -m src.layout --design-config my_design.json

# production plan: capacity, quantities, recommendations, actions per login
python -m src.planner
python -m src.planner --level 30
python -m src.planner --planner-config my_planner.json   # settings: config/planner.json

# combined plan: layout sized by the production plan, one report
python -m src.combiner
python -m src.combiner --design-config my_design.json --planner-config my_planner.json
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
├── layout.svg
├── layout_town.*                      # python -m src.layout --area town
├── layout_fishing_lake.*
├── capacity.json                      # python -m src.planner
├── schedule.json
├── schedule.md
├── combined.json                      # python -m src.combiner
├── combined.md
├── combined.svg
├── blocks/                            # one SVG per block + collage.svg (block_images)
└── combined_blocks/                   # the same for the combined layout
```

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
│   ├── game-updates.md                # update process, known versions
│   ├── wiki-gaps.md                   # data the wiki lacks: estimates in use, measurement / wiki TODO
│   ├── user-guide.md                  # how to use the tools: profile, map, settings, run, outputs
│   └── player-profile.md              # player-specific settings and profile schema
├── config/
│   ├── player.example.json            # example player config (committed)
│   ├── examples/                      # level-default profiles: player_level_10 … _50.json
│   ├── player.json                    # your own config (git-ignored)
│   ├── design.example.json            # layout / design settings (committed)
│   ├── planner.example.json           # production / Combiner settings (committed)
│   ├── design.json                    # your own settings (git-ignored)
│   ├── planner.json
│   ├── farm_map.example.json          # fixed farm buildings, positions empty (committed)
│   ├── farm_map.json                  # your measured farm map (git-ignored)
│   ├── town_map.example.json          # town buildings, positions empty; service buildings movable
│   ├── fishing_lake_map.example.json  # fishing lake buildings, positions empty
│   ├── town_map.json                  # your measured town / lake maps (git-ignored)
│   ├── fishing_lake_map.json
│   └── farm_background.png            # your stitched farm screenshot (git-ignored)
├── data/
│   ├── locations.json                 # locations (buildings, fields, animals…)
│   ├── resources.json                 # crops, animal products, processed goods, ores
│   ├── recipes.json                   # production transformations inside locations
│   ├── meta.json                      # scrape date, level, wiki revisions, game version
│   ├── level_limits.json              # field grants + building / shelter copies per level
│   ├── mastery_bonuses.json           # production speed-up per building and mastery star
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
│   ├── combiner/                      # Combiner (farm): the only place joining both planners
│   │   ├── cli.py                     # python -m src.combiner
│   │   ├── combine.py                 # sizing from the plan, lookahead, flows between blocks
│   │   └── report.py                  # combined.json / combined.md
│   ├── __main__.py                    # python -m src <command>
│   ├── cli.py                         # unified CLI: graph, layout, plan, combine, scrape, all
│   ├── config.py                      # player profile: model, loader, validation
│   ├── settings.py                    # design / planner settings: models, defaults, loader
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
│   │   ├── mastery.py
│   │   ├── recipe.py
│   │   └── resource.py
│   ├── layout/                        # Layout Planner (farm, town, fishing lake)
│   │   ├── area.py                    # town / fishing lake layout from the measured map
│   │   ├── blocks.py                  # named blocks (anchor method), flow order
│   │   ├── cli.py                     # python -m src.layout
│   │   ├── describe.py                # layout.md / layout.json
│   │   ├── design.py                  # design layer: paths, decoration band
│   │   ├── farm_map.py                # config/<area>_map*.json model and loader
│   │   ├── fields.py                  # dedicated fields per block (crop demand)
│   │   ├── inventory.py               # copies per location (profile → level)
│   │   ├── packing.py                 # greedy rectangle packing on the tile grid
│   │   ├── planner.py                 # plan_layout(): blocks → frames → farm
│   │   ├── render_svg.py              # isometric SVG with tile grid
│   │   ├── sizing.py                  # block sizes from production quantities (Combiner input)
│   │   ├── support.py                 # support relations (nectar bush → beehive tree)
│   │   └── visuals.py                 # block images and collage
│   ├── planner/                       # Production Planner (farm)
│   │   ├── capacity.py                # capacity model: storage, fields, parallel lines, rates
│   │   ├── cli.py                     # python -m src.planner
│   │   ├── mastery.py                 # mastery modifiers: stars, workbench (placeholder)
│   │   ├── profile.py                 # player profile with level defaults (option B)
│   │   ├── examples.py                # level-default profiles for config/examples/
│   │   ├── quantities.py              # linear program: steady-state rates per login interval
│   │   ├── run.py                     # one planner run: profile → capacity → plans → schedule
│   │   ├── schedule.py                # interval suggestion, recommendations, actions per login
│   │   └── wizard.py                  # interactive profile wizard (python -m src wizard)
│   ├── scraper/
│   │   ├── parsers/
│   │   │   ├── level_limits.py        # field grants from Experience Levels pages
│   │   │   ├── locations.py           # incl. base slots from the building infoboxes
│   │   │   ├── masteries.py           # speed-up per star from the Masteries page
│   │   │   ├── recipes.py
│   │   │   └── resources.py
│   │   ├── cli.py
│   │   ├── durations.py               # "1 d 3 h" / "★★★" → seconds
│   │   ├── factcheck.py               # game fact tables vs. the wiki (python -m src check-facts)
│   │   ├── normalizer.py
│   │   ├── wiki_client.py
│   │   └── writer.py
│   └── main.py
├── tools/
│   └── farm_map_editor.html           # screenshot calibration → config/<area>_map.json, PNG exports
├── tests/
│   ├── fixtures/wiki/                 # trimmed wiki HTML / wikitext for scraper tests
│   ├── test_analysis.py
│   ├── test_cli.py
│   ├── test_combiner.py
│   ├── test_config.py
│   ├── test_examples.py
│   ├── test_exporters.py
│   ├── test_factcheck.py
│   ├── test_farm_map_editor.py        # editor JS core via node (skipped without node)
│   ├── test_graph_builder.py
│   ├── test_graph_quality.py
│   ├── test_json_loader.py
│   ├── test_layout.py
│   ├── test_level_limits.py
│   ├── test_models.py
│   ├── test_planner.py
│   ├── test_scraper.py
│   ├── test_settings.py
│   └── test_wizard.py
├── AGENTS.md                          # instructions for coding agents
├── CLAUDE.md -> AGENTS.md             # symlink
├── LICENSE
├── README.md
├── requirements.txt
└── requirements-dev.txt               # ruff
```

---

## License

MIT License

## Disclaimer

This project is an independent fan-made analysis tool.

Hay Day and related assets are properties of Supercell.
