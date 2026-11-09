# AGENTS.md

Instructions for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

Commit prefix: [HAYDAY-PROJECT]

## Project

The project analyses Hay Day production chains. It turns locations, resources and recipes into a weighted directed graph (NetworkX). From that graph it forms named production blocks for the farm layout and plans production quantities. Overview: `README.md`; how each tool works: `docs/tools/`.

- Milestones v0.3-v2.2 are done; what each brought is in `docs/roadmap.md`. Next: **v2.3** (site structure and farm view), then v2.4 (farm profiles and the plan in the browser); the v2+ sub-versions are in `docs/roadmap.md`, the web app design and its decisions in `docs/v2-design.md`.
- The values the wiki lacks are measured or accepted estimates in `docs/wiki-gaps.md`.

## Read first

Domain terms (block, anchor, goods flow, connection point, sizing, …) are defined in [CONTEXT.md](CONTEXT.md). Use them consistently in code, docs and replies; add a term there when a new one appears.

Game knowledge is already collected. **Before researching the game or the wiki, read [docs/README.md](docs/README.md)** and the relevant file:

| Question about…                                    | File                                      |
| -------------------------------------------------- | ----------------------------------------- |
| slots, mastery, building copies, costs             | `docs/game-facts/production-buildings.md` |
| shelters, beehive, nectar bush, lobster, duck      | `docs/game-facts/animals.md`              |
| fields, trees, bushes, farm buildings, measuring   | `docs/game-facts/farm.md`                 |
| barn, silo                                         | `docs/game-facts/storage.md`              |
| fishing lake (goods, fishing spots)                | `docs/game-facts/fishing-lake.md`         |
| game versions, update process                      | `docs/game-updates.md`                    |
| how a player uses the tools (commands, outputs)    | `docs/user-guide.md`                      |
| data the wiki lacks, estimates in use              | `docs/wiki-gaps.md`                       |
| which wiki pages the scraper reads                 | `docs/data-sources.md`                    |
| player-specific settings, profile schema           | `docs/player-profile.md`                  |
| how a tool works inside (steps, fallback, outputs) | `docs/tools/<tool>.md`                    |
| every command, option, output file                 | `docs/cli.md`                             |
| tool settings and defaults                         | `docs/settings.md`                        |
| data files, models, overrides                      | `docs/data-model.md`                      |
| graph nodes, edges, weights                        | `docs/graph-model.md`                     |
| package diagram, data flow                         | `docs/architecture.md`                    |
| module roles, entry points without file IO         | `docs/modules.md`                         |
| setup, tests, CI, release steps                    | `docs/development.md`                     |
| milestones, v2+ sub-versions                       | `docs/roadmap.md`                         |
| web app architecture, v2 decisions                 | `docs/v2-design.md`                       |

When you learn a new game fact (from the wiki, the web or the user), add a row to the matching `docs/game-facts/*.md` table in the documented format: `| Fact | Value | Source | Checked |`.

## Architecture rules

- A shared core (`src/config.py`, `src/settings.py`, `src/models`, `src/loaders`, `src/graph`) feeds three tools.
- The **Layout Planner** (`src/layout/`) and the **Production Planner** (`src/planner/`) are independent. Neither may import the other. Layout must work without production data.
- The **Combiner** (`src/combiner/`) is the only place that joins the two. It passes production quantities to the layout as a plain `Sizing` (`src/layout/sizing.py`); `tests/test_combiner.py` checks that layout and planner never import each other.
- Only the farm is laid out. Town and fishing lake get no layout; lake locations stay in the data for the Production Planner.
- `docs/architecture.md` holds the package diagram (Mermaid). A new import between top-level `src/` packages needs a new arrow there; `tests/test_architecture.py` fails until the diagram matches.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt       # pytest, ruff

