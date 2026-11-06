# Level recommendations and the static site

The plan and layout for every level with level defaults (`src/recommend/`, `python -m src recommend`), and the static site in `web/` that shows them.

## Level recommendations

`python -m src recommend [--levels 1-100] [--output-dir output/recommendations]` runs the combined plan once per level, without a player profile or a farm map of the player:

1. **Profile**: the level-default profile of `python -m src examples` (`example_profile`).
2. **Map**: the base map (`data/base_map.json`) with an empty profile map. No plot is unlocked, so the layout uses only section `base`.
3. **Settings**: the built-in defaults of `config/design*.json` and `config/planner*.json`, with `block_images` off; no design template.
4. **Plan**: `combined_plan` of the Core API; the files of one level are its `combined.json` payload and `combined.svg`.

Blocks that do not fit on section `base` stay unplaced (from about level 36 on, game version 1.73); `blocks_not_placed` lists them and the site shows a warning. A plot recommendation that unlocks the plots they need is planned for v2.5.

`--levels` takes ranges and lists (`1-100`, `1,20,40`, `1-10,40`). A level above the data is an error. The run takes about three minutes for 1-100; the logs of the planners are muted, the command logs the levels with unplaced blocks.

Outputs in `output/recommendations/`:

| File           | Content                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `level_N.json` | `schema_version`, `level`, `game_version` (from `data/meta.json`), `core_version` (`pyproject.toml`), `blocks_not_placed`, `combined` |
| `level_N.svg`  | the combined layout (`combined.svg`)                                                                                                  |
| `index.json`   | `schema_version`, `levels`: one row per level with `level`, `blocks`, `blocks_not_placed` (count), `login_interval_hours`             |

The output is deterministic: the same data and code give the same files.

## Static site (`web/`)

Astro with TypeScript and one Svelte island (the level picker). Every page is static HTML built from `output/recommendations/` (or `RECOMMENDATIONS_DIR`); no Python and no Pyodide run in the browser.

| Page             | Content                                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `/`              | level picker, table of every level (login interval, blocks, unplaced blocks), game and planner version                      |
| `/levels/N/`     | plan figures, trees and bushes to plant, external goods, the steps at each login, layout image and blocks, upcoming unlocks |
| `/layouts/N.svg` | the layout image of level N                                                                                                 |

Every page has the footer: the Supercell Fan Content Policy notice, the Hay Day Wiki data attribution (CC BY-SA 3.0) and the MIT licence of the code.

The site is served under `/farm-production-recipe-dependency-graph/` on GitHub Pages. `web/tests/site.spec.ts` (Playwright, Desktop Chrome and Pixel 7) checks that the pages load, use no request to another origin and no Pyodide, show the footer and the layout image, and have no horizontal scroll. Local look: `./serve-web.sh` (Ctrl+C stops). Build and deploy: [development.md](../development.md#web-site).
