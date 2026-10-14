# Data overrides

Hand-maintained values that the wiki does not provide. The loader merges these files on top of the scraped `data/*.json` at every load, so re-scraping never overwrites them.

- An entry with an existing `id` patches only the fields it lists.
- An entry with a new `id` adds a complete entity.
- `null` means "not filled in yet" and is ignored. Replace it with a number when you have measured it.

Only **shared game facts** belong here, values that are the same for every player. Anything a player can upgrade or buy (machine slots, mastery, animals, beehives, lobster / duck slots, barn / silo) belongs in the player profile instead. See [docs/player-profile.md](../../docs/player-profile.md).

`recipes.json` is empty, because the wiki currently provides all of its values. `resources.json` holds the honeycomb estimate.

## Fields in `locations.json`

| Field              | Meaning                                                        |
| ------------------ | -------------------------------------------------------------- |
| `footprint_width`  | tiles along the **↘ edge** (see below)                         |
| `footprint_height` | tiles along the **↙ edge** (see below)                         |
| `movable`          | `false` for fixed buildings (mine, fishing lake buildings)     |
| `rotatable`        | `true` if the item can be turned in the game (default `false`) |
| `base_slots`       | slots per copy at purchase, where the wiki infobox has none    |
| `max_slots`        | maximum slots per copy, where it differs from the default 9    |
| `lifetime_yield`   | goods a tree / bush gives in its life (both or neither)        |
| `lifetime_harvests`| harvests of a tree / bush, including the revive                |

`footprint_width` and `footprint_height` must be filled in together. One without the other fails validation.  
Fixed buildings (`movable: false`) need no footprint. The layout planner leaves them where they are.  
`rotatable` only matters for non-square items. A 1×2 item that can be turned may also be placed as 2×1.  
The lobster pool and duck salon have no `slots` in their wiki infobox; their text says 1 slot at start and 6 at most, so both fields are set here.  
`lifetime_yield` / `lifetime_harvests` and the honeycomb `growth_time_seconds` are estimates; their basis and status are in [docs/wiki-gaps.md](../../docs/wiki-gaps.md). Replace them when they are measured in the game.

### Status

Complete for level 56: every movable location has a footprint, and every non-square item (`raspberry_bush`, `blackberry_bush`, `ice_cream_maker`) has `rotatable`. After raising the player level and re-scraping, run `python -m pytest`; new locations without a footprint must be added here.

### Orientation

The farm grid is isometric: every tile is a diamond. Look at the item from its **top (northern) corner**:

```text
                top corner
                    ◆
        height    ◆   ◆    width
        (↙ edge) ◆  ◆  ◆   (↘ edge)
                  ◆   ◆
                    ◆
```

- **width** = tiles from the top corner down to the **right** (↘)
- **height** = tiles from the top corner down to the **left** (↙)

The convention only matters for non-square items. For a size shown as `1x2`, enter `"footprint_width": 1, "footprint_height": 2`. Trees and bushes can be rotated in the game, so the layout planner may swap them.

### How to measure in the game

Layout Edit Mode shows **no grid**, so use one of these:

1. **Shop info (preferred):** tap the item in the shop before placing it. The game shows its size, e.g. "3x3" for the chicken coop.
2. **Field ruler:** a field is 1×1. Place fields next to the item along each edge and count them.
3. **Calibrate:** the Dairy is 4×4 according to the wiki. Measure it first to check the method.
