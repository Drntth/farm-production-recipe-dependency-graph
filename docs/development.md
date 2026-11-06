# Development

Setup, checks, CI and releases. Code conventions and the code map: [AGENTS.md](../AGENTS.md); module entry points: [modules.md](modules.md); architecture: [architecture.md](architecture.md).

## Setup

Python 3.14 or newer (`requires-python` in `pyproject.toml`; the code uses 3.14-only syntax). Node.js 22 or newer is needed for the map editor tests and the web site (`web/`, see [Web site](#web-site)).

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt     # runtime (requirements.txt) + pytest, ruff
```

The project is not an installable package: `pyproject.toml` holds only metadata and tool settings, the dependencies are pinned in `requirements*.txt`.

## Checks

A change is done when all three pass:

```bash
python -m pytest                        # every test, no network
ruff check src tests                    # lint
ruff format --check src tests           # formatting (ruff format src tests fixes it)
```

## Tests

| Kind               | Where / how                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Unit tests         | `tests/test_<area>.py`, one file per module area                                                                                 |
| Scraper            | trimmed wiki HTML and wikitext in `tests/fixtures/wiki/`; the wiki client is injectable, tests never call the network            |
| Real data          | tests marked with `HAS_REAL_DATA` run only when `data/locations.json` exists                                                     |
| Map editor JS core | `tests/test_farm_map_editor.py` runs the functions between `CORE-START` / `CORE-END` of the editor in node; skipped without node |
| Architecture       | `tests/test_architecture.py` compares the package diagram in `architecture.md` with the real imports                             |
| Generated examples | `tests/test_examples.py` fails when `config/examples/` is stale: regenerate with `python -m src examples`                        |

Rules:

- New behavior gets a test; a bug fix starts with a failing regression test.
- Tests never depend on a specific player level or on the local `config/*.json` files.
- New scraper parsing gets a fixture-based test in `tests/test_scraper.py`.

## CI

`.github/workflows/ci.yml` runs on every push and pull request: Python 3.14 and Node 24, `pip install -r requirements-dev.txt`, then the three checks above. Its `web` job builds the site on levels 1, 20 and 40 and runs the web checks below.

## Web site

The static site in `web/` (Astro, TypeScript, Svelte; [tools/recommend.md](tools/recommend.md)) is built from the level recommendations. Quick local look, the same files GitHub Pages gets:

```bash
./serve-web.sh                             # reuse output/recommendations/ (else levels 1-100), build, serve, open the browser; Ctrl+C stops
./serve-web.sh 1,20,40                     # recompute these levels first
./serve-web.sh stop                        # stop a server left running
```

The steps one by one are below. The npm versions are exact and at least two weeks old when added; `package-lock.json` is committed.

```bash
python -m src recommend --levels 1,20,40   # or every level: python -m src recommend (about 3 minutes)
cd web
npm ci
npm run check                              # astro check: TypeScript and Svelte
npm run build                              # dist/; RECOMMENDATIONS_DIR overrides ../output/recommendations
npx playwright install chromium            # once
npm run test:e2e                           # Playwright on the built site, mobile + desktop
npm run dev                                # local server with reload
```

Deploy: `.github/workflows/pages.yml` runs after a green CI run of a push to `main`. It computes levels 1-100, builds `web/dist` and deploys it to GitHub Pages. One-time setting in the repository: Settings → Pages → Source "GitHub Actions". The generated recommendations are not committed.

## Common changes

| Change                    | Also update                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| New tool setting          | model field in `src/settings.py`, value in the example config, a row in [settings.md](settings.md), a test   |
| New node attribute        | the CSV column list and the GraphML key list in `src/exporters/`                                             |
| New data field            | the pydantic model in `src/models/` (models forbid extra keys), [data-model.md](data-model.md)               |
| Input file format change  | bump `CURRENT` in `src/schema.py`, one migration in `MIGRATIONS` and a test in `tests/test_schema.py`        |
| New configurable location | `config/player.example.json` (`tests/test_config.py` checks it against the data)                             |
| New CLI tool              | a `COMMANDS` entry in `src/cli.py`, [cli.md](cli.md), the diagrams in [architecture.md](architecture.md)     |
| Recommendation format     | bump `recommendation` / `recommendation_index` in `src/schema.py` and the version check in `web/src/data.ts` |
| New tool output or input  | the Core API in `src/api/core.py` (returns every file); the tool's `cli.py` only reads and writes            |
| How a tool works          | its page in [tools/](tools/) in the same commit                                                              |
| Game update               | follow [game-updates.md](game-updates.md): re-scrape, run the tests, record the version and new wiki gaps    |

## Releases

1. Finish the milestone: tick it in [roadmap.md](roadmap.md) and update the status line of the README.
2. Bump `version` in `pyproject.toml` (SemVer; the version lives only there).
3. Move the `CHANGELOG.md` Unreleased lines into `## [x.y.z] - YYYY-MM-DD`.
4. Commit, then tag the commit: `git tag -a vX.Y.Z -m "..."`.
