# Changelog

One entry per version. The version is kept in `pyproject.toml`; the details of each milestone are in the README roadmap. Versions before 1.0.0 have no git tag.

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
