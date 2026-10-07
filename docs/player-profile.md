# Player profile: analysis and schema

Status: the schema (option B) is implemented in `src/config.py` (`PlayerConfig`, `LocationProgress`, `validate_player_config`). `config/player.example.json` lists every configurable location. Default resolution and use by the planners follow in v0.7.

## Problem

Many values that the planners need are not tied to the player level. The player buys or upgrades them with coins or diamonds, or earns them through mastery. Two players at level 56 can have very different farms. The shared data (`data/*.json`, `level_limits.json`) can only give the level maximum or the base value. The actual state belongs to the player profile (`config/player.json`).

## Inventory of player-specific settings

| Setting                                             | Applies to                     | How it changes                         | Profile field                       | Default if missing                          | Needed by          |
| --------------------------------------------------- | ------------------------------ | -------------------------------------- | ----------------------------------- | ------------------------------------------- | ------------------ |
| Barn / silo capacity                                | storage                        | upgrade supplies                       | `barn_capacity`, `silo_capacity`    | none (must be given)                        | Production         |
| Owned copies                                        | multi-copy buildings, shelters | bought with coins, unlocked by level   | `owned`                             | `instances_at(level)` (all unlocked copies) | Layout, Production |
| Production slots                                    | production buildings           | diamonds, per copy                     | `slots` (sum over copies)           | base slots per copy (data needed)           | Production         |
| Mastery                                             | production buildings           | production hours, shared by all copies | `mastery_stars` / `workbench_level` | 0                                           | Production         |
| Animals                                             | chicken coop, cow pasture, …   | animals bought with coins              | `animals` (sum over shelters)       | all shelters full                           | Production         |
| Beehives                                            | beehive tree                   | grows with collected nectar (1-4)      | `beehives`                          | 1                                           | Production         |
| Lobster / duck slots                                | lobster pool, duck salon       | coins, 1 → 6                           | `slots`                             | 1                                           | Production         |
| Fields owned                                        | field                          | coins, granted by level                | `fields_owned`                      | the planner recommends                      | Layout, Production |
| Trees / bushes owned, per kind                      | apple tree, nectar bush, …     | coins                                  | `owned`                             | the planner recommends                      | Layout, Production |
| Fishing spots unlocked                              | fishing lake                   | expansion supplies (15 in total)       | `fishing_spots_unlocked`            | unknown                                     | Production (fish)  |
| Town hall / train station / service building levels | town                           | upgrades                               | (v0.8)                              | lowest level                                | Town layout (v0.8) |
| Mastery system                                      | whole farm                     | game rollout (stars → Workbench)       | `mastery_system`                    | `stars`                                     | Production         |

Dropped: **farm land expansions**. Players cannot reliably count cleared expansions afterwards. The usable farm area is handled by the layout planner instead: the player measures the map size and the fixed buildings into `config/farm_map.json`.

Out of scope: helpers (Tom, Rose, Ernest), boosters and events. They are temporary or optional and do not change the static plan.

### Storage decisions

- **Totals, not per copy.** `slots` and `animals` are summed over all copies (two feed mills with 6 slots each → `slots: 12`; three full coops → `animals: 18`). The planners only need the parallel capacity, and the player does not have to tell the copies apart.
- **Mastery per type.** The wiki states that mastery comes from production hours, and the copies of a building count together (e.g. the smelter "is very hard to master if you do not have five of them"). So there is one `mastery_stars` per building type.
- **`owned` only where it varies.** Most production buildings exist only once, so the example omits `owned` for them (default: 1 when unlocked). It is listed for multi-copy buildings, shelters, trees and bushes.
- **Optional counts that are hard to count.** Fields, trees and bushes may stay `null`. The planners then recommend a sensible number instead of requiring an exact inventory.

## What the wiki says (checked 2026-10-05)

| Fact                                                                                                           | Source page                              |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Machines start with 1-3 slots (infobox `slots`) and reach 9 per copy                                           | Production Buildings, Feed Mill, Smelter |
| Lobster pool and duck salon: 1 slot at start, up to 6, bought with coins; cannot be mastered, moved or rotated | Lobster Pool, Duck Salon                 |
| Mastery comes from production hours, shared by all copies of a building                                        | Smelter, Production Buildings            |
| Shelter capacity, e.g. a chicken coop holds up to 6 chickens                                                   | Chicken Coop, Animal Shelters            |
| Beehive tree: one per player, grows from 1 to 4 beehives (3 bees each) with collected nectar                   | Beehive Tree                             |
| Nectar bush: level 39, feeds the beehives; the further from the beehive tree, the slower the bees              | Nectar Bush                              |
| 15 fishing spots in total                                                                                      | Fishing Lake                             |

