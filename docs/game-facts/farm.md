# Farm

## Fields

| Fact                         | Value                                                                                                      | Source                             | Checked    |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------- |
| Fields at level 1            | 6                                                                                                          | wiki:Experience_Levels/Levels_1-25 | 2026-10-05 |
| New fields per level         | every other level: 3 until level 49, 2 until 99, then 1                                                    | wiki:Farm                          | 2026-10-05 |
| Fields available at level 56 | 84 (computed from the grants)                                                                              | data/level_limits.json             | 2026-10-05 |
| Field price                  | 1 coin each; planting crops is free                                                                        | wiki:Crops                         | 2026-10-05 |
| Field limit                  | wiki: "There is no limit to how many fields you can have" (conflicts with the per-level grants; to verify) | wiki:Farm                          | 2026-10-05 |
| Field footprint              | 1x1                                                                                                        | in-game                            | 2026-10-05 |

## Trees and bushes

| Fact                                    | Value                                                                                                                          | Source                            | Checked    |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- | ---------- |
| Trees and bushes are bought in the shop | 160-910 coins per unit                                                                                                         | wiki:Crops                        | 2026-10-05 |
| Every kind is a separate item           | own fruit, own size                                                                                                            | wiki:Category:Trees_and_Bushes    | 2026-10-05 |
| Kinds up to level 56                    | apple, cherry, cacao tree; raspberry, blackberry, blueberry, coffee, nectar bush                                               | wiki:Goods_List, wiki:Nectar_Bush | 2026-10-05 |
| Kinds above level 56                    | olive 57, peanut bush 62, lemon 66, orange 71, peach 76, banana 88, plum 94, mango 97, coconut 101, guava 104, pomegranate 107 | wiki:Goods_List                   | 2026-10-05 |
| Tree footprints                         | apple, cherry, cacao: 1x1                                                                                                      | in-game                           | 2026-10-05 |
| Bush footprints                         | raspberry, blackberry: 1x2; blueberry, coffee, nectar: 1x1                                                                     | in-game                           | 2026-10-05 |
| Rotation                                | wiki: "Both can be rotated" (ambiguous); raspberry and blackberry bushes rotate in game                                        | wiki:Farm, in-game                | 2026-10-05 |
| The nectar bush produces no goods       | feeds the beehive tree (see animals.md)                                                                                        | wiki:Nectar_Bush                  | 2026-10-05 |

## Farm buildings (not production)

| Fact                       | Value                                                                                                                                                                                                                                                                      | Source            | Checked    |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | ---------- |
| Main buildings on the farm | farmhouse, mailbox, newspaper mailbox, roadside shop, truck, riverboat, Wheel of Fortune truck, silo, barn, mine, Maggie's workbench (customisation), helpers' house, event board, neighborhood house, derby stand, leaderboard, fishing boat, train station, valley board | wiki:Farm         | 2026-10-05 |
| First decoration           | level 8 (wiki: "tbc")                                                                                                                                                                                                                                                      | wiki:Farm         | 2026-10-05 |
| Fishing boat repair        | unlocks the fishing lake (see fishing-lake.md)                                                                                                                                                                                                                             | wiki:Fishing_Lake | 2026-10-05 |
| Train station repair       | unlocks the town (see town.md)                                                                                                                                                                                                                                             | wiki:Town         | 2026-10-05 |
| More fixed items on the farm | neighborhood requests, farm pass, decoration collection, decorate event, Tom's box | in-game | 2026-10-09 |
| Barn and silo | can be moved in Layout Edit Mode (not fixed) | in-game | 2026-10-09 |

These buildings are not in `data/`. Their footprints and positions differ per farm, so the player measures them into `config/farm_map.json` (the example lists their ids with empty positions); the layout planner treats them as fixed obstacles. The barn and silo can be moved: they are storage locations in `data/overrides/locations.json`, and the planner places them as the Storage block. Marking them in `config/farm_map.json` is optional and keeps them where they are. Mark every tile an item blocks (e.g. the truck together with its order board).

