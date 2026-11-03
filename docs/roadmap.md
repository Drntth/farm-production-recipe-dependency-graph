# Roadmap

Milestones with their items. Changes per released version: [CHANGELOG.md](../CHANGELOG.md).

**Current status:** v1.6 (pre-2.0 hardening) is done (290 tests passing, CI on every push). Next: v2.0+ (full application).  
Current data set (every wiki level, up to 126): 86 locations (19 tree / bush kinds incl. the nectar and peanut bush, the squirrel house), 418 resources, 354 recipes, 228 fields over 150 levels, 80 building / shelter copies. At level 56: 48 locations (8 tree / bush kinds incl. the nectar bush, 2 storage: barn and silo, 6 fixed, 5 on the fishing lake), 167 resources, 135 recipes (incl. 9 animal feeding recipes), 84 fields over 28 levels, 52 building / shelter copies. Every raw good has a growth time, every recipe has a base time (and a 3-star time where mastery applies), and every movable location has a footprint.  
The Layout Planner (`python -m src.layout`) arranges 15 named blocks for level 56 (including the Storage block with the barn and silo) on the unlocked plots of the measured farm.  
The Production Planner (`python -m src.planner`) suggests a login interval for the profile and writes the quantities, recommendations and actions per login to `output/schedule.json` / `schedule.md`.  
The design layer adds paths and a decoration band (126 path tiles on the measured farm: 86 main path, 40 side paths; the riverboat reached at its connection point). Only the farm is laid out; the town and the fishing lake are not planned.  
The Combiner (`python -m src.combiner`) sizes the 15 blocks by the plan and places them upstream first (16 % reserve on the measured farm) in `output/combined.*`.  
Values the wiki lacks (tree / bush yield per harvest, honeycomb and peanut rates, footprints above level 56, Workbench bonuses) are accepted estimates or player measurements collected in [docs/wiki-gaps.md](wiki-gaps.md); they refine the plans but do not block the roadmap.  
The relocation plan (`python -m src relocate`) compares the current farm measured in the map editor with the combined plan and lists what stays, what to store and where to place every item.  
Next step: v2.0+. Changes per version: [CHANGELOG.md](../CHANGELOG.md).

## v0.3 - Graph and block analysis (done)

- [x] Weighted multi-level proximity
- [x] Production-block detection
- [x] Centrality and path analysis
- [x] JSON / CSV / GraphML exporters
- [x] Wiki scraper (locations, resources, recipes)

## v0.4 - Re-foundation (done)

- [x] Player config (`config/player.json`) with level and mastery system; `--level` on every CLI
- [x] No hard-coded player level; level-independent quality tests
- [x] Scraper runnable as `python -m src.scraper`; writes `data/meta.json`
- [x] Data re-scraped for level 56
- [x] Separated architecture: Layout and Production as independent tools, Combiner optional
- [x] Game update checklist

## v0.5 - Data foundation (done)

- [x] Review the relevant wiki pages (production buildings, animal shelters, goods, experience levels, barn, silo, town, fishing lake)
- [x] `footprint_width` / `footprint_height` and `area` on locations; `animal_capacity` on shelters
- [x] `growth_time_seconds`, `production_time_seconds` and `production_time_3star_seconds` filled by the scraper
- [x] `level_limits.json`: field grants per level and building / shelter copies with unlock levels
- [x] Barn / silo capacity moved to the player config (upgraded with supplies, not level-gated)
- [x] `data/overrides/` merged by the loader (`null` = not filled in yet); footprints measured in the game
- [x] Fruit trees and bushes as separate locations per kind, plus goods-less ones (nectar bush) from the wiki category; `movable` flag for fixed buildings
- [x] Player profile analysis ([docs/player-profile.md](player-profile.md)) and schema (`PlayerConfig.locations`), validated against the data
- [x] `rotatable` flag for non-square footprints
- [x] Scraper tests with saved HTML fixtures
- [x] Game knowledge collected in [docs/](README.md): game facts by category, game updates, data sources, player profile

## v0.6 - Standalone Layout Planner (farm) (done)

- [x] Support relations outside the production graph: nectar bushes near the beehive tree (the wiki says distance slows the bees)
- [x] Fixed buildings (`movable: false`) kept in place; only movable items are arranged
- [x] Non-square items placed in both orientations when `rotatable` is true, otherwise only as stored
- [x] Usable farm area: free space and the fixed non-production buildings (farmhouse, barn, silo, …; see [docs/game-facts/farm.md](game-facts/farm.md)), measured by the player in `config/farm_map.json`
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

## v0.7 - Production Planner (done)

