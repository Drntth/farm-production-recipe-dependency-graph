# Farm Production Graph

Hay Day production chains as a graph: which buildings make which goods, how to group them into blocks on the farm, how much to produce and when to log in.

## Game data

**`Location`**: anything that takes space or produces: production building, animal shelter, field, tree, bush, storage, fixed building.
_Not to be confused with_: `FixedItem` (a measured position on the farm map, not a data entity)

**`Resource`**: a good: crop, animal product, processed good, ore. Called "good" in prose.
_Not to be confused with_: external input (voucher, diamond, lure, fishing spot), which is no good and never a graph node

**`Recipe`**: one transformation at a location: inputs → one output, with a production time.
_Related_: feeding recipe

**Feeding recipe**: a recipe at an animal shelter (chicken feed → egg); the animal time is its production time.

**`Area`**: the game area a location belongs to: `farm`, `town`, `fishing_lake`. Only `farm` locations are laid out.

**Footprint**: size of a location in tiles, `width` along the ↘ edge and `height` along the ↙ edge, seen from the top corner.

**Fixed building**: a location or map item the player cannot move (`movable: false` in the data), e.g. the mine, the farmhouse; the only kind of item in the farm map's `fixed` list.
_Not to be confused with_: current item (a movable item where it stands now)

**Rotatable**: a non-square footprint may be turned (width and height swapped).

**Copy**: one placed instance of a building or shelter; the level limits how many copies are unlocked.

**Mastery**: per building type production speed-up; `stars` (3-star mastery) or `workbench` (Building Mastery).

**Wiki gap**: a value the project needs that the wiki does not give; an estimate is used until it is measured in the game.

**Game fact**: a game rule with value, source and check date, kept in the game fact tables.

**Override**: a hand-maintained shared value in `data/overrides/` that the loader merges over the scraped data at every load; a known `id` patches only the listed fields, a new `id` adds a whole entity.
_Not to be confused with_: player profile (values one player bought or upgraded)

**Level limits**: copies of every building and the field count unlocked per level (`level_limits.json`).

**Mastery bonus**: the speed-up of one building per star below three (`mastery_bonuses.json`).

## Graph

**Edge type**: `produces` (source location → raw good), `consumes` (input good → location), `outputs` (location → recipe output); parallel edges are merged into one.

**Proximity graph**: undirected graph of locations only; an edge joins a producer and a consumer of the same good, weights diffused over a few hops. Its one-hop weights are the coupling the blocks use.

## Player

**Player profile**: what the player bought, upgraded or earned (level, barn / silo, copies, slots, mastery, animals); `null` means level default.
_Not to be confused with_: farm map (positions), design settings (taste)

**Level default**: the value used when the profile leaves an item open, derived from the level and the shared data.

**Farm map**: the player's measured farm map: size, fixed items, plots, zones, background screenshot.
_Related_: `FarmMap` (one model for every area)

**Base map**: the part of the farm map every profile shares: size, fixed items, plots, `buildable` and `blocked` zones; geometry only, no screenshot; committed as `data/base_map.json`.
_Not to be confused with_: profile map

**Profile map**: one farm's state on the base map: unlocked plots, `design` zones, current farm, background screenshot (`config/profile_map.json`). Merged with the base map it is the farm map.

**Farm profile**: one named farm in one JSON file: player profile, profile map, design and planner settings, design templates (`--farm-profile`); in the web app (v2.4) stored locally, several of them simulate different players.
_Not to be confused with_: player profile (only what the player bought, upgraded or earned)

**Data bundle**: every shared data file (`data/*.json` with the overrides merged, `base_map.json`) in one generated JSON file; a client without file access loads it in one request.
_Not to be confused with_: data set (`DataSet`, the validated models in memory)

**Schema version**: the `schema_version` number an input file starts with; an older file is upgraded on load, a newer one is an error.

**Level recommendation**: the plan and layout precomputed at build time for one level with level defaults and default settings, on section `base` only (`python -m src recommend`); shown on the static site without a farm profile.
_Not to be confused with_: recommendation (one count the plan proposes)

