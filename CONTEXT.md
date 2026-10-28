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

## Player

**Player profile**: what the player bought, upgraded or earned (level, barn / silo, copies, slots, mastery, animals); `null` means level default.
_Not to be confused with_: farm map (positions), design settings (taste)

**Level default**: the value used when the profile leaves an item open, derived from the level and the shared data.

**Farm map**: the player's measured farm map: size, fixed items, plots, zones, background screenshot.
_Related_: `FarmMap` (one model for every area)

**Plot**: one farm expansion, numbered like the wiki, unlocked or not; the starting land is section `base`.

**Zone**: hand-marked tiles of the farm map: `buildable` (land the layout may use), `blocked` (water, road, paved strip) or `design` (a design zone).

**Layout overlay**: a planned layout (`layout.json` or the `layout` part of `combined.json`) drawn over the farm map in the map editor, view only, at its own tile coordinates; never shifted, only a warning when it was planned on another map.
_Not to be confused with_: reference overlay (another image aligned to the screenshot to trace plots)

**Current farm**: where the player's production buildings, shelters, barn and silo stand now (`current` in the farm map, one **current item** per placed copy; fields, trees and bushes only counted); the start of a relocation plan. The Layout Planner ignores it.
_Not to be confused with_: fixed building (never moves), layout (the suggested arrangement)

**Current item**: one entry of the current farm (`CurrentItem`): a placed copy of a movable farm location (tile, size as measured, rotation allowed for `rotatable` items) or, without a position, a count of copies (fields, trees, bushes).
_Not to be confused with_: layout item (where a copy should stand), fixed item (an entry of `fixed`)

**Relocation plan**: keep / store / place lists that turn the current farm into a layout (`python -m src relocate`). Keep: a current item exactly at a layout item of its id. Store: every other current item. Place: the remaining layout items, grouped by block.

## Layout

**`Block`**: a production block: buildings that belong together (anchor, its suppliers, its fields), placed as one movable unit, named after its main building ("Dairy block").

**Anchor**: the production building a block is built around.

**Storage block**: the barn and the silo, placed as one block unless measured on the map.

**Dedicated fields**: the fields a block owns for the crops its buildings use.
_Related_: Shared fields block (fields for crops no block uses, and spare fields)

**Support relation**: a non-production neighbour rule, e.g. nectar bushes next to the beehive tree.

**Coupling**: how strongly two locations or blocks belong together, from the graph weights (and goods flows in the Combiner).

**Flow order**: blocks from upstream (makes inputs) to downstream (uses them).
_Not to be confused with_: goods flow (an amount per hour between two blocks)

**Goods flow**: goods per hour one block's buildings make for another block's buildings, from the production plan.

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

**Key building**: a fixed building the player walks to often (farmhouse, barn, silo, truck, roadside shop, riverboat); paths connect it.

**Hub**: where the path network starts: farmhouse (else the Storage block).

**Connection point**: the reachable free tile nearest to a key building that non-buildable ground cuts off; the path ends there.

**Decoration band**: free tiles within a given distance of a path, kept for decorations and fences.

**Design zone**: tiles of the farm map with existing decorations; no block goes there, paths may cross it.
_Not to be confused with_: decoration band (free tiles the layout leaves along paths)

**Design template**: a small grid pattern of buildings and decoration tiles (`config/templates/<name>.json`) assigned to a block: its area is kept free in the block frame (`reserve`), or its buildings are fixed positions the rest of the block is packed around (`arrange`). A wish: dropped before the reserve when the blocks do not fit.
_Not to be confused with_: design zone (existing decorations on the farm map)

**Item gap**: free tiles between the buildings of one block; a wish, lowered when the blocks would not fit otherwise.
_Not to be confused with_: gap (free tiles between blocks)

**Design figures**: numbers to compare design settings: path tiles, corners, detour ratio, free tiles per block.

**Design settings**: the player's chosen layout and design options, one flat object kept in the design settings file.
_Not to be confused with_: player profile (progress), planner settings (production and Combiner parameters)

**Planner settings**: production and Combiner parameters (login interval, storage share, lookahead), kept in the planner settings file.

## Production

**Production plan**: steady-state amounts per hour for one login interval, from a linear program.

**Login interval**: hours between two logins; fields, animals and trees are served only at a login.

**Line**: what produces in parallel at a location: a machine copy (one item at a time, slots only queue) or an animal.

**External good**: a good the plan uses but cannot make (ores from the mine, fish); its use is capped, never planned.

**Recommendation**: a count the plan proposes where the profile is open: fields, trees and bushes, nectar bushes per day.

## Combiner

**Sizing**: production quantities handed to the layout: copies, fields per crop, goods flows, extra reserves.

**Lookahead**: how many levels ahead the Combiner keeps space for unlocks.

**Combined plan**: the layout sized by the production plan, with one report.