python -m pytest                          # all tests must pass (no network needed)
ruff check src tests                      # lint; format check: ruff format --check src tests
python -m src all                         # unified CLI: graph, farm layout, plan, combined plan in one run
python -m src <graph|layout|plan|combine|scrape> [options]   # one tool; same options as its own entry point below
python -m src.main                        # graph + analysis into output/; level from the player config; validates the profile
python -m src.main --level 30             # override the player level
python -m src.layout                      # farm layout: output/layout.svg, layout.md, layout.json
# settings live only in config/design.json and config/planner.json (src/settings.py), never in CLI options
python -m src.planner                     # production plan: output/capacity.json, schedule.json, schedule.md
python -m src.combiner                    # layout sized by the plan: output/combined.json, combined.md, combined.svg
# tools/farm_map_editor.html: open in a browser to measure data/base_map.json + config/profile_map.json from a screenshot
python -m src.scraper --game-version 1.73 # refresh data/*.json, level_limits.json, mastery_bonuses.json, meta.json from the Fandom wiki (every level)
python -m src check-facts                 # docs/game-facts rows vs. the wiki → output/fact_check.md (network)
python -m src relocate [--layout PATH]    # current farm → combined.json (else layout.json): output/relocation.json / .md; not in `all`
python -m src migrate-map                 # one-file config/farm_map.json → config/profile_map.json (profile map; geometry in data/base_map.json)
python -m src farm-profile                # player, map, settings, templates → config/farm_profile.json
python -m src all --farm-profile config/farm_profile.json   # every tool reads the farm profile instead of the separate files
python -m src bundle                      # data/*.json + overrides + base map → output/data_bundle.json
python -m src wizard                      # questions → config/player.json
python -m src recommend [--levels 1,20,40] # level recommendations → output/recommendations/ (input of web/)
./serve-web.sh [--host] [1,20,40|stop]    # build the site and serve it locally (browser; --host: local network too); Ctrl+C stops
cd web && npm ci && npm run check && npm run build && npm run test:e2e   # static site: type check, build, Playwright
python -m src examples                    # regenerate config/examples/player_level_<N>.json after a re-scrape
# every option: docs/cli.md
```

## Code map

- `config/player.example.json` - the player profile (committed; currently holds the maintainer's values). `config/player.json` is local, git-ignored and takes precedence. `config/examples/player_level_<N>.json` are generated level-default profiles (`python -m src examples`, `src/planner/examples.py`); never hand-edit them, regenerate after a re-scrape (`tests/test_examples.py` fails when they are stale).
- `config/farm_map.example.json` - fixed farm buildings with empty positions. `config/farm_map.json` (local, git-ignored) holds the player's measured map size, fixed positions, the calibrated screenshot (`background`, `config/*.png` and `config/*.zip` are git-ignored; map sources live in the git-ignored `config/screenshots/` (GIMP file) and `config/reference/` (wiki plot maps)), the farm plots (`expansions`; section `base` always counts as unlocked) and hand-marked `zones` (`buildable` / `blocked` / `design`: existing decoration the layout keeps). `fixed` holds only buildings the game never moves (a movable location there is an error; the planner always places barn and silo). `current` is the current farm: placed copies of movable farm items, fields / trees / bushes only as `count`; the Layout Planner ignores it. A `movable` key in `fixed` (pre-v1.3 map) is a validation error asking to re-save in the editor.
- `config/profile_map.example.json` - the profile map (player's part of the farm map: unlocked plots, `design` zones, `current`, `background`); `config/profile_map.json` (local, git-ignored) wins over `config/farm_map.json`, which is read in memory with a warning. The shared geometry is `data/base_map.json`; `src/layout/migrate_map.py` splits a one-file map. The map editor reads and writes both files.
- `config/templates/` - design templates, one `<name>.json` each (git-ignored); `dairy_garden.example.json` is the committed example (`tests/test_templates.py` validates it).
- `tools/farm_map_editor.html` - self-contained browser tool that reads base map + profile map (or a one-file map: `mapKind`, `fromMaps`, `fromFarmMap`) and writes both (`toBaseMap`, `toProfileMap`, `mapJsonText`: byte-identical to `migrate-map`; cropping only a changed geometry) (step 8 "Current farm": `current`, ids and sizes from the loaded layout via `layoutSizes` / `sizeWarning`; `fromFarmMap` moves a pre-v1.3 measured barn / silo from `fixed` into `current`), exports PNGs and shows `layout.json` / `combined.json` as a view-only overlay (`fromLayout`, schema of `layout_to_dict`, block templates included). Step 9 "Templates" makes design templates on the farm map or on a separately calibrated design screenshot (the `tpl` surface, kept only in the browser; `cutTemplate`, `toTemplate`, `fromTemplate`, `templateWarnings`); keep its JSON in sync with `src/layout/templates.py`. Its pure JS functions sit between `CORE-START` / `CORE-END` and are tested with node in `tests/test_farm_map_editor.py`; keep the JSON it writes in sync with `src/layout/farm_map.py`.
- `src/schema.py` - `schema_version` of every input file: `Versioned` mixin (upgrades and drops the key on load), `upgrade(kind, data)`, `stamp(kind, data)` for writing; one tested migration per bump.
- `src/farm_profile.py` - `FarmProfile` (player, profile map, settings, templates in one file), `farm_profile_of(args)` for the `--farm-profile` option of every tool, `python -m src farm-profile`.
- `src/api/` - Core API without file IO (`production_plan`, `layout_plan`, `combined_plan`, `relocation_plan`): dicts or a data bundle in, `{"result", "files"}` out; every tool CLI only reads the files and writes `files`.
- `src/config.py` - `PlayerConfig` (level, mastery system, barn / silo, fields, fishing spots, per-location `LocationProgress`), `load_player_config()`, `validate_player_config()`.
- `src/settings.py` - tool settings: `DesignSettings` (`config/design*.json`, one flat object), `PlannerSettings` (`config/planner*.json`: `production`, `combiner`), the built-in defaults every tool imports, loaders returning the source file.
- `src/models/` - pydantic models: `Location` (with `Area`, footprint, `movable`, `rotatable`, `animal_capacity`, `base_slots`, `max_slots`, `lifetime_yield` / `lifetime_harvests`), `MasteryBonus` (time reduction per building and star), `Resource` (`growth_time_seconds`), `Recipe` (`production_time_seconds`, `production_time_3star_seconds`), `LevelLimits` (`field_grants`, `location_instances`).
- `src/loaders/json_loader.py` - loads `data/*.json`, merges `data/overrides/*.json` (`null` = skip), validates into a `DataSet` with optional `level_limits` and `mastery_bonuses`, optional level filter; `load_data(<bundle file>)` / `dataset_from_bundle` read a data bundle. `src/loaders/bundle.py` writes it (`python -m src bundle`).
- `src/graph/` - graph builder, edge types (`relationship.py`), weights (`weighting.py`), analysis (`analysis.py`: proximity, Louvain blocks, centrality, paths).
- `src/layout/` - Layout Planner: `blocks.py` (named blocks, anchor method), `fields.py` (dedicated fields per block by crop demand), `support.py` (nectar bush → beehive tree, peanut bush → squirrel house), `inventory.py` (copies: profile → level → placeholder), `packing.py` (greedy rect packing; coupling, size or flow order, pull toward the area centre), `planner.py` (`plan_layout`; `strategy` auto / coupling / size / flow; placing every block comes first: lowers `item_gap` first, then drops the design templates, then the block reserve in 1 % steps; optional `sizing`, optional `templates` → `PlacedTemplate` per block), `templates.py` (design template model and loader: `config/templates/<name>.json`, else `<name>.example.json`; `BlockTemplate` with mode `reserve` / `arrange`), `sizing.py` (`Sizing`: copies, fields per crop, goods flows, extra reserves from the Combiner), `farm_map.py` (farm map model, `outline_segments`), `design.py` (paths as a greedy Steiner tree from the hub: main path to the key buildings and the Storage block first, then side paths; `shortest`, `straight` (turn cost) or `stepped` style, `main_path_style`, `main_path_width` 2 as a diagonal second lane narrowed where it does not fit, terminals of one or more rects, cut-off key buildings reached at their connection point, decoration band outside design zones, figures: corners, detour ratio), `render_svg.py` (isometric grid; `scale`, legend `offset`), `visuals.py` (one SVG per block on its own grid and a collage of every block, setting `block_images`; old SVGs of the target directory are removed), `describe.py`, `cli.py`.
- `src/planner/` - Production Planner: `profile.py` (`resolve_profile`: every `null` → level default), `mastery.py` (`stars` / `workbench` modifiers, chosen by `mastery_system`), `capacity.py` (storage, fields, parallel lines, queues, max rates), `quantities.py` (scipy linear program, four lexicographic solves), `schedule.py` (interval suggestion, recommendations, actions per login), `run.py` (`run_planner`: one full run, shared with the Combiner), `examples.py` (level-default profiles), `wizard.py` (interactive sparse profile; `ask` / `say` injectable for tests), `cli.py`. Machines produce one item at a time: copies are parallel, slots are only a queue. Fields, animals and trees are served only at a login. Goods without a production model (ores from the mine, fish) are external: capped at what the balance needs, never planned.
- `src/combiner/` - Combiner (farm): `combine.py` (`sizing_from_plan`: fields per crop by use, recommended trees / bushes, goods flows without fields; `upcoming_unlocks` for the lookahead; `flow_links`, `free_tiles`; `combine`), `report.py` (`combined.json` / `combined.md`, layout and schedule sections demoted under one title), `cli.py`.
- `src/exporters/` - JSON / CSV / GraphML export. New node attributes must be added to the CSV column list and the GraphML key list.
- `src/scraper/` - `wiki_client.py` (MediaWiki API: parse, wikitext, categories, allpages, revisions), `parsers/` (locations incl. infobox base slots, resources, recipes, level_limits, masteries), `durations.py`, `normalizer.py` (`normalize`, `build_level_limits`, `build_mastery_bonuses`), `writer.py`, `cli.py`, `factcheck.py` (`python -m src check-facts`: game fact rows with `wiki:` sources vs. page revisions and page numbers; the client is injectable, tests use a fake wiki).
- `src/relocation/` - relocation plan (imports neither planner; reads the layout JSON): `relocate.py` (`load_layout`, `check_layout_map`, `check_current` (ids, movable farm items, footprint incl. rotation), `plan_relocation`: keep / store / place, reserved, surplus, missing; `new_slot_simpler`), `report.py` (`relocation.json` / `.md`), `cli.py`.
- `src/recommend/` - level recommendations (`build.py`: `level_recommendation` runs `combined_plan` with `example_profile`, default settings and the base map with an empty profile map; `recommendations` adds `index.json`; `cli.py`: `--levels` ranges). Output stamped `recommendation` / `recommendation_index` in `src/schema.py`; `web/src/data.ts` checks the same versions.
- `web/` - static site (Astro 7, TypeScript, one Svelte island). `src/data.ts` reads `RECOMMENDATIONS_DIR` (default `../output/recommendations`) at build time; two languages: English at the root, Hungarian under `/hu/`; every UI string in `content/en.json` / `hu.json` with the same keys and placeholders (`tests/test_web_content.py`; the Fan Content Policy text stays English), helpers in `src/i18n.ts` (`content`, `fill`, `localePath`, `switchPath`, `hours`); pages in `src/views/` (`Home`, `Level`, `HowItWorks`, `Usage`) with thin wrappers in `pages/` and `pages/hu/`, `layouts/[level].svg.ts` shared; game item names stay English (`label()`). Design after the portfolio site: Tailwind v4 tokens and shared classes in `src/styles/global.css` (dark mode via `.dark` on `<html>`), `components/Header.astro` (menu, hamburger below `lg`, language switch, theme toggle), `components/Footer.astro` (Fan Content Policy notice, data licence, portfolio link, version badges), `components/BarnLogo.astro` (logo; `public/favicon.svg` is the same drawing); `tests/site.spec.ts` (Playwright, mobile + desktop, both languages and themes). npm versions exact and at least two weeks old. Generated recommendations are never committed; `.github/workflows/pages.yml` builds and deploys after green CI on `main`.
- `src/cli.py` (+ `src/__main__.py`) - unified CLI: `python -m src <command>` dispatches to each tool's `main(argv)`; `all` runs graph → layout → plan → combine with the shared options. A new tool gets a `COMMANDS` entry.
- `src/main.py` - graph CLI (`python -m src graph`).
- `data/overrides/` - hand-maintained shared facts the wiki lacks; its `README.md` explains how to measure them.
- `docs/` - game knowledge and design analyses (see "Read first").
- `tests/` - pytest suite, one file per module area; `tests/fixtures/wiki/` holds trimmed wiki HTML and wikitext for scraper tests.

## Conventions

### General

- Write code, identifiers, comments, docs and commit messages in English.
- Never hard-code a player level. Take it from `PlayerConfig` or from a `--level` argument. Tests must not depend on a specific level snapshot.
- Never present a guess as a fact. If the wiki lacks a value the code needs, use an estimate derived from existing data (or the user's game experience), put it where the code reads it, and add a row to `docs/wiki-gaps.md` with its basis and status. Gaps never block a milestone.
- Every new module gets tests in `tests/`. New scraper parsing needs a fixture-based test in `tests/test_scraper.py` (no network in tests).
- `output/` is generated and git-ignored. Do not commit it.
- Tool settings (how a tool works) go into `config/design*.json` or `config/planner*.json` via `src/settings.py`, never into new CLI options. The CLI only says what to run (level, file paths). The one kind of exception: flags that change only the exit code of a check, not its result (`check-facts --fail-on-findings`). A new setting needs a model field, a value in the example file, a `docs/settings.md` table row and a test.
- When a roadmap item is finished, tick it in `docs/roadmap.md`, update its "Current status" line and the status line of `README.md`. A change to how a tool works goes into its `docs/tools/*.md` page in the same commit.
- Python 3.14+ (`requires-python` in `pyproject.toml`); ruff targets it, so 3.14-only syntax is fine. CI (`.github/workflows/ci.yml`) runs pytest, `ruff check` and `ruff format --check` on every push.
- Releases: the version lives only in `pyproject.toml`. A finished milestone bumps it, adds a `CHANGELOG.md` entry (`## [x.y.z] - date`, a few lines) and gets a `vX.Y.Z` git tag on its commit.

### Data model

- Entity ids are lower-case snake_case English, and validators enforce this.
- Models use `extra="forbid"`. Every new data field needs a model change in the same commit.
- Keep the data model close to 3NF so it can later move to PostgreSQL. Level-gated limits go in `level_limits.json`.
- Durations are stored in seconds (`*_time_seconds`).
- Footprints are two atomic ints (`footprint_width`, `footprint_height`), both or neither. Width is the ↘ edge and height the ↙ edge, seen from the top corner.
- Fixed buildings have `movable: false`. The layout planner never moves them.
- `rotatable: true` allows swapping width and height. Without it, non-square items are placed only as stored.
- Every fruit tree and bush kind is its own location (`apple_tree`, `raspberry_bush`, `nectar_bush`), never a generic `tree` / `bush`.
- External or premium recipe inputs (vouchers, diamonds) may appear in recipes but never become graph nodes.

### Where data goes

| Kind                                                                  | Place                                                                                           |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Per-entity data from wiki tables                                      | `data/*.json` via the scraper; fix problems in the scraper or normalizer, never by hand-editing |
| Per-entity data the wiki lacks                                        | `data/overrides/*.json` (existing ids patched field by field, new ids added)                    |
| Game rules (min / max, costs, mechanics)                              | `docs/game-facts/*.md`; move into data or code only when code needs them                        |
| Anything a player buys, upgrades or earns                             | the player profile (`config/player*.json`)                                                      |
| The player's farm map and building positions                          | `data/base_map.json` (shared geometry), `config/profile_map*.json`, `config/farm_map*.json`     |
| Tool settings: layout / design taste, planner and Combiner parameters | `config/design*.json`, `config/planner*.json`                                                   |

### Player profile

- Counts are totals over all copies (`slots`, `animals`). Mastery (`mastery_stars`, `workbench_level`) is per building type, because copies share production hours.
- `null` means "use the level default / let the planner recommend". Fields, trees and bushes are optional on purpose.
- `mastery_system` selects the production-time modifier: `stars` is the default, `workbench` must stay pluggable.
- When a new configurable location appears in the data, add it to `config/player.example.json`; `tests/test_config.py` checks the example against the data.

## Game update check

When the user mentions a new game update, or `data/meta.json` looks outdated, follow `docs/game-updates.md`: read the update notes, map each change with the "Mechanic → affected part" table, re-scrape with `--game-version`, run the tests, record the version there and new wiki gaps in `docs/wiki-gaps.md`.
