# Conventions

Rules for code, data and docs. The short list for coding agents is in `AGENTS.md`.

## General

- Write code, identifiers, comments, docs and commit messages in English.
- Never hard-code a player level. Take it from `PlayerConfig` or from a `--level` argument. Tests must not depend on a specific level snapshot.
- Never present a guess as a fact. If the wiki lacks a value the code needs, use an estimate derived from existing data (or the user's game experience), put it where the code reads it, and add a row to `docs/wiki-gaps.md` with its basis and status. Gaps never block a milestone.
- Every new module gets tests in `tests/`. New scraper parsing needs a fixture-based test in `tests/test_scraper.py` (no network in tests).
- `output/` is generated and git-ignored. Do not commit it.
- Tool settings (how a tool works) go into `config/design*.json` or `config/planner*.json` via `src/settings.py`, never into new CLI options. The CLI only says what to run (level, file paths). The one kind of exception: flags that change only the exit code of a check, not its result (`check-facts --fail-on-findings`). A new setting needs a model field, a value in the example file, a `docs/settings.md` table row and a test.
- When a roadmap item is finished, tick it in `docs/roadmap.md`, update its "Current status" line and the status line of `README.md`. A change to how a tool works goes into its `docs/tools/*.md` page in the same commit.
- Python 3.14+ (`requires-python` in `pyproject.toml`); ruff targets it, so 3.14-only syntax is fine. CI (`.github/workflows/ci.yml`) runs pytest, `ruff check` and `ruff format --check` on every push.
- Releases: the version lives only in `pyproject.toml`. A finished milestone bumps it, adds a `CHANGELOG.md` entry (`## [x.y.z] - date`, a few lines) and gets a `vX.Y.Z` git tag on its commit.

## Data model

- Entity ids are lower-case snake_case English, and validators enforce this.
- Models use `extra="forbid"`. Every new data field needs a model change in the same commit.
- Keep the data model close to 3NF so it can later move to PostgreSQL. Level-gated limits go in `level_limits.json`.
- Durations are stored in seconds (`*_time_seconds`).
- Footprints are two atomic ints (`footprint_width`, `footprint_height`), both or neither. Width is the ↘ edge and height the ↙ edge, seen from the top corner.
- Fixed buildings have `movable: false`. The layout planner never moves them.
- `rotatable: true` allows swapping width and height. Without it, non-square items are placed only as stored.
- Every fruit tree and bush kind is its own location (`apple_tree`, `raspberry_bush`, `nectar_bush`), never a generic `tree` / `bush`.
- External or premium recipe inputs (vouchers, diamonds) may appear in recipes but never become graph nodes.

## Where data goes

| Kind                                                                  | Place                                                                                           |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Per-entity data from wiki tables                                      | `data/*.json` via the scraper; fix problems in the scraper or normalizer, never by hand-editing |
| Per-entity data the wiki lacks                                        | `data/overrides/*.json` (existing ids patched field by field, new ids added)                    |
| Game rules (min / max, costs, mechanics)                              | `docs/game-facts/*.md`; move into data or code only when code needs them                        |
| Anything a player buys, upgrades or earns                             | the player profile (`config/player*.json`)                                                      |
| The player's farm map and building positions                          | `data/base_map.json` (shared geometry), `config/profile_map*.json`, `config/farm_map*.json`     |
| Tool settings: layout / design taste, planner and Combiner parameters | `config/design*.json`, `config/planner*.json`                                                   |

## Player profile

- Counts are totals over all copies (`slots`, `animals`). Mastery (`mastery_stars`, `workbench_level`) is per building type, because copies share production hours.
- `null` means "use the level default / let the planner recommend". Fields, trees and bushes are optional on purpose.
- `mastery_system` selects the production-time modifier: `stars` is the default, `workbench` must stay pluggable.
- When a new configurable location appears in the data, add it to `config/player.example.json`; `tests/test_config.py` checks the example against the data.
