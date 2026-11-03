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

## Timing and capacity fields

All durations are stored in seconds.  
`base_slots` (locations) is the slot count per copy at purchase (wiki infobox; lobster pool and duck salon from the overrides). `max_slots` is the maximum per copy where it differs from the default 9 (lobster pool, duck salon: 6). `max_in_barn` (resources) exists in the model but is not filled yet.  
`mastery_bonuses.json` holds one row per building and star level with the total production time reduction (`location_id`, `stars`, `time_reduction_percent`); only speed-ups are stored, not coin or XP bonuses.  
Player-specific progress (owned copies, mastery, slots, animals, barn / silo capacity) lives in the player profile, not in the shared data. `validate_player_config` (`src/config.py`) checks the profile against these fields: slots at most copies × `max_slots` (default 9), animals at most copies × `animal_capacity`. Game rules that apply to everyone (slot limits, mastery effects, costs) are documented in [docs/game-facts/](README.md).

## External resources

Recipe inputs that represent external dependencies (vouchers, premium materials) are permitted in recipes but are omitted from the graph because they do not affect layout decisions. The Production Planner skips these recipes (`plan.skipped_recipes` in `schedule.json`).