- [x] Capacity model (barn, silo, fields, animals, machine slots, trees / bushes): parallel lines, queues, maximum rates
- [x] Steady-state quantity calculation tuned to barn/silo limits (linear program, login-driven cycles)
- [x] Mastery modifier: `stars` (default, per-star speed-ups from the Masteries page), `workbench` pluggable (placeholder until its bonuses are known)
- [x] Use the player profile (option B of [docs/player-profile.md](player-profile.md)): resolve every `null` to its level default, then apply the player's values
- [x] Scrape base slots per building (wiki infobox `slots`) for the profile defaults; maximum is 9 per copy, 6 for the lobster pool and duck salon (wiki), checked by the profile validation
- [x] Recommend field, tree and bush counts when the profile leaves them empty (plus nectar bushes per day for the honeycomb)
- [x] Ordered action list and suggested login frequency
- [x] `output/schedule.json` export (plus `schedule.md`)

## v0.8 - Design layer (done)

- [x] `movable` items in the farm map (barn, silo measured but placed by the planner)
- [x] Design layer (`design_layer`): walkable paths between blocks and key buildings, decoration band for decorations and fences (`decor_band`)
- [x] Town and fishing lake layouts were dropped later: the tools plan only the farm

## v0.9 - Combiner (done)

- [x] Block sizes from Production Planner quantities (fields per crop by use, recommended trees / bushes)
- [x] Respect A→B processing order in the physical arrangement (`flow` strategy, goods flows as coupling)
- [x] Functional plan always present; Design plan applied only when requested (`design_layer`)
- [x] Single combined report / data file (`output/combined.md`, `.json`, `.svg`)
- [x] Expansion-friendly full-farm suggestion (lookahead: reserved copies and fields, space check for new buildings)

## v1.0 - Local usable platform (done)

- [x] Settings only in config files: `config/design.json` (layout and design) and `config/planner.json` (production, Combiner); the CLI only says what to run (`--level`, file paths), and every output records the settings it used
- [x] Unified CLI: `python -m src <command>` (`graph`, `layout`, `plan`, `combine`, `scrape`, `all`); the tools' own entry points keep working
- [x] Game fact checker: `python -m src check-facts` reads every row of `docs/game-facts/*.md` with a `wiki:<Page>` source, fetches each page once through the wiki API and reports rows whose page changed after `Checked` or whose numbers are no longer in the page (`output/fact_check.md` / `.json`)
- [x] Visual outputs: one SVG per block (the block on its own grid with the paths around it, legend with its map position) and a collage of every block (`output/blocks/`, `output/combined_blocks/`; setting `block_images`); the whole map stays `layout.svg` / `combined.svg`
- [x] Ready-to-use player-config examples for common levels (`config/examples/`, level defaults only; `python -m src examples`)
- [x] Interactive profile wizard (option D of [docs/player-profile.md](player-profile.md)): `python -m src wizard` asks only about items unlocked at the level and writes the sparse profile
- [x] Documentation: [user guide](user-guide.md) (profile, map, settings, commands, outputs, typical situations)
- [x] Design options: every design option below is off by default and is switched on or tuned in `config/design.json`, so a chosen style is kept between runs
- [x] Nicer paths (option): `path_style` `shortest` (default) or `straight` (a cost per turn: fewer corners and detours); `path_targets` `blocks` (blocks and key buildings, default) or `buildings` (every building; needs `item_gap` ≥ 1)
- [x] Space inside blocks (option): `item_gap` free tiles between the buildings of a block (default 0), so blocks look less packed; field, tree and bush patches stay together. Every block must fit first: the gap is lowered before the reserve, and the report shows it
- [x] Reserved design zones (option): a `design` zone kind in the map editor for existing decorations; no block is placed there, paths may cross it, it is not part of the decoration band (`design_zones`, default on; no effect without such zones)
- [x] Design figures in the report whenever the design layer is on: path tiles, corners, detour ratio, free tiles per block, unreachable buildings, to compare settings

## v1.1 - Release basics (done)

- [x] Python 3.14: `requires-python = ">=3.14"`, the local `venv` and CI use it (the tests pass on 3.14)
- [x] Continuous integration (GitHub Actions): one job on Python 3.14 with Node (so the map editor tests run), `pytest`, `ruff check` and `ruff format --check` on every push and pull request
- [x] `pyproject.toml` with the project metadata, the version (kept only here) and the ruff settings; no packaging, the `requirements*.txt` files stay the way to install
- [x] `pytest` moves from `requirements.txt` to `requirements-dev.txt`; install docs updated
- [x] `CHANGELOG.md`: one `## [x.y.z] - date` heading per version with a few lines; v0.3-v0.9 in short from this roadmap (`?` where the date is not certain)
- [x] `v1.0.0` git tag on the v1.0 commit, a tag for every later version; older milestones get no tag

## v1.2 - Layout in the map editor (done)

- [x] Load `output/layout.json` or `output/combined.json` (its `layout` part) into `tools/farm_map_editor.html` as an overlay (step 7): block frames with names, items, paths, decoration band, as a layer that can be switched on and off
- [x] View only: blocks are not dragged or edited (that is the v2.0+ layout editor); the block list highlights a block, the status bar names the item under the mouse
- [x] Same tile coordinates as the farm map; when the layout's map size differs from the loaded farm map (or it was planned without one), the editor warns and does not shift anything

