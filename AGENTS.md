# AGENTS.md

Instructions for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

Commit prefix: [HAYDAY-PROJECT]

## Project

The project analyses Hay Day production chains. It turns locations, resources and recipes into a weighted directed graph (NetworkX). From that graph it detects production blocks for layout planning, and later plans production quantities. The concept, architecture and roadmap are in `README.md`.

- Milestones done: **v0.5** (data foundation), **v0.6** (standalone Layout Planner for the farm: named blocks with footprints, isometric SVG grid, fixed / rotatable items, support relations, measured `config/farm_map.json` with plots and zones, Storage block, animal feeding recipes).
- Current milestone: **v0.7** (Production Planner: capacity model, quantities, mastery modifier, profile defaults, schedule).

## Read first

Game knowledge is already collected. **Before researching the game or the wiki, read [docs/README.md](docs/README.md)** and the relevant file:

| Question about…                                  | File                                         |
| ------------------------------------------------ | -------------------------------------------- |
| slots, mastery, building copies, costs           | `docs/game-facts/production-buildings.md`    |
| shelters, beehive, nectar bush, lobster, duck    | `docs/game-facts/animals.md`                 |
| fields, trees, bushes, farm buildings, measuring | `docs/game-facts/farm.md`                    |
| barn, silo                                       | `docs/game-facts/storage.md`                 |
| fishing lake, town                               | `docs/game-facts/fishing-lake.md`, `town.md` |
| game versions, update process, wiki gaps         | `docs/game-updates.md`                       |
| which wiki pages the scraper reads               | `docs/data-sources.md`                       |
| player-specific settings, profile schema         | `docs/player-profile.md`                     |

When you learn a new game fact (from the wiki, the web or the user), add a row to the matching `docs/game-facts/*.md` table in the documented format: `| Fact | Value | Source | Checked |`.

## Architecture rules

- A shared core (`src/config.py`, `src/models`, `src/loaders`, `src/graph`) feeds three tools.
- The **Layout Planner** (`src/layout/`) and the **Production Planner** (planned `src/planner/`) are independent. Neither may import the other. Layout must work without production data.
- The **Combiner** (planned) is the only place that joins the two.
- Layout areas: `farm` (graph-driven), plus `town` and `fishing_lake`. Town and fishing lake have no quantity calculations.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt       # ruff

