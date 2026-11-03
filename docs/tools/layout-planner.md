# Layout Planner

How the Layout Planner (`src/layout/`) arranges the farm into production blocks. The farm map it reads and the map editor are in [map-editor.md](map-editor.md); the settings are in [settings.md](../settings.md).

## Purpose

Help the player design an efficient and expandable layout by discovering natural groups of buildings that belong together.

## Design layer (optional)

`design_layer: true` in [`config/design.json`](../settings.md) adds walkable paths and a decoration band on top of the functional layout (`src/layout/design.py`):

- Paths connect every block and the key buildings into one network: on the farm the farmhouse, barn, silo, truck, roadside shop and riverboat (hub: the farmhouse, else the Storage block, else the first terminal by id that has a free tile next to it). The network grows from the hub, each time by the shortest path on free tiles to the nearest building not reached yet.
- The **main path** is built first: from the hub to the key buildings and the Storage block (barn and silo). Then **side paths** (1 tile wide) join every other block to the nearest point of the network.
- `main_path_width` (1 or 2, default 1): a 2-tile main path gets a second lane, the path shifted one diagonal step to its freer side. Where it does not fit between two blocks it narrows to 1 tile, and the report counts those tiles (on the measured farm 46 with `gap: 1`). A larger `gap` gives it room, but takes area: on the measured farm `gap: 2` leaves one block unplaced.
- A key building with no reachable free tile next to it gets a path to its **connection point**, the reachable free tile nearest to it. On the farm the riverboat stands behind a paved strip that is not buildable (mark it as a `blocked` zone; the leaderboard stands there too, but it is not a key building): the path ends at the edge of the buildable land, and the notes give the tiles left in between. A building more than 5 tiles beyond the reachable land stays unreachable.
- The decoration band is the free tiles within `decor_band` tiles of a path (default 1): room for decorations and fences, not for buildings.
- With the design layer the blocks keep at least one free tile between them (`gap` ≥ 1), so a path always fits. Buildings no path can reach are listed in the notes.
- `path_style`: `shortest` (default) takes any shortest path; `straight` adds a cost to every change of direction, so paths have fewer corners and detours (on the measured farm 16 corners instead of 20); `stepped` takes the shortest path closest to the straight line between its ends, a staircase that looks diagonal and curved on the isometric grid. `main_path_style` (default: the same as `path_style`) styles the main path alone, e.g. a `straight` main path with `stepped` side paths.
- `path_targets` (farm): `blocks` (default) connects the blocks and the key buildings; `buildings` connects every building and every field / tree / bush patch inside the blocks; the paths may cross the free part of a block frame, but the decoration band stays out of it (it is the reserve for later unlocks). With the design layer on it needs `item_gap` ≥ 1, so a path fits between the buildings.
- `item_gap` (farm, default 0): free tiles between the buildings of a block, so blocks look less packed; patches stay whole. Placing every block comes first, looks second: when the blocks do not fit, the item gap is lowered step by step (at the requested reserve) before the reserve is; with no gap left, `path_targets: buildings` falls back to `blocks`. The report shows the gap used and the one asked for (on the measured farm `item_gap: 1` drops to 0: at a 0 % reserve its block frames take about 1,260 tiles, about 1,545 with the gaps between the blocks, and the unlocked plots have 1,546 usable tiles; with gap 0 the frames take about 880).
- Design zones (`design` zones of the farm map, `design_zones`, default on): existing decorations; no block is placed there, paths may cross them, and the decoration band leaves them alone.
- Figures in `layout.md` / `layout.json` (`design.figures`) to compare settings: path tiles (main and side paths apart, narrowed main path tiles), corners (turns and junctions of the centre lines), detour ratio (tiles walked per tile of grid distance), free tiles per block, unreachable buildings, design zone tiles.

## Design templates (optional)

A design template is a small grid pattern of buildings and decoration tiles, one file per template in `config/templates/<name>.json` (git-ignored; `dairy_garden.example.json` is the committed example and the fallback for that name). Coordinates are tiles from the template's top corner, with the axes of the farm map; decorations are tile rectangles that are only "taken":

```json
{
  "width": 9, "height": 5,
  "buildings": [
    {"location_id": "dairy", "x": 0, "y": 0, "width": 4, "height": 4},
    {"location_id": "cow_pasture", "x": 5, "y": 0, "width": 4, "height": 4}
  ],
  "decorations": [[4, 0, 1, 4], [0, 4, 9, 1]]
}
```

`templates` in [`config/design.json`](../settings.md) assigns templates to blocks (`src/layout/templates.py`, used by the Layout Planner and the Combiner):