## v1.3 - Relocation plan (done)

- [x] Current farm: a `current` list in `config/farm_map.json` with the positions of the player's production buildings, shelters, barn and silo now (fields, trees and bushes only as counts), measured in a new editor tab; the Layout Planner ignores it
- [x] Farm map clean-up: `fixed` holds only buildings the game never moves; the barn and the silo leave it and the `movable` flag is removed (old farm maps fail with a clear error; re-save them in the editor)
- [x] The editor offers the item ids and sizes of the loaded layout (v1.2) for the current farm, free text without one; `relocate` checks every size against the data footprint, rotation included
- [x] `python -m src relocate [--layout PATH]`: compares the current farm with `output/combined.json` (else `output/layout.json`); not part of `all`
- [x] Relocation plan as keep / store / place lists: keep = same item at exactly the same place (greedy match per id), store = every other current item, place = target positions grouped by block; no move order is needed, because Layout Edit Mode can store everything (see [docs/game-facts/farm.md](game-facts/farm.md)); a note when a new layout slot is simpler
- [x] Listed apart: reserved copies (space to keep free), current copies the layout has no place for, layout copies the player does not own yet; an unknown id is an error
- [x] Report: `output/relocation.md` / `.json`

## v1.4 - Path network (done)

- [x] Main path from the hub (farmhouse) to the key buildings and the Storage block, built first; side paths join every block to the nearest point of the network
- [x] `main_path_width` (1 or 2, default 1); where a 2-tile main path does not fit between blocks it narrows to 1 there, and the report counts those tiles (a larger `gap` gives it room)
- [x] New `path_style` `stepped`: the staircase closest to the straight line between two points (a diagonal, curved look on the isometric grid); `main_path_style` (default: same as `path_style`) gives mixed styles such as a straight main path with stepped side paths
- [x] Design figures: path tiles of main and side paths apart, narrowed main path tiles; the main path drawn darker in the SVG

## v1.5 - Design templates (done)

- [x] Design template: a small grid pattern of buildings (`location_id` and rect) and decoration tiles (only "taken", no decoration kind), one file per template in `config/templates/<name>.json` (git-ignored, one committed example)
- [x] `templates` in `config/design.json` assigns templates to blocks, e.g. `{"dairy_block": {"template": "dairy_garden", "mode": "reserve"}}`
- [x] Mode `reserve` (default): the block frame grows by the template and keeps its area free; mode `arrange`: the template's buildings go to their template positions, its decoration tiles stay free and the rest of the block is packed around them
- [x] A template is a wish: when the blocks do not fit, `item_gap` is lowered first, then the template is dropped (with a warning), only then the reserve; a building that is not in the block is an error, template copies the player does not own become reserved space; no rotation or mirroring
- [x] Map editor "Templates" tab: cut a template out of the farm map (current items and design zone tiles inside a rectangle) or draw one; a screenshot of another design can be loaded and calibrated as its own background to mark it the same way

## v1.6 - Pre-2.0 hardening (done)

- [x] Data for every wiki level: the scraper reads every level by default (`--level N` cuts off), game version 1.73; `meta.json` `max_level` is the highest level read; the tools still filter by the player level, so the level-56 results stay the same and the Combiner lookahead lists the next unlocks
- [x] Field grants above level 100 ("1 field") are read; footprints of the new trees, the peanut bush and the squirrel house are estimates in `data/overrides/` (see [docs/wiki-gaps.md](wiki-gaps.md))
- [x] Squirrel house: each pair of squirrels makes peanuts every 5 h (into the silo), the plan recommends peanut bushes per day, the layout keeps peanut bushes next to the squirrel house
- [x] Fact checker: number words (`one to three`) count as numbers, derived steps (`(+N each)`) are not checked; every game fact row re-checked
- [x] Combined report: the weighted flow distance (goods / h × tiles apart over every goods flow) to compare layouts
- [x] Placement measured: on the measured farm `item_gap: 1` needs about as many tiles as the unlocked plots have, so it drops to 0 (area, not the packer); a re-placement / swap pass after the greedy packing gained only 6 % flow distance and was left out
- [x] Polish: one log line of overrides per data file, crop names with `+N more` in the combined report, old layout outputs (`layout_town.*`, `layout_<strategy>.*`) removed before writing

## v2.0+ - Full application (future)

- Web UI
- Persistent database (PostgreSQL)
- Interactive drag-and-drop layout editor
- Real-time visualisation
- Optional live-order import (still secondary to the static capacity-driven core)
- Image recognition in the map editor: find the grid and the buildings on a screenshot of a design, the player corrects the result

## In-game TODO

Nothing left: the values the wiki lacks are measured (field limit, barn footprint) or kept as accepted estimates (tree / bush yield, honeycomb rate, 3-star times). The Workbench bonuses wait for the game rollout to reach the account; until then the base times are used. Basis and status of every value: [docs/wiki-gaps.md](wiki-gaps.md).
