# Level recommendations and the static site

The plan and layout for every level with level defaults (`src/recommend/`, `python -m src recommend`), and the static site in `web/` that shows them.

## Level recommendations

`python -m src recommend [--levels 1-100] [--output-dir output/recommendations]` runs the combined plan once per level, without a player profile or a farm map of the player:

1. **Profile**: the level-default profile of `python -m src examples` (`example_profile`).
2. **Map**: the base map (`data/base_map.json`) with an empty profile map. No plot is unlocked, so the layout uses only section `base`.
3. **Settings**: the built-in defaults of `config/design*.json` and `config/planner*.json`, with `block_images` off; no design template.
4. **Plan**: `combined_plan` of the Core API; the files of one level are its `combined.json` payload and `combined.svg`.

Blocks that do not fit on section `base` stay unplaced (from about level 36 on, game version 1.73); `blocks_not_placed` lists them and the site shows a warning. A plot recommendation that unlocks the plots they need is planned for v2.7.

`--levels` takes ranges and lists (`1-100`, `1,20,40`, `1-10,40`). A level above the data is an error. The run takes about three minutes for 1-100; the logs of the planners are muted, the command logs the levels with unplaced blocks.

Outputs in `output/recommendations/`:

| File           | Content                                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `level_N.json` | `schema_version`, `level`, `game_version` (from `data/meta.json`), `core_version` (`pyproject.toml`), `blocks_not_placed`, `combined`                              |
| `level_N.svg`  | the combined layout (`combined.svg`)                                                                                                                               |
| `index.json`   | `schema_version`, `levels`: one row per level with `level`, `blocks`, `blocks_not_placed` (count), `logins_per_day`                                                |
| `map.json`     | `schema_version`, the base map for the farm view: `width`, `height`, `usable` and `usable_bounds` (`[x, y, w, h]` rects), `farm_outline` (segments), `fixed` items |

The output is deterministic: the same data and code give the same files.

## Static site (`web/`)

Astro with TypeScript and two Svelte islands (the level picker and the farm view). Every page is static HTML built from `output/recommendations/` (or `RECOMMENDATIONS_DIR`); no Python and no Pyodide run in the browser.

| Page              | Content                                                                                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/`               | intro, level picker, a card of every level (blocks, logins per day, new buildings, unplaced blocks)                                                                                              |
| `/levels/N/`      | key figures, level switch, tabs, farm view with the block cards and the SVG download, plan summary (logins per day, fields used, production hours) with a link to the plan, upcoming, next level |
| `/levels/N/plan/` | key figures, level switch (stays on this tab), tabs, plan summary (figures, login times, last login, trees, bought goods), login actions per building (collapsed), next level                    |
| `/how-it-works/`  | the four steps: graph → blocks → layout → plan                                                                                                                                                   |
| `/usage/`         | running the tools for an own farm: install, wizard, map editor, `python -m src all`, links to the docs                                                                                           |
| `/layouts/N.svg`  | the layout image of level N                                                                                                                                                                      |
| `/hu/…`           | the same pages in Hungarian                                                                                                                                                                      |

The design follows the portfolio site drntth.github.io ([v2-design.md](../v2-design.md#architecture)): Tailwind CSS v4 tokens and shared classes in `web/src/styles/global.css`, a sticky header with the barn logo, the menu (Levels, How it works, Usage; a hamburger with a card grid below 1024 px), a language switch and a dark mode toggle (stored in `localStorage`, else the system setting). The "summer farm" palette: leaf green as the main colour, barn red as the second, a leaf green → gold gradient, on a sky blue → grass green background; light and dark have their own values. The barn logo is `components/BarnLogo.astro` (theme colours) and `public/favicon.svg` with PNG icons made from it. Fredoka sets the headings, Nunito the text; Hungarian pages set headings in Nunito too, because Fredoka has no ő / ű. Wide screens use the width as the portfolio does: a page container up to 90rem, justified and hyphenated paragraphs (narrow cards stay left-aligned), card grids with more columns on wider screens. The plan page puts the summary first; the login actions follow as one collapsed `<details>` group per building in the planner's order (collect, plant and sell have no building and are a group each), with the kind of action, the slots and the number of items in the closed header. Sections below the fold fade in once when scrolled into view (`.reveal` in the views, an IntersectionObserver in `layouts/Base.astro`); the CSS hides them only when the `html.js` class is set by the head script and the player allows motion, so without JavaScript, under `prefers-reduced-motion` and in print everything is shown at once.

### Farm view

`components/FarmView.svelte` draws the level's layout as an isometric SVG from `map.json` and the combined plan (`layout.blocks`, `blocks`, `flow_links`); a tile is 2 × 1 units (point (x, y) → (x − y, (x + y) / 2)), the block colours follow the order of `layout.blocks`. The area outside the buildable zones is faint, and the first view frames `usable_bounds`. Its own pan and zoom (no library): wheel or pinch to zoom, drag to move, the + / − / ⌂ buttons, and on the focused map the arrow keys, + / − and 0; labels keep about 12 px at every zoom. Blocks and their cards highlight each other on hover and focus (the others dim); a click on a block or its card button selects it, zooms to it and opens the detail panel below the map (buildings × copies, reserved copies, busy share, goods per hour, fields and crops, goods flows in and out, unplaced note), closed by × or Esc, which returns the focus to the card. A drag never selects. The page renders the same SVG on the server, so without JavaScript it is a still map with the cards; the SVG file stays as a download. Every class in the SVG has the `fv-` prefix, because Tailwind utilities (`outline`, `fixed`, `block`) would style SVG elements of the same name. The new buildings on a home card come from the previous listed level's look-ahead (`expansion.upcoming`, kind `new`, unlocked after it up to this level); a lookahead shorter than a gap between listed levels misses some.

Languages: English at the root, Hungarian under `/hu/`. Every UI string sits in `web/content/en.json` and `hu.json` with the same keys and placeholders (`tests/test_web_content.py`); the views in `web/src/views/` take `lang`, and `pages/` and `pages/hu/` only pass it. Game item names come from the data and stay English; the login step texts of the schedule are translated by their English text (`whats`), with the English text as the fallback.

Every page has the footer: the Supercell Fan Content Policy notice (in English in both languages, its required wording), the Hay Day Wiki data attribution (CC BY-SA 3.0), the MIT licence of the code, links to the pages, the source and the portfolio site, and the game and planner version as badges.

The site is served under `/farm-production-recipe-dependency-graph/` on GitHub Pages. `web/tests/site.spec.ts` (Playwright, Desktop Chrome and Pixel 7) checks that the pages load, use no request to another origin and no Pyodide, show the footer with the versions and the layout image, reach every page from the menu (hamburger on the phone), open levels from the picker and the level switch, switch language and theme, and have no horizontal scroll, in both languages; the farm view zooms and moves by mouse, touch, buttons and keys, blocks and cards highlight each other and open the detail panel, the plan groups start collapsed, sections fade in on scroll (at once under reduced motion), and without JavaScript the map, the cards and the download stay. Local look: `./serve-web.sh` (Ctrl+C stops; `--host`: from a phone on the same Wi-Fi too). Build and deploy: [development.md](../development.md#web-site).
