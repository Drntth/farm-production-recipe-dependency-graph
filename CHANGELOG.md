# Changelog

One entry per version. The version is kept in `pyproject.toml`; the details of each milestone are in [docs/roadmap.md](docs/roadmap.md). Versions before 1.0.0 have no git tag.

## [Unreleased]

- Map editor reads and writes the split map: `data/base_map.json` and `config/profile_map.json` open together (or a one-file map, which it splits) and save as two files identical to `migrate-map`; only a changed geometry is cropped, together with the profile map. It no longer writes the one-file map.
- Fix: a map opened in the editor without its screenshot kept the image size on save (it wrote 0).

## [2.0.0] - 2026-11-06

- Core API (`src/api`): plan, layout, combined plan and relocation plan as entry points without file IO (dict or data bundle in, `{"result", "files"}` out); every CLI calls them and its outputs are byte-identical to v1.6.3.
- Farm map split into the base map (`data/base_map.json`, committed) and the profile map (`config/profile_map.json`); `python -m src migrate-map` splits a one-file map, which the tools still read with a warning. The map editor keeps the one-file format until v2.0.1.
- Farm profile: `python -m src farm-profile` puts the player profile, profile map, settings and templates of one farm into one JSON; every tool and `all` take `--farm-profile`.
- `schema_version` on every input file (player, map, settings, templates, farm profile, data bundle) with tested migrations (`src/schema.py`); a newer version is an error.
- Data bundle: `python -m src bundle` writes `output/data_bundle.json`; `load_data` and the Core API read it.

## [1.6.3] - 2026-11-06

- v2+ plan: `docs/v2-design.md` (web app architecture, Pyodide measurements, base map / profile map split, decisions) and the v2.0-v4.0 sub-versions with done criteria in `docs/roadmap.md`; `CONTEXT.md` gained the planned v2 terms.
- README: the game data in `data/` (overrides included) is CC BY-SA 3.0 like the Hay Day Wiki, the code stays MIT; the Supercell Fan Content Policy notice is in the disclaimer.
- `docs/game-facts/farm.md`: per-plot unlock cost ranges and totals of every expansion section from the wiki.

## [1.6.2] - 2026-11-03

- Docs reorganized: a short README; the tool details moved to `docs/tools/` (layout planner, production planner, combiner, relocation, map editor); new `docs/cli.md` (every option), `docs/settings.md`, `docs/data-model.md`, `docs/graph-model.md`, `docs/modules.md` (entry points without file IO), `docs/development.md` and `docs/roadmap.md`; `docs/README.md` indexes them all.
- Docs corrected against the code: barn and silo are whole entities in the overrides and go into `current`, never `fixed`; `design.json` is one flat object; the layout groups blocks with the anchor method; schedule, capacity, relocation and combined JSON keys listed; `CONTEXT.md` gained the layout, graph and production terms.
- Fix: the GraphML export keeps `max_in_barn` and `description`.
- Fix: with `strategy: all` the layout summary log describes the main `layout`, not the last fixed-strategy run.
- Stale docstrings updated (graph type, edge merge, proximity propagation, fixed items, template example); the unused `main()` in `src/__init__.py` removed.
- `pyproject.toml` version follows the tags again (it stayed at 1.6.0 in 1.6.1).

## [1.6.1] - 2026-10-29

- `docs/architecture.md`: Mermaid diagrams of the package dependencies and the data flow; `tests/test_architecture.py` checks the package diagram against the real imports.

## [1.6.0] - 2026-10-28

- Data for every wiki level (game 1.73): the scraper has no level cap by default, field grants of "1 field" are read, new tree, peanut bush and squirrel house footprints are estimates in `data/overrides/`.
- The scraper no longer reads the player profile: `--player-config` is removed, use `--level N` to cut off.
- Squirrel house and peanut bush: peanuts per pair of squirrels into the silo, peanut bush recommendations, a support relation in the layout.
- Fact checker: number words count, derived steps are skipped; the game fact rows were re-checked.
- Combined report: weighted flow distance; the `item_gap: 1` fallback on the measured farm is explained (not enough land).
- Polish: one override log line per file, crop names in the combined block table, stale layout outputs removed.