python -m pytest                          # all tests must pass (no network needed)
ruff check src tests                      # lint and format check: ruff format --check src tests (ruff from requirements-dev.txt)
python -m src.main                        # graph + analysis into output/; level from the player config; validates the profile
python -m src.main --level 30             # override the player level
python -m src.layout                      # farm layout: output/layout.svg, layout.md, layout.json
# tools/farm_map_editor.html: open in a browser to measure config/farm_map.json from a screenshot
python -m src.scraper --game-version 1.72 # refresh data/*.json, level_limits.json, meta.json from the Fandom wiki
```

## Code map

- `config/player.example.json` - the player profile (committed; currently holds the maintainer's values). `config/player.json` is local, git-ignored and takes precedence.
- `config/farm_map.example.json` - fixed farm buildings with empty positions. `config/farm_map.json` (local, git-ignored) holds the player's measured map size, fixed positions, the calibrated screenshot (`background`, `config/*.png` and `config/*.zip` are git-ignored; map sources live in the git-ignored `config/screenshots/` (GIMP file) and `config/reference/` (wiki plot maps)), the farm plots (`expansions`; section `base` always counts as unlocked) and hand-marked `zones` (`buildable` / `blocked`). Barn and silo are optional there: without a position the planner places them as the Storage block.
- `tools/farm_map_editor.html` - self-contained browser tool that writes `farm_map.json` and exports PNGs. Its pure JS functions sit between `CORE-START` / `CORE-END` and are tested with node in `tests/test_farm_map_editor.py`; keep the JSON it writes in sync with `src/layout/farm_map.py`.
- `src/config.py` - `PlayerConfig` (level, mastery system, barn / silo, fields, fishing spots, per-location `LocationProgress`), `load_player_config()`, `validate_player_config()`.
- `src/models/` - pydantic models: `Location` (with `Area`, footprint, `movable`, `rotatable`, `animal_capacity`), `Resource` (`growth_time_seconds`), `Recipe` (`production_time_seconds`, `production_time_3star_seconds`), `LevelLimits` (`field_grants`, `location_instances`).
- `src/loaders/json_loader.py` - loads `data/*.json`, merges `data/overrides/*.json` (`null` = skip), validates into a `DataSet` with optional `level_limits`, optional level filter.
- `src/graph/` - graph builder, edge types (`relationship.py`), weights (`weighting.py`), analysis (`analysis.py`: proximity, Louvain blocks, centrality, paths).
- `src/layout/` - Layout Planner: `blocks.py` (named blocks, anchor method), `fields.py` (dedicated fields per block by crop demand), `support.py` (nectar bush → beehive tree), `inventory.py` (copies: profile → level → placeholder), `packing.py` (greedy rect packing; coupling or size order, pull toward the area centre), `planner.py` (`plan_layout`; `strategy` auto / coupling / size; lowers the block reserve in 1 % steps until every block fits), `farm_map.py` (model, `outline_segments`), `render_svg.py` (isometric grid), `describe.py`, `cli.py`.
- `src/exporters/` - JSON / CSV / GraphML export. New node attributes must be added to the CSV column list and the GraphML key list.
- `src/scraper/` - `wiki_client.py` (MediaWiki API: parse, wikitext, categories, allpages, revisions), `parsers/` (locations, resources, recipes, level_limits), `durations.py`, `normalizer.py` (`normalize`, `build_level_limits`), `writer.py`, `cli.py`.
- `src/main.py` - CLI entry point.
- `data/overrides/` - hand-maintained shared facts the wiki lacks; its `README.md` explains how to measure them.
- `docs/` - game knowledge and design analyses (see "Read first").
- `tests/` - pytest suite, one file per module area; `tests/fixtures/wiki/` holds trimmed wiki HTML for scraper tests.

## Conventions

### General

- Write code, identifiers, comments, docs and commit messages in English.
- Never hard-code a player level. Take it from `PlayerConfig` or from a `--level` argument. Tests must not depend on a specific level snapshot.
- Never invent game values. If no source exists, leave the field empty and say so; record ambiguous sources in `docs/`.
- Every new module gets tests in `tests/`. New scraper parsing needs a fixture-based test in `tests/test_scraper.py` (no network in tests).
- `output/` is generated and git-ignored. Do not commit it.
- When a roadmap item is finished, tick it in `README.md` and update the "Current status" line and the milestone lines above.

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

| Kind                                      | Place                                                                                           |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Per-entity data from wiki tables          | `data/*.json` via the scraper; fix problems in the scraper or normalizer, never by hand-editing |
| Per-entity data the wiki lacks            | `data/overrides/*.json` (existing ids patched field by field, new ids added)                    |
| Game rules (min / max, costs, mechanics)  | `docs/game-facts/*.md`; move into data or code only when code needs them                        |
| Anything a player buys, upgrades or earns | the player profile (`config/player*.json`)                                                      |
| The player's farm area and fixed building positions | `config/farm_map*.json`                                                               |

### Player profile

- Counts are totals over all copies (`slots`, `animals`). Mastery (`mastery_stars`, `workbench_level`) is per building type, because copies share production hours.
- `null` means "use the level default / let the planner recommend". Fields, trees and bushes are optional on purpose.
- `mastery_system` selects the production-time modifier: `stars` is the default, `workbench` must stay pluggable.
- When a new configurable location appears in the data, add it to `config/player.example.json`; `tests/test_config.py` checks the example against the data.

## Game update check

When the user mentions a new game update, or `data/meta.json` looks outdated, follow `docs/game-updates.md`: read the update notes, map each change with the "Mechanic → affected part" table, re-scrape with `--game-version`, run the tests, and record the version and any new wiki gaps there.
