# Game updates

Hay Day changes regularly. This file records what is known about recent versions and how to bring the project up to date after an update.

## Process after a game update

1. Read the update notes: [Fandom Update page](https://hayday.fandom.com/wiki/Update) and the official in-game / Supercell announcements.
2. Compare them with `data/meta.json`: game version and wiki revision dates.
3. Work through the table below for every changed mechanic.
4. Re-scrape: `python -m src.scraper --game-version <version>`. Run `python -m pytest` and `python -m src.main`.
5. Fill in values the wiki does not have in `data/overrides/` and new rules in `docs/game-facts/`.
6. Add the version to "Known versions" below.

## Mechanic → affected part

| Game change                                 | What to update                                                                                        |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| New building, good, crop, tree or animal    | scraper parsers, normalizer, re-scrape, quality tests, footprint in overrides, player example config  |
| Changed unlock levels or new level cap      | re-scrape, player config                                                                              |
| Mastery system (3 stars ↔ Workbench)        | planner mastery modifier, `mastery_system` in the player config, `game-facts/production-buildings.md` |
| Production / growth times, machine slots    | timing fields, `game-facts/production-buildings.md`, Production Planner                               |
| Fields per level, building / shelter copies | `level_limits.json` (scraper: Experience Levels, building lists)                                      |
| Barn / silo capacity, upgrade tables        | player config, `game-facts/storage.md`, capacity model                                                |
| Building sizes, rotation, fixed buildings   | `data/overrides/locations.json`, Layout Planner                                                       |
| Expansion, map size                         | `game-facts/farm.md`, Layout Planner                                                                  |
| Town, sanctuary, fishing lake               | area modes (`--area`), `game-facts/town.md`, `game-facts/fishing-lake.md`                             |
| Decorations, paths                          | Design layer                                                                                          |
| Wiki lags behind the game                   | `data/overrides/`, `known_game_version` in `meta.json`, "Known wiki gaps" below                       |

## Known versions

| Version | Date       | Changes relevant to the project                                                                                            | Source                                   |
| ------- | ---------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 1.72    | 2026-08-10 | Building Mastery / Workbench (gradual rollout, replaces the 3-star mastery); Boat Destinations; queue several truck orders | wiki:Update                              |
| 1.71    | 2026-06    | 14th anniversary; beach area by the sanctuary for decorations; Birthday Balloon Maker delivered again (2026-06-19)         | wiki:Update, wiki:Birthday_Balloon_Maker |
| Spring  | 2026       | quality-of-life changes; crops, axes and saws can be bought with coins                                                     | web:vortexgaming.io                      |

Data in the repository was scraped for game version 1.72 at level 56 (see `data/meta.json`).

## Known wiki gaps

| Gap                                                                             | Handling                                    | Checked    |
| ------------------------------------------------------------------------------- | ------------------------------------------- | ---------- |
| No page for Building Mastery / Workbench                                        | data has 3-star times only                  | 2026-10-05 |
| No footprints for shelters, fields, trees, bushes                               | measured in game, `data/overrides/`         | 2026-10-05 |
| Rotation of trees and bushes is ambiguous ("Both can be rotated")               | `rotatable` in `data/overrides/`, from game | 2026-10-05 |
| Lobster pool / duck salon slot cost: text says coins, table shows diamond icons | noted in `game-facts/animals.md`            | 2026-10-05 |
| "No limit" on fields vs. per-level field grants                                 | noted in `game-facts/farm.md`               | 2026-10-05 |

## Corrections of earlier assumptions

- The "Balloon Maker" of 1.71 is the seasonal Birthday Balloon Maker, which is on the wiki. It is not part of the planning data.
- The "Kebab Machine" is the existing Döner Kebab Stand (level 32), which is already in the data.
