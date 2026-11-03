# Settings

Tool settings: how a tool works. They live only in config files, never in CLI options.

How the tools work is set in config files, never on the command line: the CLI only says what to run (`--level`, `--player-config`, `--map`, `--design-config`, `--planner-config`, `--data-dir`, `--output-dir`). Each file has a committed example and a local, git-ignored copy that wins; without either, the built-in defaults of `src/settings.py` apply. Every run logs the file it used, and `layout*.json`, `schedule.json` and `combined.json` record the settings in a `settings` key.

`config/design.json` (Layout Planner, design layer, Combiner layout): one flat object; a missing key keeps its default.

```json
{
  "gap": 1,
  "design_layer": false,
  "decor_band": 1,
  "path_style": "shortest",
  "main_path_style": null,
  "main_path_width": 1,
  "design_zones": true,
  "reserve": 0.2,
  "strategy": "auto",
  "field_pool": 0.0,
  "item_gap": 0,
  "path_targets": "blocks",
  "block_images": true,
  "templates": {}
}
```

| Key               | Meaning                                                                                             | Default  |
| ----------------- | --------------------------------------------------------------------------------------------------- | -------- |
| `gap`             | free tiles between blocks                                                                           | 1        |
| `design_layer`    | paths and decoration band (gap is then at least 1)                                                  | false    |
| `decor_band`      | decoration band width next to the paths                                                             | 1        |
| `reserve`         | extra free area per block for later unlocks                                                         | 0.2      |
| `strategy`        | block order: `auto`, `coupling`, `size`, `flow`, or `all` (one output set per order)                | auto     |
| `field_pool`      | share of the fields in a separate Shared fields block (without production sizing)                   | 0        |
| `item_gap`        | free tiles between the buildings of a block; patches stay whole; lowered if the blocks do not fit   | 0        |
| `path_style`      | `shortest`, `straight` (fewer corners and detours) or `stepped` (staircase along the straight line) | shortest |
| `main_path_style` | style of the main path; `null` = `path_style`                                                       | null     |
| `main_path_width` | main path width, 1 or 2; narrows to 1 where 2 does not fit between the blocks                       | 1        |
| `path_targets`    | `blocks` (blocks and key buildings) or `buildings` (every building; needs `item_gap` ≥ 1)           | blocks   |
| `design_zones`    | keep the map's `design` zones free of blocks (paths may cross them)                                 | true     |
| `block_images`    | one SVG per block (`blocks/`, `combined_blocks/`) and a collage of every block                      | true     |
| `templates`       | block id → `{"template": name, "mode": "reserve" or "arrange"}` (see "Design templates")            | {}       |

`config/planner.json`:

```json
{
  "production": {
    "login_interval": null,
    "storage_share": 0.5,
    "min_efficiency": 0.8
  },
  "combiner": { "lookahead": 5, "strategy": "flow" }
}
```

| Key                         | Meaning                                                                       | Default |
| --------------------------- | ----------------------------------------------------------------------------- | ------- |
| `production.login_interval` | hours between logins; `null` = suggested                                      | null    |
| `production.storage_share`  | share of barn and silo the goods of one interval may fill (the rest is stock) | 0.5     |
| `production.min_efficiency` | the suggested interval keeps at least this share of the best production time  | 0.8     |
| `combiner.lookahead`        | levels ahead whose unlocks get space now (0 = none)                           | 5       |
