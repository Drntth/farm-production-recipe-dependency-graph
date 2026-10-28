# User guide

How to get a production plan and a farm layout for your own Hay Day farm. Everything runs locally from the command line; nothing is uploaded. The [README](../README.md) explains how the tools work inside; this guide is about using them.

## 1. Install

Needs Python 3.14 or newer.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src            # lists the commands
```

## 2. Describe your farm: the player profile

The tools read your profile from `config/player.json` (git-ignored). Pick one way to make it:

| Way                                                   | Effort    | Result                                                                                   |
| ----------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------- |
| `python -m src wizard`                                | 5 minutes | asks what is unlocked at your level; Enter keeps a default, `slots=5 stars=3` changes it |
| copy `config/examples/player_level_<N>.json` and edit | low       | a player who bought nothing beyond the level (levels 10-50)                              |
| write it by hand                                      | high      | see [player-profile.md](player-profile.md) for every field                               |

Only the level is required. Every missing value gets its level default: all unlocked copies, base slots, no mastery, full shelters. Two values have no default and are worth adding: `barn_capacity` and `silo_capacity` (without them the plan ignores storage limits and says so). Leave fields, trees and bushes empty if you do not want to count them: the planner recommends a number.

## 3. Measure your map (optional, for a real layout)

Without a map the layout is drawn on an unbounded grid: useful to see the blocks, not to rebuild the farm. For a layout on your own land, measure `config/farm_map.json` with `tools/farm_map_editor.html` (open it in a browser). The steps are in the README section "Measuring with the map editor": stitch a screenshot, calibrate it with two rows of fields, mark the fixed buildings, the unlocked plots and the zones:

- `blocked` (red): water, roads, paved strips; nothing is built there.
- `design` (violet): decorations you want to keep; no block goes there, paths may cross.

## 4. Choose how it should look: settings

Settings are files, not command-line options. Copy the examples and edit them; the tools tell you in their log which file they used, and every output records the settings it was made with.

- `config/design.json`: layout and design. Most useful keys: `design_layer` (paths and a decoration band), `path_style` (`straight` for fewer corners), `item_gap` (room between the buildings of a block), `reserve` (free area per block for later unlocks), `block_images`.
- `config/planner.json`: `production.login_interval` (fix how often you log in; empty = suggested), `production.storage_share`, `combiner.lookahead` (levels ahead whose unlocks get space now).

Every key with its default is in the README section "Settings". Placing every block always comes first: if the blocks do not fit, the tools lower `item_gap` first and then the reserve, and the report says so.

## 5. Run

```bash
python -m src all                        # graph, farm layout, production plan, combined plan
python -m src combine                    # only the combined plan (layout sized by production)
python -m src plan --level 30            # try another level for one run
```

Every command takes the files it uses (`--player-config`, `--map`, `--design-config`, `--planner-config`, `--output-dir`) to use other files than the defaults; `python -m src <command> -h` lists them.

## 6. Read the results (`output/`)

| File                                     | Look at it for                                                                               |
| ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| `combined.md`                            | the whole plan: blocks upstream → downstream, goods flows between them, expansion, schedule  |
| `combined.svg`, `combined_blocks/*.svg`  | the farm with every block; one image per block to rebuild it in the game, plus `collage.svg` |
| `schedule.md`                            | how often to log in and what to do at every login, recommended fields, trees and bushes      |
| `layout.md`, `layout.svg`, `blocks/`     | the layout without production sizing (graph and profile only)                                |

The SVG files open in any browser. To see the layout on your own screenshot, load `layout.json` or `combined.json` in the map editor (step 7, Layout overlay). Coordinates are tiles from the top corner of the map: x along the ↘ edge, y along the ↙ edge. The game's Layout Edit Mode shows no grid, so count tiles from a fixed building.

## 7. Typical situations

- **You reached a new level:** change `level` in `config/player.json` (or run the wizard again) and run `python -m src all`. Copies unlocked within the lookahead already have space in their blocks.
- **A block "does not fit":** unlock or mark more land, lower `reserve` or `item_gap`, or try `strategy: size` in the farm section of `design.json`.
- **"barn_capacity is not set":** add your barn and silo capacity to the profile.
- **A building "not reachable by a path":** check that the zones around it are right; a building behind a paved strip gets a path to the edge of the buildable land.
- **After a game update:** follow [game-updates.md](game-updates.md). `python -m src check-facts` compares the game fact tables with the wiki and lists the rows to look at (`output/fact_check.md`):
  - `changed`: the wiki page was edited after the row was checked; read the page and update the row (and its `Checked` date);
  - `page error`: the page could not be fetched (renamed, deleted, offline); fix the source or try again;
  - `value not found`: a number of the row is not on the page; only a hint, because the page may write it in words or the value may be derived, so check it by hand.

  `--fail-on-findings` makes the command exit with code 3 when a row is `changed` or has a `page error` (for a scheduled check).

## Limits

- The data covers levels up to the scraped level (see `data/meta.json`); unlocks above it are not known.
- Some values the wiki lacks are estimates (tree and bush yield, honeycomb rate); see [wiki-gaps.md](wiki-gaps.md). They change the numbers, not the method.
- Live orders (truck, boat, town visitors, events) are not planned: the plan is a steady state for your farm's capacity.
