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

**Fixed building**: a location or map item the player cannot move (`movable: false`), e.g. the mine, the farmhouse.
_Not to be confused with_: movable map item (`movable: true`): measured, but placed by the planner

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

**Current farm** (planned, v1.3): where the player's production buildings, shelters, barn and silo stand now, measured on the farm map; the start of a relocation plan.
_Not to be confused with_: fixed building (never moves), layout (the suggested arrangement)

**Relocation plan** (planned, v1.3): keep / store / place lists that turn the current farm into a layout, grouped by block.

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

**Path**: one-tile-wide walkable tiles connecting blocks and key buildings into one network.

**Main path** (planned, v1.4): the path from the hub to the key buildings, built first; one or two tiles wide.
_Related_: side path

**Side path** (planned, v1.4): a one-tile path joining a block to the nearest point of the network.

**Key building**: a fixed building the player walks to often (farmhouse, barn, silo, truck, roadside shop, riverboat); paths connect it.

**Hub**: where the path network starts: farmhouse (else the Storage block).

**Connection point**: the reachable free tile nearest to a key building that non-buildable ground cuts off; the path ends there.

**Decoration band**: free tiles within a given distance of a path, kept for decorations and fences.

**Design zone**: tiles of the farm map with existing decorations; no block goes there, paths may cross it.
_Not to be confused with_: decoration band (free tiles the layout leaves along paths)

**Design template** (planned, v1.5): a small grid pattern of buildings and decoration tiles for a block: kept free (`reserve`) or used as fixed positions the block is arranged around (`arrange`).
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
