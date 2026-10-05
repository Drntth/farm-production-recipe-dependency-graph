# Documentation

Project knowledge that is not code and not scraped data. Read these before researching the game again: most answers are already here.

## Index

| File                                                                     | Content                                                                                   |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| [game-facts/production-buildings.md](game-facts/production-buildings.md) | slots, mastery, copies, build cost and time, footprints of machines                       |
| [game-facts/animals.md](game-facts/animals.md)                           | animal shelters, capacities, beehive tree, nectar bush, lobster pool, duck salon          |
| [game-facts/farm.md](game-facts/farm.md)                                 | fields, trees, bushes, farm buildings, layout edit mode, measured footprints              |
| [game-facts/storage.md](game-facts/storage.md)                           | barn and silo capacity and upgrades                                                       |
| [game-facts/fishing-lake.md](game-facts/fishing-lake.md)                 | fishing lake area, buildings, spots                                                       |
| [game-facts/town.md](game-facts/town.md)                                 | town area, town hall, service buildings, sanctuary                                        |
| [game-updates.md](game-updates.md)                                       | game versions, what changed, update checklist, known wiki gaps                            |
| [data-sources.md](data-sources.md)                                       | which wiki pages and categories the scraper reads, what is scraped vs. manual vs. profile |
| [player-profile.md](player-profile.md)                                   | player-specific settings, input options, profile schema                                   |

## Where knowledge lives

| Kind of knowledge                               | Place                                   | Maintained by          |
| ----------------------------------------------- | --------------------------------------- | ---------------------- |
| Per-entity data the wiki lists in tables        | `data/*.json`, `data/level_limits.json` | scraper                |
| Per-entity data the wiki lacks (footprints, …)  | `data/overrides/*.json`                 | hand, measured in game |
| Game rules (min / max values, mechanics, costs) | `docs/game-facts/*.md`                  | hand, from wiki / game |
| One player's farm state                         | `config/player.json`                    | the player             |

Rules are kept in Markdown, not in the data files, until code needs them. When a planner starts using a rule (e.g. the maximum of 9 slots), move the value into data or code and keep the fact row here as its source.

## Fact table format

Every file in `game-facts/` uses the same table, so that a future checker script can verify the rows automatically (see the roadmap):

```text
| Fact | Value | Source | Checked |
```

- **Fact**: one statement, short.
- **Value**: the exact value as stated by the source (numbers, levels, costs).
- **Source**: `wiki:<Page_Name>` for the Hay Day Fandom wiki, `in-game` for the maintainer's own observation, `web:<site>` for other pages.
- **Checked**: the date the row was last confirmed (YYYY-MM-DD).

Do not invent values. If a source is ambiguous, say so in the Fact column and keep both readings.
