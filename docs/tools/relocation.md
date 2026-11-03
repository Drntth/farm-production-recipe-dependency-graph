# Relocation plan

From the current farm to the planned layout (`src/relocation/`, `python -m src relocate`).

## Relocation plan

`python -m src relocate [--layout PATH]` (package `src/relocation/`; not part of `all`) turns the current farm (`current` in the farm map) into the planned layout: `output/combined.json` by default, else `output/layout.json`.

1. **Checks** (each an error): the layout was planned on this farm map (same size, fixed buildings at the same tiles); every current id is a known, movable farm location; every measured size matches the data footprint (the swapped size only for `rotatable` items).
2. **Keep**: a current item at exactly the tile and size of a layout item of the same id stays (greedy, each layout item once).
3. **Store**: every other current item, including counted fields, trees and bushes. Layout Edit Mode can store every movable item, so no move order is needed.
4. **Place**: the remaining layout items, grouped by block, with their tile and rotation.
5. **Listed apart**: reserved space (copies for later levels, keep free), current copies the layout has no place for, layout copies the farm does not have yet.
6. A note when fewer items stay than have to be stored: a new layout slot (empty except the fixed buildings) is simpler then.

Writes `output/relocation.json` and `output/relocation.md`. Top-level keys of the JSON: `layout_file`, `level`, `summary` (counts: `current_copies`, `keep`, `store`, `place`, `reserved`, `not_in_layout`, `not_owned`), `new_slot_simpler`, `note`, and the lists `keep`, `store`, `place`, `reserved`, `not_in_layout`, `not_owned`.
