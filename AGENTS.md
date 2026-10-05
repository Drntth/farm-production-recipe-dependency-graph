# AGENTS.md

Instructions for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

## Project

The project analyses Hay Day production chains. It turns locations, resources and recipes into a weighted directed graph (NetworkX). From that graph it detects production blocks for layout planning. The full concept, architecture and roadmap are in `README.md`.

- Milestone done: **v0.4** (re-foundation: player config, `--level`, `meta.json`, separated architecture, game update checklist).
- Next milestone: **v0.5** (Data foundation: footprints, `area`, timing fields, `level_limits.json`, `data/overrides/`).

## Architecture rules

- A shared core (`src/config.py`, `src/models`, `src/loaders`, `src/graph`) feeds three tools.
- The **Layout Planner** (planned `src/layout/`) and the **Production Planner** (planned `src/planner/`) are independent. Neither may import the other. Layout must work without production data.
- The **Combiner** (planned) is the only place that joins the two.
- Layout areas: `farm` (graph-driven), plus `town` and `fishing_lake`. Town and fishing lake have no quantity calculations.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m pytest                          # all tests must pass
python -m src.main                        # graph + analysis into output/, level from player config
python -m src.main --level 30             # override the player level
python -m src.scraper --game-version 1.72 # refresh data/*.json + data/meta.json from the Fandom wiki
```

## Layout

- `config/player.example.json` - committed example player config. `config/player.json` is local, git-ignored and takes precedence.
- `src/config.py` - `PlayerConfig` (`level`, `mastery_system`) and `load_player_config()`
- `src/models/` - pydantic models (`Location`, `Resource`, `Recipe`)
- `src/loaders/json_loader.py` - loads and validates `data/*.json` into a `DataSet`, with an optional level filter
- `src/graph/` - graph builder, edge types (`relationship.py`), weights (`weighting.py`), analysis (`analysis.py`)
- `src/exporters/` - JSON / CSV / GraphML export
- `src/scraper/` - wiki client, parsers, normalizer, writer (`meta.json`)
- `src/main.py` - CLI entry point
- `tests/` - pytest suite, one file per module area

## Conventions

- Write code, identifiers, comments and commit messages in English.
- Never hard-code a player level. Take it from `PlayerConfig` or from a `--level` argument. Tests must not depend on a specific level snapshot.
- Entity ids are lower-case snake_case English, and validators enforce this.
- Models use `extra="forbid"`. Every new data field needs a model change in the same commit.
- Keep the data model close to 3NF so it can later move to PostgreSQL. Per-level limits go in a separate `level_limits.json`. Player progress goes in the player config.
- Durations are stored in seconds (`*_time_seconds`).
- Production-time modifiers (mastery) depend on `mastery_system`: `stars` is the default, `workbench` must stay pluggable.
- External or premium recipe inputs (vouchers, diamonds) may appear in recipes but never become graph nodes.
- `data/*.json` is scraper output. Fix data problems in the scraper or normalizer, not by hand-editing the JSON. Content missing from the wiki goes in `data/overrides/` (v0.5+).
- `output/` is generated and git-ignored. Do not commit it.
- Every new module gets tests in `tests/`.
- When a roadmap item is finished, tick it in `README.md` and update the "Current status" line.

## Game update check

When the user mentions a new game update, or `data/meta.json` looks outdated:

1. Check the [Fandom Update page](https://hayday.fandom.com/wiki/Update) and official patch notes for changed mechanics.
2. Map each change with the "Game update checklist" table in `README.md` (e.g. a mastery rework → planner mastery modifier + `mastery_system`; new machine → scraper / overrides).
3. Re-scrape with `--game-version`, run the tests, and update the "Known state" list in `README.md`.
