# Farm map and map editor

The farm map is player data: the measured land, the fixed buildings, the plots, the zones and the current farm. `tools/farm_map_editor.html` measures it from a screenshot.

## Farm map (player data)

Every farm has its own expansions and its own spot for the farmhouse, mine, truck, …, so the usable area is measured per farm. Since v2.0 it is kept in two files: the geometry every player shares in `data/base_map.json` (size, fixed buildings, plots, `buildable` / `blocked` zones) and the player's state in `config/profile_map.json` (git-ignored: unlocked plots, `design` zones, current farm, screenshot; format in [data-model.md](../data-model.md#profile-map)). The tools merge the two. The one-file format below (`config/farm_map.json`, before v2.0) holds both parts; the tools and the editor still read it, and `python -m src migrate-map` splits it.

```json
{
  "width": 60,
  "height": 55,
  "fixed": [
    { "id": "farmhouse", "x": 20, "y": 18, "width": 6, "height": 6 },
    { "id": "mine", "x": 52, "y": 2, "width": 4, "height": 4 }
  ],
  "current": [
    { "id": "bakery", "x": 30, "y": 12, "width": 3, "height": 3 },
    { "id": "field", "count": 24 }
  ]
}
```

The values above are only an illustration. Coordinates are tiles from the farm's top corner, with `x` along the ↘ edge and `y` along the ↙ edge. `null` means not measured yet: without `width` / `height` the layout is unbounded, and a fixed item without a position is listed in the notes but not drawn. A fixed item whose id is a location (`mine`) also pulls the coupled block (smelter) toward it.

The file can also hold a calibrated screenshot (`background`) and the farm plots (`expansions`, numbered like the wiki page Expansion/Farm, each a list of tile rectangles with an `unlocked` flag). With a background, `layout.svg` draws the screenshot under the grid. When at least one drawn plot is `unlocked` (draw the starting land as section `base`), blocks are placed only on unlocked plots; plots without rectangles are ignored. Plots of section `base` (the starting land) always count as unlocked. `fixed` holds only buildings the game never moves; the planner places the barn and silo as the Storage block, and a movable location listed in `fixed` is an error. `current` is the current farm: where the player's production buildings, shelters, barn and silo stand now (one entry with a position per copy), fields, trees and bushes only as counts (`count`). The Layout Planner ignores it; `python -m src relocate` reads it (see "Relocation plan"). Farm maps from before v1.3 (barn and silo in `fixed`, a `movable` flag) fail with a clear error: open them in the map editor and save them again. `zones` are hand-marked tile rectangles: blocks stay inside the `buildable` zones (if any) and never touch `blocked` ones (water, road, forest, …).

The editor reads and writes both parts (v2.0.1). **Open JSON…** takes `data/base_map.json` and `config/profile_map.json` together (select both), one of them (the other part already in the editor is kept: a profile map needs a base map opened before, and asks first when the measured geometry has unsaved changes, which it would drop), or a one-file `farm_map.json`, which it splits. A newer `schema_version` than the editor knows is an error. The files it writes are the same as those of `migrate-map`, one line per fixed item, plot and zone.

### Measuring with the map editor