- `reserve` (default): the block frame grows by the template, and its whole area stays free of buildings and paths.
- `arrange`: the template's buildings stand at their template positions and count as copies of the block, its decoration tiles stay free, and the rest of the block is packed around them. Its other tiles stay empty (paths may cross them; the figures count them as free tiles of the block). A template copy the player does not own is reserved space.
- A template is a wish: when the blocks do not fit, `item_gap` is lowered first, then the templates are dropped (with a warning in the log and the report), and only then the reserve.
- Errors: a template building that is not in the block, or whose size is not its footprint (the swapped size is accepted for a `rotatable` location). A block that does not exist at the player's level only gets a log line. Templates are never rotated or mirrored.
- `layout.json` / `combined.json` give the template of every block (`template`: name, mode, rect, decoration cells) and `templates_dropped`; the SVG draws it pink (dashed outline in `reserve` mode), and the map editor overlay shows it too.
- The map editor makes templates in step 9 (see "Measuring with the map editor").

## How it works (farm)

1. Loads the normalised JSON data (locations, resources, recipes), filtered to the player level.
2. Builds a weighted directed dependency graph with three edge kinds:
   - PRODUCES (location → resource)
   - CONSUMES (resource → location, weight = input/output ratio)
   - OUTPUTS (location → resource)
3. Derives a location-proximity graph (multi-level weight propagation with decay).
4. For analysis only, detects communities on the proximity graph (Louvain; `python -m src.main`, `analysis.json`). The layout does not use them.
5. Builds **named blocks** for placement (`python -m src.layout`, `src/layout/blocks.py`):
   - every production building is an anchor;
   - every tree, bush and animal shelter joins the anchor with the strongest direct coupling;
   - support relations pull non-production neighbours along (nectar bushes join the beehive tree, peanut bushes the squirrel house);
   - a lone building merges into the block it is most coupled to (at most 3 production buildings per block; suppliers do not count); a big crop user (at least 10 % of the farm's crop demand, e.g. the feed mill) is never lone, because its fields are its suppliers;
   - the block is named after its main building ("Dairy block").
6. Counts the copies per location: player profile, else everything the level allows, else one placeholder tree / bush (the Combiner sizes them from the plan).
7. Gives **every block its own fields** (`src/layout/fields.py`), so crops such as corn for the feed mill or sugarcane for the sugar mill can stay planted: the fields are shared out in proportion to the block's crop demand (sum of the crop CONSUMES weights into its buildings), at least one per crop-using block. `field_pool: 0.1` keeps 10 % in a separate "Shared fields block". The counts are estimates; the Combiner sizes them from the production plan.
8. Packs each block (buildings one by one, fields / trees / bushes as patches, `item_gap` free tiles between the buildings), grows its frame by a reserve (default 20 %) and keeps unlocked but not yet owned copies as reserved space.
9. Packs the block frames on the farm map around the fixed buildings, `gap` free tiles apart (default 1), pulling coupled blocks together. `strategy` sets the block order: `coupling`, `size` (largest first), `flow` (upstream first along the processing order), `auto` (default) or `all` (one output set per order: coupling, size, flow).
   When a block does not fit, placing every block comes first, in this order:
   1. `item_gap` is lowered step by step, at the requested reserve;
   2. the design templates are dropped (with a warning);
   3. the reserve is lowered in 1 % steps down to 0.
   At each reserve `auto` tries coupling, then size. `flow` keeps the processing order down to a 0 % reserve and only then tries size the same way. An explicit `coupling` or `size` never switches order.
10. With `design_layer: true`, adds the design layer (see below).
11. Writes `output/layout.svg` (isometric tile grid with every footprint; paths sand-coloured, decoration band light green), `output/layout.md` (block list, design summary, upstream → downstream order, recommended neighbourhoods) and `output/layout.json`.

A production block is a movable logical unit, for example:

- 1× Dairy
- related Cow Pasture(s)
- Feed Mill
- the appropriate number of fields

## Placement inputs (already in the data)

- **Footprints** in tiles (`footprint_width` × `footprint_height`) for every movable location at the current level. Machine sizes come from the wiki, the rest were measured in the game.
- **Fixed buildings**: the `fixed` list of the farm map (farmhouse, truck, roadside shop, …) and locations with `movable: false` (the mine) stay where they are; barn and silo are movable since v1.3 and form the Storage block; fishing lake buildings are never placed on the farm.
- **Rotation** (`rotatable`): non-square items that can be turned, e.g. the 1×2 raspberry and blackberry bushes and the 3×2 ice cream maker.
- **Copies per level** (`level_limits.json`): how many feed mills, coops, … are available.
- **Support relations** (`src/layout/support.py`): non-production neighbours, e.g. nectar bushes next to the beehive tree, peanut bushes next to the squirrel house.

## Evolution

| Horizon     | Output                                                                                                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Short term  | Weighted graph + detected production blocks (done)                                                                                                                                                     |
| Medium term | Named blocks with footprints and a simple graphical layout, without production data (v0.6, measured farm map)                                                                                          |
| Long term   | Complete expansion-friendly farm layout, so the farm does not need a full rebuild at every level. With Design planning, space is reserved for paths and decorations (v0.8: paths and decoration band). |
