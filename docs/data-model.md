# Data model

The shared game data in `data/` and the pydantic models in `src/models/` that validate it.

All identifiers are snake_case English.  
The model is kept close to 3NF so the same structure can later be loaded into PostgreSQL.

## locations.json

Everything that occupies space (production buildings, animal shelters, fields, trees, bushes, storage…).

```json
{
  "id": "dairy",
  "name": "Dairy",
  "type": "production",
  "unlock_level": 6,
  "area": "farm",
  "footprint_width": 4,
  "footprint_height": 4
}
```

Allowed `type` values: `production`, `animal`, `field`, `tree`, `bush`, `storage`, `other`.  
Allowed `area` values: `farm` (default), `town`, `fishing_lake`. The scraper sets `fishing_lake` from the wiki category _Fishing Lake Buildings_. The Layout Planner places only `farm` locations; the farm map itself has no `area` key.  
`movable` is `true` by default. It is `false` for fixed buildings the player cannot move (mine, fishing lake buildings).  
`rotatable` is `false` by default. It is `true` when the footprint can be turned (width and height swapped). It only matters for non-square footprints such as the 1×2 bushes or the 3×2 ice cream maker.  
Every fruit tree and bush kind is its own location (`apple_tree`, `raspberry_bush`, …), because each is placed separately and has its own footprint and fruit. Trees and bushes that produce no goods (the nectar bush) come from the wiki category _Trees and Bushes_.  
Optional fields:

- `footprint_width` / `footprint_height`: size in tiles, both or neither. The wiki lists them for production buildings only; the rest come from `data/overrides/`.
- `animal_capacity`: maximum animals per shelter (e.g. 6 for a chicken coop). The player's actual animals, beehives and lobster / duck slots are in the profile.
- `base_slots` / `max_slots`: slots per copy at purchase and at most (see [Timing and capacity fields](#timing-and-capacity-fields); the rules are in [docs/game-facts/production-buildings.md](game-facts/production-buildings.md)).
- `lifetime_yield` / `lifetime_harvests`: goods and harvests of a tree / bush over its life, incl. a revive (estimates, see [docs/wiki-gaps.md](wiki-gaps.md)).
- `description`: free text, also on resources and recipes; the scraper does not fill it.

## resources.json

Crops, animal products, intermediate/processed goods and ores.

```json
{
  "id": "milk",
  "name": "Milk",
  "type": "animal_product",
  "unlock_level": 6,
  "source_location_id": "cow_pasture",
  "growth_time_seconds": 3600
}
```

`source_location_id` is mandatory for `crop`, `animal_product` and `ore`; only these types get a `PRODUCES` edge from their source location in the [graph](graph-model.md).  
Allowed `type` values: `crop`, `animal_product`, `processed_material`, `raw_material`, `ore`.  
`growth_time_seconds` is set for raw goods: crop growth, animal production, `0` for instant goods (ores, honeycomb). Processed goods carry their time on the recipe.

## recipes.json

Transformations that happen inside production locations, plus **feeding recipes** at animal shelters (`chicken_coop`: 1 `chicken_feed` → 1 `egg`), taken from the Goods List "Needs" column.  
Raw crops, ores and goods without needs (honeycomb) are resources only. The wiki names the caught animal for the lobster pool and duck salon; the normalizer maps it to the trap that catches it (`lobster` → `lobster_trap`, `duck` → `duck_trap`), so the net maker feeds the fishing-lake shelters.

```json
{
  "id": "cream",
  "name": "Cream",
  "location_id": "dairy",
  "unlock_level": 6,
  "inputs": [
    {
      "resource_id": "milk",
      "amount": 1
    }
  ],
  "output": {
    "resource_id": "cream",
    "amount": 1
  },
  "production_time_seconds": 7200,
  "production_time_3star_seconds": 6120
}
```

`production_time_3star_seconds` is the time with full 3-star mastery.  
Recipes may contain zero or more inputs. External/premium inputs (vouchers, diamonds, etc.) are allowed but never become graph nodes.

## meta.json

Written by the scraper. It records where and when the data came from, and is used by the [game update process](game-updates.md).

```json
{
  "scraped_at": "2026-10-14T08:54:12+00:00",
  "max_level": 126,
  "known_game_version": "1.73",
  "wiki_revisions": { "Goods_List": "2026-07-29T14:20:27Z" }
}
```

## level_limits.json

Level-gated limits, as two 3NF tables:

- `field_grants`: new fields per level (from the wiki's _Experience Levels_ pages). The total at a level is the sum of all grants up to that level.
- `location_instances`: one row per placeable copy of a production building or shelter, with its unlock level (e.g. the second Feed Mill at level 12).

```json
{
  "field_grants": [
    { "level": 1, "count": 6 },
    { "level": 3, "count": 3 }
  ],
  "location_instances": [
    { "location_id": "feed_mill", "instance": 1, "unlock_level": 2 },
    { "location_id": "feed_mill", "instance": 2, "unlock_level": 12 }
  ]
}
```

`LevelLimits.fields_at(level)` and `LevelLimits.instances_at(location_id, level)` answer "how many at my level". Fields, trees and bushes beyond the grants can be bought, so they have no instance rows.

## overrides/

`data/overrides/{locations,resources,recipes}.json` are hand-maintained lists that the loader merges on top of the scraped data at every load:

- an entry whose `id` already exists patches only the listed fields;
- an entry with a new `id` is added as a complete entity;
- `null` means "not filled in yet" and is ignored.

Use them for data the wiki does not have, for example shelter and field footprints, or for content the wiki has not listed yet. They survive re-scraping. `load_data(..., apply_data_overrides=False)` loads the raw scraped data only.

`data/overrides/locations.json` holds the measured footprints, `movable` and `rotatable` values; it covers every location of the data (above level 56 partly estimates, see [docs/wiki-gaps.md](wiki-gaps.md)). [data/overrides/README.md](../data/overrides/README.md) explains how to measure footprints in the game and which edge is width and which is height.

## base_map.json

The measured farm geometry every player shares: `width`, `height`, `fixed` (the buildings the game never moves), `expansions` (the plots, without `unlocked`) and the `buildable` / `blocked` zones. It is the base map of the map editor format, without any player data; `BaseMap` (`src/layout/farm_map.py`) rejects an `unlocked` flag and `design` zones. The player's part is the profile map (next section); the tools merge the two into one `FarmMap`.

The map editor (**Save base map**) or `python -m src migrate-map --base-output data/base_map.json` writes it, one line per fixed item, plot and zone.

## Profile map

`config/profile_map.json` (git-ignored; `config/profile_map.example.json` is committed) is one player's state on the base map:

```json
{
  "schema_version": 1,
  "background": {
    "image": "farm_background.png",
    "image_width": 1600,
    "image_height": 900,
    "origin_px": [800, 40],
    "x_axis_px": [12, 6],
    "y_axis_px": [-12, 6]
  },
  "unlocked": ["main_1", "main_2"],
  "zones": [{ "id": "garden", "kind": "design", "cells": [[30, 20, 4, 3]] }],
  "current": [{ "id": "field", "count": 24 }]
}
```

`unlocked` lists plot ids of the base map (an unknown id is an error; section `base` is always unlocked), `zones` only `design` zones (existing decoration), `current` the current farm as in the one-file map. The tools look for the farm map in this order: `config/profile_map.json` merged with `DATA_DIR/base_map.json`, the one-file `config/farm_map.json` (read as it is, with a warning to run `python -m src migrate-map`), `config/farm_map.example.json`. `--map` takes either format. `migrate-map` splits a one-file map, compares its geometry with `data/base_map.json` and moves the background path so it still points at the screenshot. The map editor reads and writes both files (and reads the one-file map).

## Farm profile

`config/farm_profile.json` (git-ignored) holds every player-side input of one farm:

```json
{
  "schema_version": 1,
  "name": "Main farm",
  "player": { "schema_version": 1, "level": 56 },
  "profile_map": { "schema_version": 1, "unlocked": ["main_1"] },
  "design": { "schema_version": 1, "gap": 1 },
  "planner": { "schema_version": 1, "production": {}, "combiner": {} },
  "templates": {
    "dairy_garden": { "schema_version": 1, "width": 6, "height": 5 }
  }
}
```

Each part has the content of its own file (player profile, profile map, `design.json`, `planner.json`, the design templates the design settings assign). `python -m src farm-profile` assembles one from the current files; `--farm-profile PATH` makes the tools read it instead of them. The farm map is the profile map merged with `DATA_DIR/base_map.json`.

## Data bundle

`python -m src bundle` writes `output/data_bundle.json`: one JSON object with `meta.json`, the entity files with the overrides merged, `level_limits.json`, `mastery_bonuses.json` and `base_map.json`:

```json
{
  "schema_version": 1,
  "meta": {},
  "locations": [],
  "resources": [],
  "recipes": [],
  "level_limits": {},
  "mastery_bonuses": [],
  "base_map": {}
}
```

It is generated, not committed; write it again after a re-scrape. `load_data(<bundle file>)` and `dataset_from_bundle(obj)` give the same `DataSet` as `load_data("data")`, and the Core API takes the bundle object as its data (the combined plan reads `meta.max_level` from it).

## schema_version

Every input JSON (player profile, `design.json`, `planner.json`, design templates, farm maps, base map, profile map, farm profile, data bundle) may carry `"schema_version": N` as its first key; the committed examples and the files the tools write have it. A file without it is version 1, the format of v1.6. On load, `src/schema.py` runs the migrations from the file's version to the current one and drops the key, so the outputs never contain it. A newer version than the tools know is an error asking to update the tools. A format change bumps `CURRENT[kind]` and registers one migration in `MIGRATIONS[kind]`, with a test. The `data/*.json` files themselves and the output files are not versioned.

## Timing and capacity fields

All durations are stored in seconds.  
`base_slots` (locations) is the slot count per copy at purchase (wiki infobox; lobster pool and duck salon from the overrides). `max_slots` is the maximum per copy where it differs from the default 9 (lobster pool, duck salon: 6). `max_in_barn` (resources) exists in the model but is not filled yet.  
`mastery_bonuses.json` holds one row per building and star level with the total production time reduction (`location_id`, `stars`, `time_reduction_percent`); only speed-ups are stored, not coin or XP bonuses.  
Player-specific progress (owned copies, mastery, slots, animals, barn / silo capacity) lives in the player profile, not in the shared data. `validate_player_config` (`src/config.py`) checks the profile against these fields: slots at most copies × `max_slots` (default 9), animals at most copies × `animal_capacity`. Game rules that apply to everyone (slot limits, mastery effects, costs) are documented in [docs/game-facts/](README.md).

## External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect layout decisions. The Production Planner skips these recipes (`plan.skipped_recipes` in `schedule.json`).
