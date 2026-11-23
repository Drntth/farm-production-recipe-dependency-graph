# Farm profiles and the browser planner

The "My farms" page of the site (`/profiles/`, `/hu/profiles/`) keeps farm profiles in the browser and plans them with the unchanged Python core in Pyodide (v2.4). Design and decisions: [v2-design.md](../v2-design.md).

## Build-time files

`python -m src web-files [--data-dir data] [--output-dir web/public/py]` (`src/recommend/web_files.py`, about a second) writes the git-ignored files the page loads:

| File               | Content                                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `core.zip`         | the `src` modules `src.api.browser` imports (found by following the imports; no scraper, recommend or tests), fixed timestamps |
| `data_bundle.json` | the data bundle (`python -m src bundle`)                                                                                       |
| `defaults.json`    | `{"schema_version": 1, "locations": {id: {name, type}}, "levels": {"<N>": <level-default player profile>}}`, levels 1 to max   |

The level-default profile is the one of `python -m src examples` (`example_profile`): every unlocked copy, base slots, no mastery, full shelters; trees and bushes `owned: null` (recommended).

## Page

`web/src/components/FarmProfiles.svelte` (a `client:only` island):

1. **Farm profiles**: a list with one tab per profile, a "new profile" form (name, level) and JSON import. Every change is written to IndexedDB at once; the first write asks for `navigator.storage.persist()` and the page says whether the browser keeps the data.
2. **Form**: name, level, barn / silo capacity, fields, fishing spots, the daily login window (first and last login, logins per day) and one table per location type (production, animals, trees, bushes, other) with the fields that apply. An empty field means the level default, shown as the placeholder; a level change drops the overrides of locations not unlocked at the new level.
3. **Plan**: "Calculate the plan" sends the profile to the worker and shows the plan like the level plan page (`PlanView.svelte`): key figures, login times, the last login, trees and bushes, outside goods, the login actions per building (collapsed), the planner's notes, and the time it took. A plan made before the profile changed is marked as out of date.

The exported file is the farm profile JSON of `python -m src farm-profile` ([cli.md](../cli.md)), so `python -m src plan --farm-profile <file>` reads it too, and an import of an export is unchanged.

## Code

| Part                          | Role                                                                                                                                                                                                       |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `web/src/profiles/types.ts`   | farm profile JSON types, `SCHEMA_VERSIONS` (from `src/schema.py`)                                                                                                                                          |
| `web/src/profiles/profile.ts` | pure functions: `newFarmProfile`, `setLevel`, `setLocationValue`, `setPlayerValue`, `setLoginWindow`, `setName`, `migrate`, `exportJson`, `importJson`                                                     |
| `web/src/profiles/store.ts`   | `createProfileStore(backend)`: IndexedDB through idb-keyval (`farm-production` / `profiles`), a Map backend for tests; `requestPersist`                                                                    |
| `web/src/worker/`             | `planner.worker.ts` (module worker: Pyodide from jsDelivr, numpy, scipy, pydantic, networkx by wheel URL, `core.zip`), `client.ts` (lazy worker, `planFarmProfile`, `warmUp`, `onProgress`), `messages.ts` |
| `src/api/browser.py`          | `plan_farm_profile(bundle, profile)`: validates the farm profile, calls `production_plan`, returns `result`, `files` and the logged warnings; `level_defaults`                                             |

Pyodide loads only on the first calculation; the level pages never load it (`tests/site.spec.ts`). The worker reaches the core only through `src.api.browser` (`tests/test_browser.py`). On a Pyodide update change `PYODIDE_VERSION` and the networkx wheel in both `planner.worker.ts` and `web/scripts/pyodide-smoke.mjs`. Only a failed start reloads Pyodide; a planner error keeps it loaded. An import whose level is not in `defaults.json` is refused; stored profiles are migrated to the current schema version when read.

## Checks

- `npm test` (Vitest): profile functions, migration, export → import, the store with a Map backend.
- `tests/profiles.spec.ts` (Playwright): two profiles kept over a reload, the form follows the level, export → import unchanged, a bad file; on desktop two profiles planned in Pyodide (needs the network).
- `node web/scripts/pyodide-smoke.mjs` (after `python -m src web-files`; network): plans a fixed farm profile in Pyodide under Node and compares the JSON with native CPython character by character; the `pyodide-smoke` CI job runs it with `continue-on-error` (it needs the CDN), so check its result by hand. `tests/test_browser.py` checks that the worker, the smoke test, `package.json` and `requirements.txt` pin the same Pyodide and networkx versions.