## [1.5.0] - 2026-10-28

- Design templates: `config/templates/<name>.json` (buildings and decoration tiles, one committed example), assigned to blocks in `templates` of `config/design.json`.
- Mode `reserve` keeps the template area free in the block frame; mode `arrange` places its buildings at their template positions and packs the rest of the block around them (copies not owned become reserved space).
- Templates are dropped with a warning when the blocks do not fit (after `item_gap`, before the reserve); `layout.json` / `combined.json` list each block's template and `templates_dropped`; the SVG and the editor overlay draw them.
- Map editor step 9 "Templates": cut a template out of the farm map or mark one on another design's calibrated screenshot, then download or reopen it.

## [1.4.0] - 2026-10-28

- Path network: the main path reaches the key buildings and the Storage block first, side paths join every other block to the nearest point of the network.
- `main_path_width` (1 or 2): a second lane on the main path, narrowed to 1 tile where it does not fit; the report counts the narrowed tiles.
- New `path_style` `stepped` (staircase along the straight line) and `main_path_style` for mixed styles.
- Design figures: main and side path tiles apart; the main path is drawn darker in the SVG; `layout.json` lists `main_paths`.

## [1.3.0] - 2026-10-28

- Current farm: a `current` list in the farm map (placed copies of movable farm items, fields / trees / bushes as counts), measured in the new map editor step 8 with the ids and sizes of the loaded layout; the Layout Planner ignores it.
- `fixed` holds only buildings the game never moves: barn and silo and the `movable` flag left it; old farm maps fail with a clear error (the editor moves a measured barn / silo into `current` on load).
- `python -m src relocate [--layout PATH]`: keep / store / place lists from the current farm to `combined.json` (else `layout.json`), reserved space, surplus and missing copies, a note when a new layout slot is simpler; `output/relocation.md` / `.json`.

## [1.2.0] - 2026-10-28

- Map editor step 7 "Layout overlay": loads `output/layout.json` or `output/combined.json` and draws block frames, items, paths and the decoration band as a switchable `layout` layer (view only).
- A warning instead of any shift when the layout was planned on a map of another size or without a farm map.

## [1.1.0] - 2026-10-28

- Python 3.14 required (`requires-python = ">=3.14"`).
- `pyproject.toml` with the project metadata, the version and the ruff settings; installation stays with `requirements*.txt`.
- `pytest` moved to `requirements-dev.txt`.
- GitHub Actions CI: `pytest`, `ruff check` and `ruff format --check` on Python 3.14 with Node, on every push and pull request.
- This changelog; git tags from v1.0.0 on.

## [1.0.0] - 2026-10-15

- Unified CLI `python -m src <command>` with `all`; settings only in `config/design.json` and `config/planner.json`.
- Design options (path style, item gap, design zones), block images, game fact checker (`check-facts`).
- Profile wizard, level-default profile examples, user guide.

## [0.9.0] - 2026-10-14

- Combiner: farm layout sized by the production plan, `flow` block order, lookahead reserves, one combined report.

## [0.8.0] - 2026-10-14

- Design layer: paths between blocks and key buildings, decoration band.
- Town and fishing lake layouts (later dropped: only the farm is laid out).

## [0.7.0] - 2026-10-14

- Production Planner: profile defaults, mastery, capacity model, linear-program quantities, recommendations, login schedule.

## [0.6.0] - 2026-10-09

- Standalone Layout Planner for the farm: named blocks, isometric SVG grid, fixed and rotatable items, support relations.
- Farm map editor and measured farm map with plots and zones; Storage block; animal feeding recipes.

## [0.5.0] - 2026-10-05

- Data foundation: footprints, production and growth times, level limits, data overrides, player profile schema, game knowledge docs.

## [0.4.0] - 2026-10-05

- Player config with level and mastery system, no hard-coded level, scraper `meta.json`, data for level 56.

## [0.3.0] - 2026-08-05

- Weighted graph, production-block detection, centrality and path analysis, JSON / CSV / GraphML export, wiki scraper.