Not on the wiki or any official page: the player's own counts (owned copies, bought slots, animals, mastery progress). They are account data and need the profile.

## Ways to provide the profile

| Option                                          | Effort for the player | Accuracy                 | Feasibility now | Notes                                                                                                                                                                                                                                   |
| ----------------------------------------------- | --------------------- | ------------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Full manual profile                          | very high             | exact                    | yes             | 40+ locations × several fields. Too much to fill in at once, and it goes stale quickly.                                                                                                                                                 |
| B. Level defaults + sparse overrides            | low                   | good                     | yes             | Everything not listed is derived from the level and the base data. The player lists only what differs (e.g. bought slots).                                                                                                              |
| C. Presets on top of B (e.g. `free`, `spender`) | very low              | rough                    | yes             | A quick estimate. A preset sets typical slots and animals, and overrides still win.                                                                                                                                                     |
| D. Interactive wizard (CLI, later web form)     | low                   | exact for answered items | later           | Asks only about items unlocked at the player's level and writes the sparse file from option B.                                                                                                                                          |
| E. Automatic sync with the game account         | none                  | exact                    | no              | Supercell has no public API for Hay Day (official APIs exist only for Clash of Clans, Clash Royale and Brawl Stars). Reading the game client is against the terms of service. A screenshot / OCR import could be a v2.0+ research item. |

## Recommendation

1. **Now / v0.7: option B.** It is the smallest file that still gives exact results where the player cares.
2. **v1.0: option D** as the UX on top of B, so nobody has to edit JSON by hand.
3. **Option C** if testing shows that defaults are too far off for typical players.
4. **Option E** stays on the watch list for v2.0+, in case an official API appears.

## Schema (option B)

```json
{
  "level": 56,
  "mastery_system": "stars",
  "barn_capacity": 675,
  "silo_capacity": 750,
  "fields_owned": 84,
  "fishing_spots_unlocked": 8,
  "locations": {
    "chicken_coop": { "owned": 3, "animals": 18 },
    "feed_mill": { "owned": 2, "slots": 12, "mastery_stars": 1 },
    "dairy": { "slots": 8, "mastery_stars": 3 },
    "beehive_tree": { "beehives": 2 },
    "lobster_pool": { "slots": 3 },
    "nectar_bush": { "owned": null }
  }
}
```

Per-location fields, all optional:

| Field             | Meaning                                           | Default                                            |
| ----------------- | ------------------------------------------------- | -------------------------------------------------- |
| `owned`           | copies placed                                     | `instances_at(level)`; trees / bushes: recommended |
| `slots`           | slots unlocked, summed over all copies            | base slots × copies                                |
| `mastery_stars`   | 0-3 per building type (`mastery_system: "stars"`) | 0                                                  |
| `workbench_level` | per building type (`mastery_system: "workbench"`) | 0                                                  |
| `animals`         | animals in all shelters of the type               | copies × `animal_capacity`                         |
| `beehives`        | beehives on the beehive tree, 1-4                 | 1                                                  |

Validation rules (`validate_player_config`, logged as warnings by `python -m src.main`):

- Location ids must exist in the data, and the location must be unlocked at `level`.
- `owned` ≤ `instances_at(level)` where instance rows exist.
- `animals` ≤ copies × `animal_capacity` (copies = `owned`, or all unlocked copies).
- `animals` only on shelters with a known `animal_capacity`; `slots` not on fields, trees or bushes.
- `mastery_stars` only with `mastery_system: "stars"`, `workbench_level` only with `"workbench"`.
- `fields_owned` ≤ `fields_at(level)`.

Future database mapping (3NF): `player(level, mastery_system, barn_capacity, silo_capacity, fields_owned, fishing_spots_unlocked)` and `player_location(player_id, location_id, owned, slots, mastery_stars, workbench_level, animals, beehives)`.

## Shared data still needed for good defaults

- Base slots per building (wiki infobox `slots`; scraper extension in v0.7).
- Farm map size and free area: player-measured in `config/farm_map.json` with `tools/farm_map_editor.html` (v0.6); no shared default exists. Unlocked farm plots are marked there too, by wiki plot number.