## Placing and measuring

| Fact                                         | Value                                                | Source  | Checked    |
| -------------------------------------------- | ---------------------------------------------------- | ------- | ---------- |
| Layout Edit Mode shows no tile grid          | -                                                    | in-game | 2026-10-05 |
| Layout Edit Mode unlock                      | level 37 (farm), level 34 (town)                     | wiki:Edit_Mode | 2026-10-05 |
| Layout slots                                 | 2 per area at start; extra slots 20 / 40 / 80 diamonds | wiki:Edit_Mode | 2026-10-05 |
| A new layout starts empty                    | every movable item is stored; only fixed buildings remain | wiki:Edit_Mode | 2026-10-05 |
| A layout can be set active only if complete  | all production buildings, fields, shelters, trees and bushes placed | wiki:Edit_Mode | 2026-10-05 |
| Paintbrush tool                              | places fields, trees, bushes and decorations in rows | wiki:Edit_Mode | 2026-10-05 |
| The shop shows an item's size before placing | e.g. "3x3" for the chicken coop                      | in-game | 2026-10-05 |
| Measuring trick                              | 1x1 fields as a ruler; calibrated with the 4x4 dairy | in-game | 2026-10-05 |
| Width / height convention of this project    | width = ↘ edge, height = ↙ edge from the top corner  | project | 2026-10-05 |

## Expansion

| Fact                                          | Value                                                                            | Source         | Checked    |
| --------------------------------------------- | -------------------------------------------------------------------------------- | -------------- | ---------- |
| Farm expansion available from                 | level 22                                                                         | wiki:Expansion | 2026-10-05 |
| Locked land is opened with expansion supplies | land deed, mallet, marker stake (map pieces: town only)                          | wiki:Expansion | 2026-10-05 |
| Special farm section                          | needs expansion permits (Wheel of Fortune, derby, valley shop, level thresholds) | wiki:Expansion | 2026-10-05 |
| Town expansion available from                 | reputation level 3                                                               | wiki:Expansion | 2026-10-05 |
| Number of cleared expansions                  | hard to count afterwards; not in the profile                                     | in-game        | 2026-10-05 |
| Expansion locations                           | main section beside the farmhouse; second section across the main road (with special plots) | wiki:Expansion/Farm | 2026-10-05 |
| Main section plots                            | 52 (plus 13 upper plots since summer 2021); each needs N deeds = N mallets = N stakes, 5-40 per plot | wiki:Expansion/Farm | 2026-10-05 |
| Second section plots | two wiki maps, each numbered #1-#9: "Farm Expansions 2" (April 2015, 239 of each tool in total) and "Farm Expansions 3" (December 2018, 355 in total); the editor uses sections `second` and `second_2018` | wiki:Expansion/Farm | 2026-10-09 |
| Special and later plots | wiki maps: "Farm Expansions Special" (March 2017, section `special`); special plots of December 2018 unlocked with expansion permits and LEMs (169 and 609 in total, section `special_2018`; its map labels plots with pairs such as "10/33", probably permits / LEMs per plot (unverified), not plot numbers, so the editor numbers them top to bottom, left to right); "Hay Day Lower plots" #1-#24 (October 2019) and #25-#41 (summer 2021, section `lower`); "Farm expansion Spring 2023" next to the left side of the second section (section `spring_2023`) | wiki:Expansion/Farm | 2026-10-09 |
| Plots missing from the wiki | 3 rows of unlockable plots along the top and the bottom edge of the farm, with no wiki map; the editor puts them in section `other`, numbered top to bottom, left to right | in-game | 2026-10-09 |
| Unlock order                                  | from the top; a cleared plot makes its neighbours unlockable                     | wiki:Expansion/Farm | 2026-10-05 |
| Plot maps on the wiki                         | isometric images with plot numbers, no tile grid, no tile sizes                  | wiki:Expansion/Farm | 2026-10-05 |
| Farm overview image on the wiki               | 2015 screenshot of the central area only, not to scale                           | wiki:Farm      | 2026-10-05 |
