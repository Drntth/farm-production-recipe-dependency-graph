# AGENTS.md

Instructions for coding agents working in this repository. `CLAUDE.md` is a symlink to this file.

Commit prefix: [HAYDAY-PROJECT]

The project analyses Hay Day production chains. It turns locations, resources and recipes into a weighted directed graph (NetworkX). From that graph it forms named production blocks for the farm layout and plans production quantities. Overview: `README.md`; how each tool works: `docs/tools/`.

- Milestones v0.3-v2.4 are done (v2.4 released as v2.4.0); what each brought is in `docs/roadmap.md`. Next: **v2.5** (UI/UX design: `docs/ui-design.md`, validated inputs, icons, own drawings); the v2+ sub-versions are in `docs/roadmap.md`, the web app design and its decisions in `docs/v2-design.md`.
- The values the wiki lacks are measured or accepted estimates in `docs/wiki-gaps.md`.

## Read first

1. Domain terms (block, anchor, goods flow, connection point, sizing, …) are defined in [CONTEXT.md](CONTEXT.md). Use them consistently in code, docs and replies; add a term there when a new one appears.
2. Game knowledge is already collected. **Before researching the game or the wiki, read [docs/README.md](docs/README.md)** and the file for the question:

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
| code map: which file holds what                    | `docs/code-map.md`                        |
| conventions (code, data, where data goes)          | `docs/conventions.md`                     |
| setup, tests, CI, release steps                    | `docs/development.md`                     |
| milestones, v2+ sub-versions                       | `docs/roadmap.md`                         |
| web app architecture, v2 decisions                 | `docs/v2-design.md`                       |
| input types, icons, drawings, accessibility rules  | `docs/ui-design.md`                       |

When you learn a new game fact (from the wiki, the web or the user), add a row to the matching `docs/game-facts/*.md` table in the documented format: `| Fact | Value | Source | Checked |`.

## Architecture rules

- A shared core (`src/config.py`, `src/settings.py`, `src/models`, `src/loaders`, `src/graph`) feeds three tools.
- The **Layout Planner** (`src/layout/`) and the **Production Planner** (`src/planner/`) are independent. Neither may import the other. Layout must work without production data.
- The **Combiner** (`src/combiner/`) is the only place that joins the two. It passes production quantities to the layout as a plain `Sizing` (`src/layout/sizing.py`); `tests/test_combiner.py` checks that layout and planner never import each other.
- Only the farm is laid out. Town and fishing lake get no layout; lake locations stay in the data for the Production Planner.
- `docs/architecture.md` holds the package diagram (Mermaid). A new import between top-level `src/` packages needs a new arrow there; `tests/test_architecture.py` fails until the diagram matches.

## Commands

```bash
python -m pytest                          # all tests must pass (no network needed)
ruff check src tests && ruff format --check src tests
python -m src all                         # graph, layout, plan, combined plan in one run
```

Web interface changes are checked by tests, not by hand: `cd web && npm run test:e2e` locally, `npm run test:live` against GitHub Pages after the deploy (the Pages `live-check` job runs it too). Details: [docs/development.md](docs/development.md#automated-checks-instead-of-manual-ones).

Every other command (single tools, scraper, web, map editor): [docs/cli.md](docs/cli.md#quick-list) and [docs/development.md](docs/development.md).

## Conventions (short)

- Code, identifiers, comments, docs and commit messages in English.
- Never hard-code a player level; never present a guess as a fact (use an estimate, record it in `docs/wiki-gaps.md`).
- Every new module gets tests in `tests/`; tests run without network.
- `output/` is generated and git-ignored; never commit it.
- Tool settings go into `config/design*.json` / `config/planner*.json`, never into CLI options.
- Releases: version only in `pyproject.toml`; a finished milestone gets a `CHANGELOG.md` entry and a `vX.Y.Z` tag.

Full rules: [docs/conventions.md](docs/conventions.md).

## Game update check

When the user mentions a new game update, or `data/meta.json` looks outdated, follow [docs/game-updates.md](docs/game-updates.md).
