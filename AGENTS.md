# AGENTS.md

Instructions for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Project

The project analyses Hay Day production chains. It turns locations, resources and recipes into a weighted directed graph (NetworkX). From that graph it detects production blocks for farm-layout planning. The full concept and roadmap are in `README.md`.

- Milestone done: **v0.3** (Layout Planner: proximity graph, Louvain blocks, centrality, exporters, wiki scraper).
- Next milestone: **v0.5** (Production Planner foundation: timing and capacity data, `level_limits.json`, `src/planner/`).

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m pytest                          # all tests must pass
python -m src.main --max-level 52         # build graph + analysis into output/
python -m src.scraper --max-level 52      # refresh data/*.json from the Fandom wiki
```

## Layout

- `src/models/` - pydantic models (`Location`, `Resource`, `Recipe`)
- `src/loaders/json_loader.py` - loads and validates `data/*.json` into a `DataSet`, with optional level filter
- `src/graph/` - graph builder, edge types (`relationship.py`), weights (`weighting.py`), analysis (`analysis.py`)
- `src/exporters/` - JSON / CSV / GraphML export
- `src/scraper/` - wiki client, parsers, normalizer, writer
- `src/main.py` - CLI entry point
- `src/planner/` - planned for v0.5, does not exist yet
- `tests/` - pytest suite, one file per module area

## Conventions

- Write code, identifiers, comments and commit messages in English.
- Entity ids are lower-case snake_case English, and validators enforce this.
- Models use `extra="forbid"`. Every new data field needs a model change in the same commit.
- Keep the data model close to 3NF so it can later move to PostgreSQL. Per-level limits go in a separate `level_limits.json`, and player progress goes in a separate player-config file.
- Durations are stored in seconds (`*_time_seconds`).
- External or premium recipe inputs (vouchers, diamonds) may appear in recipes but never become graph nodes.
- `data/*.json` is scraper output. Fix data problems in the scraper or normalizer, not by hand-editing the JSON.
- `output/` is generated and git-ignored. Do not commit it.
- Every new module gets tests in `tests/`.
- When a roadmap item is finished, tick it in `README.md` and update the "Current status" line.