`tools/farm_map_editor.html` is a self-contained page (open it in a browser, no server, nothing is uploaded). It is kept in the browser and saved as `profile_map.json` (save it as `config/profile_map.json`) and, after measuring the geometry, `base_map.json` (save it as `data/base_map.json`). The toolbar holds opening files, saving and zoom; the side panel lists the steps with their progress, can be resized by dragging its edge and hidden with `\`; the buildings and plots lists can be filtered; `?` shows every shortcut (`1`-`9` steps, `Ctrl+S` save, `Ctrl+Z` undo).

Preparation in the game:

- Open a **new layout slot** in Layout Edit Mode (level 37+): it starts empty, so only the fixed buildings remain. With the paintbrush, lay two rows of fields in an L shape from one corner field (one row ↘, one row ↙, 10+ fields each) as a ruler.
- Zoom out fully, take screenshots at the same zoom, and stitch them without scaling or rotating; remove UI elements. Save the result as **PNG** in `config/farm_background.png` (git-ignored). Keep the GIMP file (`.xcf`) and the raw screenshots in `config/screenshots/`, and the wiki plot maps used on the Reference tab in `config/reference/`; both folders are git-ignored (player data, wiki licence, file size). Manual stitching in GIMP:
  - Take all screenshots in **one session**, with overlap between neighbours. After closing the game the same zoom cannot be reproduced, and details of locked plots (e.g. stone wall textures) change, so later shots do not match.
  - **File → Open as Layers** loads all screenshots at once; enlarge the canvas with **Image → Canvas Size** (resize layers: none), then move each layer into place by hand.
  - Small black gaps where no screenshot covers the farm are acceptable, as long as the ruler fields and the fixed buildings are visible.
  - Tile accuracy is enough: an error of a few pixels does not matter for the calibration.

The editor's steps (the numbered tabs of the side panel):

1. **Calibrate**: load the PNG, click A (top corner of the corner field), B (right corner of the last ↘ field), C (left corner of the last ↙ field), enter the two row lengths and apply. The grid must follow the field edges everywhere. A placed point can be dragged to a better spot; apply again afterwards.
2. **Buildings** (fixed): pick an id (farmhouse, mine, truck, …) and drag over its tiles. Only buildings the game never moves; the barn and silo go to step 8.
3. **Reference overlay** (optional): overlay the wiki plot map (Expansion/Farm) to trace plot borders that unlocked plots no longer show. Zoom to the part of the farm the overlay shows, then load it: it starts fitted into the visible area. Click 3 point pairs far apart, each first on the overlay and then on the same spot of the farm (r1, m1, r2, m2, r3, m3). After each pair the overlay snaps closer (1 pair: moved, 2 pairs: scaled and rotated, 3 pairs: fully fitted), so the later points need less zoom. Placed points can be dragged; where an r and an m point overlap, the drag takes the m point (Shift: the r point). The overlay is not saved in the JSON.
4. **Plots (expansions)**: add a plot (section + wiki number, unlocked or not) and drag one or more rectangles over its tiles; touching rectangles of one plot merge into one shape, Alt + drag erases tiles.
5. **Zones**: mark the farm sections as **buildable** (green), water, roads, forest, paved strips (e.g. in front of the riverboat), … as **blocked** (red), and existing decorations the layout should keep as **design** (violet), each as tile rectangles.
6. **Export**: **Save profile map** writes `profile_map.json` (save it as `config/profile_map.json`; `Ctrl+S` and the toolbar button do the same). **Save base map** writes `base_map.json` (save it as `data/base_map.json`); the panel says whether the measured geometry matches the loaded base map, and saving the profile map warns when it does not. Only a changed geometry is cropped (by default with a 5-tile margin around the plots, buildable zones, fixed buildings and current items, so the outline follows the real farm); a loaded, unchanged base map keeps its coordinates. A crop moves every rectangle and the screenshot calibration, so the profile map is saved with it. Also: the full map PNG with grid, fixed buildings and plots, or a ZIP with `pieces/<plot>.png` (one cropped PNG per plot), `pieces/index.json` (crop in pixels, tile bounds), `base_map.json` and `profile_map.json`. The visible layers decide what the PNGs show; the editor keeps its state in the browser, and an exported JSON can be loaded again to continue.
7. **Layout overlay** (view only): load `output/layout.json` or `output/combined.json` to check the planned layout on the screenshot: block frames with names, items (reserved space dashed), paths and the decoration band, as the `layout` layer. Hovering an item shows its block and id in the status bar. The overlay uses the tile coordinates of the farm map it was planned on and is never shifted; when its map size or a fixed building's position differs from the loaded map (e.g. planned before the map was cropped on save, or without a farm map), the editor warns: plan again after every re-save of the base map. It is kept in the browser, not in the map JSON.
8. **Current farm**: where the production buildings, shelters, barn and silo stand now. Pick an id and drag over the item; every drag adds one copy. With a layout loaded in step 7 its ids are offered with their sizes, a click places the item at that size, and a rectangle of another size (rotation allowed) is flagged; without a layout any id can be typed. Fields, trees and bushes are counted only (**Set count**). A farm map from before v1.3 loads with its measured barn and silo moved here. Saved as `current` in the profile map.
9. **Templates**: make a design template. On the **farm map**, the **cut** tool takes the current items (step 8) fully inside the dragged rectangle and its design-zone tiles (step 5). Another design can be loaded as a **design screenshot** and calibrated as its own background (A, B, C as in step 1, tool **calibrate**). On either surface, **frame** drags the template rectangle, **building** adds one copy of an id (a click uses its layout size from step 7), **decoration** marks taken tiles (Alt + drag erases). **Download template** writes `<name>.json` relative to the frame (save it in `config/templates/`); only buildings fully inside the frame are kept, overlapping buildings stop the download, and a building wins over a decoration tile. **Open template** loads a template file to edit it. The template is kept in the browser, never in the map JSON.

The game's Layout Edit Mode shows no tile grid, so the graphical output always draws the grid and every footprint.
