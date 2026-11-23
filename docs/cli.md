# Command reference

Every command of the tools. The [user guide](user-guide.md) explains the workflow; this page lists the commands and the output files.

```bash
# install (Python 3.14 or newer)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for development: pytest, ruff

# personal player config (optional; otherwise the example is used)
cp config/player.example.json config/player.json

# run tests and lint (the same checks run in CI)
python -m pytest
ruff check src tests
ruff format --check src tests

# unified CLI: one entry point, one command per tool
python -m src                       # list the commands
python -m src all                   # graph, farm layout, plan and combined plan in one run
python -m src layout --level 30     # any tool: python -m src <graph|layout|plan|combine|scrape> [options]
python -m src wizard                # questions → config/player.json (sparse profile)
python -m src examples              # regenerate config/examples/player_level_<N>.json
python -m src check-facts           # docs/game-facts vs. the wiki → output/fact_check.md (network)
python -m src relocate              # current farm → combined.json (else layout.json): output/relocation.*
python -m src relocate --layout output/layout.json
python -m src migrate-map           # one-file config/farm_map.json → config/profile_map.json
python -m src farm-profile          # player, map, settings, templates → config/farm_profile.json
python -m src all --farm-profile config/farm_profile.json   # every tool from one farm profile
python -m src bundle                # data/ with the overrides → output/data_bundle.json
python -m src recommend             # level recommendations 1-100 → output/recommendations/ (the web site)
python -m src recommend --levels 1,20,40
python -m src web-files             # core.zip, data bundle, level defaults → web/public/py/ ("My farms" page)

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
# optional: measure config/farm_map.json with tools/farm_map_editor.html (see docs/tools/map-editor.md)
# settings (gap, reserve, strategy, design layer): config/design.json, see docs/settings.md
python -m src.layout
python -m src.layout --level 30
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
├── capacity.json                      # python -m src.planner
├── schedule.json
├── schedule.md
├── combined.json                      # python -m src.combiner
├── combined.md
├── combined.svg
├── blocks/                            # one SVG per block + collage.svg (block_images)
├── combined_blocks/                   # the same for the combined layout
├── relocation.json                    # python -m src relocate
├── relocation.md
├── data_bundle.json                   # python -m src bundle
├── recommendations/                   # python -m src recommend: level_N.json, level_N.svg, index.json, map.json
└── fact_check.md                     # python -m src check-facts
```

Update data from the wiki (every level; `--level N` cuts it off):

```bash
python -m src.scraper --game-version 1.73
```

## Options

Every command takes `--help`. The options only say what to run (level, file paths); how a tool works is set in [settings.md](settings.md).

`--farm-profile PATH` (graph, layout, plan, combine, relocate, all) reads the player profile, the profile map, both settings files and the design templates from one farm profile ([data-model.md](data-model.md#farm-profile)). It replaces `--player-config`, `--map`, `--design-config` and `--planner-config`; giving one of them as well is an error. `--level` and `--data-dir` still apply.

`--data-dir` is always the data directory (it also holds `meta.json` and `base_map.json`); a data bundle file there is an error. The bundle is read by the Core API and `load_data` ([modules.md](modules.md)).

| Command                       | Options                                                                                                                                                                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `graph` (`src.main`)          | `--data-dir` (data), `--level` / `--max-level`, `--player-config`, `--output-dir` (output), `--formats json graphml csv` (all), `--no-analysis`, `--farm-profile`                                                                       |
| `layout` (`src.layout`)       | `--data-dir`, `--level`, `--player-config`, `--farm-map` / `--map` (config/profile_map.json with DATA_DIR/base_map.json, else the one-file config/farm_map.json, else the example), `--output-dir`, `--design-config`, `--farm-profile` |
| `plan` (`src.planner`)        | `--data-dir`, `--level`, `--player-config`, `--output-dir`, `--planner-config`, `--farm-profile`                                                                                                                                        |
| `combine` (`src.combiner`)    | `--data-dir`, `--level`, `--player-config`, `--farm-map` / `--map`, `--output-dir`, `--design-config`, `--planner-config`, `--farm-profile`                                                                                             |
| `relocate` (`src.relocation`) | `--data-dir`, `--layout` (OUTPUT_DIR/combined.json, else layout.json), `--farm-map` / `--map`, `--output-dir`, `--farm-profile`                                                                                                         |
| `scrape` (`src.scraper`)      | `--level` / `--max-level` (every wiki level), `--output-dir` (data), `--delay` seconds between requests (0.5), `--game-version` (stored in `meta.json`)                                                                                 |
| `examples`                    | `--data-dir`, `--output-dir` (config/examples)                                                                                                                                                                                          |
| `wizard`                      | `--data-dir`, `--output` (config/player.json)                                                                                                                                                                                           |
| `check-facts`                 | `--facts-dir` (docs/game-facts), `--output-dir`, `--fail-on-findings` (exit code 3 when a row changed or its page failed)                                                                                                               |
| `migrate-map`                 | `--map` (config/farm_map.json), `--data-dir`, `--output` (config/profile_map.json), `--base-output` (also write the geometry as a base map), `--force`                                                                                  |
| `farm-profile`                | `--player-config`, `--map`, `--design-config`, `--planner-config` (the same defaults as the tools), `--data-dir`, `--name`, `--output` (config/farm_profile.json), `--force`                                                            |
| `recommend`                   | `--data-dir` (data), `--levels` (1-100; ranges and lists: `1-10,40`), `--output-dir` (output/recommendations)                                                                                                                           |
| `bundle`                      | `--data-dir` (data), `--output` (output/data_bundle.json)                                                                                                                                                                               |
| `web-files`                   | `--data-dir` (data), `--output-dir` (web/public/py)                                                                                                                                                                                     |
| `all`                         | `--level`, `--player-config`, `--data-dir`, `--output-dir`, `--map`, `--design-config`, `--planner-config`, `--farm-profile`; each step gets the ones it accepts                                                                        |

## Quick list

Copy-paste block with the commands of the development loop (setup, checks, tools, web):

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
cd web && npm ci && npm run check && npm run format:check && npm run build && npm run test:e2e   # static site: type check, Prettier, build, Playwright
python -m src examples                    # regenerate config/examples/player_level_<N>.json after a re-scrape
# every option: docs/cli.md
```