**Farm view**: the interactive map of a layout on the site (v2.3): pan, zoom, block selection with the block detail panel; the area outside the buildable zones is faint.

**Plot recommendation** (v2, planned): the smallest connected set of plots, unlockable in game order, that fits the blocks of a level or a farm profile.

**Plot**: one farm expansion, numbered like the wiki, unlocked or not; the starting land is section `base`.

**Usable tiles**: tiles the layout may use: unlocked plots, then only `buildable` zones (if any), minus `blocked` zones (and `design` zones when they are kept free).

**Calibration**: the origin and the two tile axes measured on the background screenshot, mapping tile corners to pixels.

**Reference overlay**: another image (the wiki plot map) aligned to the screenshot in the map editor to trace plot borders; not saved in the JSON.

**Zone**: hand-marked tiles of the farm map: `buildable` (land the layout may use), `blocked` (water, road, paved strip) or `design` (a design zone).

**Layout overlay**: a planned layout (`layout.json` or the `layout` part of `combined.json`) drawn over the farm map in the map editor, view only, at its own tile coordinates; never shifted, only a warning when it was planned on another map.
_Not to be confused with_: reference overlay (another image aligned to the screenshot to trace plots)

**Current farm**: where the player's production buildings, shelters, barn and silo stand now (`current` in the farm map, one **current item** per placed copy; fields, trees and bushes only counted); the start of a relocation plan. The Layout Planner ignores it.
_Not to be confused with_: fixed building (never moves), layout (the suggested arrangement)

**Current item**: one entry of the current farm (`CurrentItem`): a placed copy of a movable farm location (tile, size as measured, rotation allowed for `rotatable` items) or, without a position, a count of copies (fields, trees, bushes).
_Not to be confused with_: layout item (where a copy should stand), fixed item (an entry of `fixed`)

**Relocation plan**: keep / store / place lists that turn the current farm into a layout (`python -m src relocate`). Keep: a current item exactly at a layout item of its id. Store: every other current item. Place: the remaining layout items, grouped by block.

## Layout

**`Block`**: locations placed as one movable unit: a production block, the Storage block or the Shared fields block.

**Production block**: buildings that belong together (anchor, its suppliers, its fields), named after its main building ("Dairy block").

**Anchor**: the production building a block is built around.

**Storage block**: the barn and the silo, placed as one block unless measured on the map.

**Dedicated fields**: the fields a block owns for the crops its buildings use.

**Shared fields block**: fields for crops no block uses, rarely used crops and owned fields the plan leaves empty (`shared_fields_block`).

**Frame**: the rectangle a placed block takes on the map, its items plus reserve; `None` when the block did not fit (an **unplaced block**).

**Patch**: a near-square group of equal units (fields, bushes) packed as one box inside a frame.

**Gap**: free tiles between blocks (`gap`).
_Not to be confused with_: item gap (free tiles inside a block)

**Free tiles**: usable tiles outside every frame and fixed item after the layout.

**Support relation**: a non-production neighbour rule, e.g. nectar bushes next to the beehive tree.

**Coupling**: how strongly two locations or blocks belong together, from the graph weights (and goods flows in the Combiner).

**Flow order**: blocks from upstream (makes inputs) to downstream (uses them).
_Not to be confused with_: goods flow (an amount per hour between two blocks)

**Goods flow**: goods per hour one block's buildings make for another block's buildings, from the production plan.

**Weighted flow distance**: the sum of goods per hour x tiles apart over every goods flow of a combined plan; one number to compare layouts (lower is better).

**Reserve**: extra free area inside a block frame for later unlocks; lowered step by step when blocks do not fit.

**Reserved copy**: a copy unlocked (or unlocked within the lookahead) but not owned yet; its space is kept free.

**Placeholder**: one copy shown for a tree or bush whose count is unknown.

**Strategy**: the order in which blocks are placed: `coupling`, `size`, `flow`, `auto`.

## Design

**Design layer**: optional additions to the functional layout: paths and decoration band.

**Path**: walkable tiles connecting blocks and key buildings into one network: the main path and the side paths.

