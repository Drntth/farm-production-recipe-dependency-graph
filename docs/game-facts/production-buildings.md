# Production buildings

Rules about machines that the scraper does not read. Per-building values that the wiki lists in tables (unlock level, size, recipes, times) are scraped into `data/`.

## Slots

| Fact                                                        | Value                                              | Source                       | Checked    |
| ----------------------------------------------------------- | -------------------------------------------------- | ---------------------------- | ---------- |
| Starting slots per machine                                  | 1-3 (infobox `slots` on each page)                 | wiki:Production_Buildings    | 2026-10-05 |
| Maximum slots per machine copy                              | 9                                                  | wiki:Production_Buildings    | 2026-10-05 |
| Maximum slots, lobster pool and duck salon                  | 6                                                  | wiki:Production_Buildings    | 2026-10-05 |
| Extra slots are paid with                                   | diamonds; lobster pool and duck salon: coins       | wiki:Production_Buildings    | 2026-10-05 |
| Diamond cost of extra slots                                 | 6, 9, 12, … (+3 each)                              | wiki:Production_Buildings    | 2026-10-05 |
| Lure workbench and net maker slots are much more expensive  | 9th slot: 415 diamonds                             | wiki:Production_Buildings    | 2026-10-05 |
| Feed mill: starting slots                                   | 3; 4th costs 6 diamonds; full upgrade 81 diamonds  | wiki:Feed_Mill               | 2026-10-05 |
| Smelter: starting slots                                     | 1; 2nd costs 6 diamonds; full upgrade 132 diamonds | wiki:Smelter                 | 2026-10-05 |
| Slots are bought per copy                                   | each copy has its own slots                        | wiki:Feed_Mill, wiki:Smelter | 2026-10-05 |
| Finished products that can be stacked in front of a machine | 52                                                 | wiki:Production_Buildings    | 2026-10-05 |
| Queued products cannot be discarded or switched             | -                                                  | wiki:Production_Buildings    | 2026-10-05 |

## Mastery (3-star system)

| Fact                                            | Value                                                      | Source                             | Checked    |
| ----------------------------------------------- | ---------------------------------------------------------- | ---------------------------------- | ---------- |
| Mastery is earned by production hours           | stars at fixed hour targets, maximum 3                     | wiki:Production_Buildings          | 2026-10-05 |
| The final ★★★ level always speeds production up | about 15 % (e.g. 2 h → 1 h 42 min, 5 min → 4 min 15 s)     | wiki:Goods_List (times)            | 2026-10-05 |
| Copies of a building share their mastery hours  | e.g. smelter is "very hard to master" with fewer than five | wiki:Smelter                       | 2026-10-05 |
| Hours to master the feed mill                   | 6,840 h                                                    | wiki:Feed_Mill                     | 2026-10-05 |
| Hours to master the smelter                     | 8,110 h                                                    | wiki:Smelter                       | 2026-10-05 |
| Lobster pool and duck salon cannot be mastered  | -                                                          | wiki:Lobster_Pool, wiki:Duck_Salon | 2026-10-05 |
| Mastered machines get golden parts and a star   | visual only                                                | wiki:Feed_Mill                     | 2026-10-05 |

The 3-star production time of every recipe is scraped as `production_time_3star_seconds`.

## Building Mastery / Workbench (v1.72)

| Fact                                                   | Value                         | Source        | Checked    |
| ------------------------------------------------------ | ----------------------------- | ------------- | ---------- |
| Workbench screen to upgrade and level up all buildings | introduced 2026-08-10 (v1.72) | wiki:Update   | 2026-10-05 |
| Rolled out gradually, not available to all players     | -                             | wiki:Update   | 2026-10-05 |
| No wiki page with levels or bonuses yet                | -                             | wiki (search) | 2026-10-05 |
| Maintainer's account still uses the 3-star system      | -                             | in-game       | 2026-10-05 |

## Copies, cost and build time

| Fact                                      | Value                                                                              | Source                                       | Checked    |
| ----------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------- | ---------- |
| Most production buildings exist only once | 1 copy                                                                             | in-game, wiki:Production_Buildings_List      | 2026-10-05 |
| Feed mill copies                          | 2, unlocked at levels 2 and 12; 2nd costs 3,200                                    | wiki:Production_Buildings_List               | 2026-10-05 |
| Sugar mill copies                         | 2, unlocked at levels 7 and 76; 2nd costs 200,000                                  | wiki:Production_Buildings_List               | 2026-10-05 |
| Smelter copies                            | 5, all at level 24; 12,500 / 22,000 / 31,500 / 41,000 / 50,500 coins (+9,500 each) | wiki:Production_Buildings_List, wiki:Smelter | 2026-10-05 |
| Smelter build time                        | 18 h (or 42 diamonds), 21 XP                                                       | wiki:Smelter                                 | 2026-10-05 |
| Feed mill build time                      | 40 s (or 1 diamond), 4 XP                                                          | wiki:Feed_Mill                               | 2026-10-05 |
| Last production building in the list      | Milkshake Bar, level 124                                                           | wiki:Production_Buildings_List               | 2026-10-05 |

Build price, time, XP and size of every building are in the wiki table and partly scraped (`footprint_width` / `footprint_height`).

## Footprints and placement

| Fact                                           | Value                                               | Source                                      | Checked    |
| ---------------------------------------------- | --------------------------------------------------- | ------------------------------------------- | ---------- |
| Machine sizes are listed in the building table | e.g. dairy 4x4, feed mill 3x3, ice cream maker 3x2  | wiki:Production_Buildings_List              | 2026-10-05 |
| The mine is fixed                              | cannot be moved                                     | in-game                                     | 2026-10-05 |
| Fishing lake machines are fixed                | lure workbench, net maker, lobster pool, duck salon | in-game, wiki:Lobster_Pool, wiki:Duck_Salon | 2026-10-05 |
| The ice cream maker (3x2) can be rotated       | -                                                   | in-game                                     | 2026-10-05 |

## Seasonal machines

| Fact                                                                     | Value                                                 | Source                      | Checked    |
| ------------------------------------------------------------------------ | ----------------------------------------------------- | --------------------------- | ---------- |
| Birthday Balloon Maker is delivered for the anniversary, for free        | 2024-06-11, 2025-06-10, 2026-06-19; level 17, 2 slots | wiki:Birthday_Balloon_Maker | 2026-10-05 |
| Its products are boat-only, cannot be bought or sold, stored in the barn | -                                                     | wiki:Birthday_Balloon_Maker | 2026-10-05 |
| Not part of the planning data                                            | temporary                                             | project decision            | 2026-10-05 |
