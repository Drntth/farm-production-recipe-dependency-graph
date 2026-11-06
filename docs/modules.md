# Modules

Where each part of the code lives and what it does.

```text
farm-production-recipe-dependency-graph/
├── .github/workflows/ci.yml          # CI: pytest, ruff check, ruff format --check
├── docs/                              # project knowledge, see docs/README.md
│   ├── README.md                      # index, where knowledge lives, fact table format
│   ├── game-facts/                    # game rules by category (wiki + in-game)
│   │   ├── animals.md
│   │   ├── farm.md
│   │   ├── fishing-lake.md
│   │   ├── production-buildings.md
│   │   └── storage.md
│   ├── tools/                         # how each tool works: layout-planner, production-planner, combiner, relocation, map-editor
│   ├── architecture.md                # package diagram (tested) and data flow
│   ├── cli.md                         # every command, option and output file
│   ├── data-model.md                  # data/*.json and the pydantic models
│   ├── development.md                 # setup, checks, tests, CI, releases
│   ├── graph-model.md                 # nodes, edges, weights, analysis
│   ├── modules.md                     # this file
│   ├── roadmap.md                     # milestones v0.3 … v1.6 and the v2+ sub-versions
│   ├── v2-design.md                   # web app target architecture and v2 decisions
│   ├── settings.md                    # config/design.json and config/planner.json keys
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
│   ├── templates/                     # design templates <name>.json (git-ignored; one committed example)
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
│   ├── relocation/                    # relocation plan: current farm → layout (imports no planner)
│   │   ├── cli.py                     # python -m src relocate
│   │   ├── relocate.py                # checks, keep / store / place matching
│   │   └── report.py                  # relocation.json / relocation.md
│   ├── __main__.py                    # python -m src <command>
│   ├── cli.py                         # unified CLI: every command of COMMANDS, and all
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
│   ├── layout/                        # Layout Planner (farm)
│   │   ├── blocks.py                  # named blocks (anchor method), flow order
│   │   ├── cli.py                     # python -m src.layout
│   │   ├── describe.py                # layout.md / layout.json
│   │   ├── design.py                  # design layer: main / side paths, decoration band
│   │   ├── farm_map.py                # config/farm_map*.json model and loader
│   │   ├── fields.py                  # dedicated fields per block (crop demand)
│   │   ├── inventory.py               # copies per location (profile → level)
│   │   ├── packing.py                 # greedy rectangle packing on the tile grid
│   │   ├── planner.py                 # plan_layout(): blocks → frames → farm
│   │   ├── render_svg.py              # isometric SVG with tile grid
│   │   ├── sizing.py                  # block sizes from production quantities (Combiner input)
│   │   ├── support.py                 # support relations (nectar bush → beehive tree, peanut bush → squirrel house)
│   │   ├── templates.py               # design template model and loader (config/templates/)
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
│   └── farm_map_editor.html           # screenshot calibration → config/farm_map.json, PNG exports
├── tests/
│   ├── fixtures/wiki/                 # trimmed wiki HTML / wikitext for scraper tests
│   ├── test_analysis.py
│   ├── test_architecture.py           # docs/architecture.md diagram vs. the real imports
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
│   ├── test_relocation.py
│   ├── test_scraper.py
│   ├── test_settings.py
│   ├── test_templates.py
│   └── test_wizard.py
├── AGENTS.md                          # instructions for coding agents
├── CHANGELOG.md                       # one entry per version
├── CLAUDE.md -> AGENTS.md             # symlink
├── LICENSE
├── README.md
├── pyproject.toml                     # project metadata, version, ruff settings (not a package)
├── requirements.txt
└── requirements-dev.txt               # pytest, ruff

## Entry points without file IO

The CLIs read files and write `output/`; the functions below take objects and return results, so other front ends can reuse them.

| Function                                                                                  | Module                       | Returns                                                         |
| ----------------------------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------- |
| `load_data(data_dir, max_level=None, *, apply_data_overrides=True)`                       | `src/loaders/json_loader.py` | `DataSet` (reads `data/`)                                       |
| `build_graph(dataset)`                                                                    | `src/graph/graph_builder.py` | `nx.DiGraph`                                                    |
| `analysis_summary(G, *, top_n=8, max_hops=…)`                                             | `src/graph/analysis.py`      | the `analysis.json` payload                                     |
| `plan_layout(dataset, *, level, player=None, farm_map=None, …, sizing=None, templates=None)` | `src/layout/planner.py`      | `Layout`; `layout_to_dict` / `layout_to_markdown` in `describe.py` |
| `render_svg(layout, path=None, title=None, *, scale=1.0, offset=(0, 0))`                  | `src/layout/render_svg.py`   | SVG text (also written when `path` is given)                    |
| `run_planner(player, dataset, *, login_interval=None, storage_share=0.5, min_efficiency=0.8)` | `src/planner/run.py`         | `PlanRun`: profile, capacity, plans, chosen plan, schedule          |
| `combine(full, player, farm_map=None, *, lookahead=5, …)`                                 | `src/combiner/combine.py`    | `CombinedPlan`; `combined_to_dict` / `combined_to_markdown` in `report.py` |
| `plan_relocation(layout, farm_map, dataset)`                                              | `src/relocation/relocate.py` | `RelocationPlan` from a layout dict                             |
| `run_wizard(dataset, ask, say)`                                                           | `src/planner/wizard.py`      | `PlayerConfig` (`ask` / `say` are injected)                     |

Loaders for the other inputs: `load_player_config` (`src/config.py`), `load_design_settings` / `load_planner_settings` (`src/settings.py`), `load_farm_map` (`src/layout/farm_map.py`), `load_templates` (`src/layout/templates.py`), `load_layout` (`src/relocation/relocate.py`).