**Main path**: the path from the hub to the key buildings and the Storage block, built first; one or two tiles wide (`main_path_width`).
_Related_: side path

**Side path**: a one-tile path joining a block to the nearest point of the network.

**Second lane**: the extra tiles of a 2-tile main path (the path shifted one diagonal step); where it does not fit, the main path is **narrowed** to one tile.

**Path style**: how a path runs between its ends: `shortest`, `straight` (few corners) or `stepped` (staircase along the straight line).

**Key building**: a building the player walks to often (farmhouse, barn, silo, truck, roadside shop, riverboat); the main path connects it. All are fixed except the barn and silo, which are placed in the Storage block.

**Terminal**: a target the path network must reach (a key building, a block, a patch of fields); reached at any free tile next to it.

**Hub**: where the path network starts: farmhouse (else the Storage block).

**Connection point**: the reachable free tile nearest to a key building that non-buildable ground cuts off; the path ends there.

**Decoration band**: free tiles within a given distance of a path, kept for decorations and fences.

**Design zone**: tiles of the farm map with existing decorations; no block goes there, paths may cross it.
_Not to be confused with_: decoration band (free tiles the layout leaves along paths)

**Design template**: a small grid pattern of buildings and decoration tiles (`config/templates/<name>.json`) assigned to a block: its area is kept free in the block frame (`reserve`), or its buildings are fixed positions the rest of the block is packed around (`arrange`). A wish: dropped before the reserve when the blocks do not fit.
_Not to be confused with_: design zone (existing decorations on the farm map)

**Dropped template**: a design template removed so that every block fits (`templates_dropped`).

**Item gap**: free tiles between the buildings of one block; a wish, lowered when the blocks would not fit otherwise.
_Not to be confused with_: gap (free tiles between blocks)

**Design figures**: numbers to compare design settings: path tiles, corners, detour ratio, free tiles per block.

**Design settings**: the player's chosen layout and design options, one flat object kept in the design settings file.
_Not to be confused with_: player profile (progress), planner settings (production and Combiner parameters)

**Planner settings**: production and Combiner parameters (login window, storage share, lookahead), kept in the planner settings file.

## Production

**Production plan**: steady-state amounts per hour for one login window, from a linear program.

**Login window**: the daily active hours (`start`-`end`) and the number of logins spread evenly in them; the night outside it is one long gap (`login_window`). Replaces the round-the-clock login interval.

**Login gap**: the time between two consecutive logins; a day has one per login, the night gap is the longest. Fields, animals and trees are served only at a login.
_Not to be confused with_: login interval (the former even gap around the clock, no longer used)

**Line**: what produces in parallel at a location: a machine copy (one item at a time, slots only queue) or an animal.

**External good**: a good the plan uses but cannot make (ores from the mine, fish); its use is capped, never planned.
_Not to be confused with_: external input (voucher, diamond, lure, fishing spot: no good at all)

**Skipped recipe**: a recipe with an external input; not planned, listed in `plan.skipped_recipes`.

**Balance**: the same spare amount per hour of every good, maximized first by the linear program.

**Storage share**: the part of barn and silo that the goods made between two logins may fill (`storage_share`, default 0.5).

**Min efficiency**: the share of the best production time the suggested number of logins must keep (`min_efficiency`, default 0.8); the best is taken over up to 8 logins.

**Recommendation**: a count the plan proposes where the profile is open: fields, trees and bushes, feeder bushes per day.

**Feeder bush**: a bush planted to feed a producer: nectar bush for beehive trees, peanut bush for squirrel houses (`FEEDER_BUSHES`).

**Login action**: one step of the fixed order at every login: collect, feed, plant, fill machine queues, sell the surplus.

## Combiner

**Sizing**: production quantities handed to the layout: copies, fields per crop, goods flows, extra reserves.

**Lookahead**: how many levels ahead the Combiner keeps space for unlocks.

**Upcoming unlock**: a new building, more copies or more fields within the lookahead (`upcoming_unlocks`).

**Combined plan**: the layout sized by the production plan, with one report.
