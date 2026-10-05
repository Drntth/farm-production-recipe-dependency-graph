# Animals and shelters

Shelter unlock levels and capacities are scraped into `data/` (`animal_capacity`, `level_limits.json`). This file keeps the rules and the special buildings.

## Farm animal shelters

| Fact                    | Value                                                                          | Source                                  | Checked    |
| ----------------------- | ------------------------------------------------------------------------------ | --------------------------------------- | ---------- |
| Chicken coop            | 6 chickens each; 3 coops at levels 1, 12, 23; 5 coins each                     | wiki:Animal_Shelters, wiki:Chicken_Coop | 2026-10-05 |
| Cow pasture             | 5 cows each; 3 at levels 6, 15, 27                                             | wiki:Animal_Shelters                    | 2026-10-05 |
| Pig pen                 | 5 pigs each; 3 at levels 10, 18, 32                                            | wiki:Animal_Shelters                    | 2026-10-05 |
| Sheep pasture           | 5 sheep each; 3 at levels 16, 26, 42                                           | wiki:Animal_Shelters                    | 2026-10-05 |
| Lamb pasture            | 5 lambs each; 2 at levels 25, 30                                               | wiki:Animal_Shelters                    | 2026-10-05 |
| Goat yard               | 4 goats each; 3 at levels 32, 37, 50                                           | wiki:Animal_Shelters                    | 2026-10-05 |
| Beehive tree            | 1-4 beehives; level 39; can be mastered                                        | wiki:Animal_Shelters                    | 2026-10-05 |
| Squirrel house          | 1-4 squirrels; level 62; can be mastered                                       | wiki:Animal_Shelters                    | 2026-10-05 |
| Pet shelters            | dog, bird, cat, horse, bunny, alpaca, puppy, donkey, kitten, guinea pig houses | wiki:Animal_Shelters                    | 2026-10-05 |
| Pets are not production | excluded from the data                                                         | project decision                        | 2026-10-05 |

## Shelter footprints (measured)

| Fact          | Value | Source  | Checked    |
| ------------- | ----- | ------- | ---------- |
| Chicken coop  | 3x3   | in-game | 2026-10-05 |
| Cow pasture   | 4x4   | in-game | 2026-10-05 |
| Pig pen       | 4x4   | in-game | 2026-10-05 |
| Sheep pasture | 4x4   | in-game | 2026-10-05 |
| Lamb pasture  | 4x4   | in-game | 2026-10-05 |
| Goat yard     | 3x3   | in-game | 2026-10-05 |
| Beehive tree  | 2x2   | in-game | 2026-10-05 |

The values are stored in `data/overrides/locations.json`.

## Beehive tree and nectar bush

| Fact                                                                | Value                                                                          | Source            | Checked    |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------- | ---------- |
| One beehive tree per player                                         | costs 4,000 coins                                                              | wiki:Beehive_Tree | 2026-10-05 |
| Beehives on the tree                                                | 1 at start, up to 4; 3 bees each (12 bees)                                     | wiki:Beehive_Tree | 2026-10-05 |
| The tree grows a beehive after collected nectar                     | 4,000 / 40,000 / 400,000 drops                                                 | wiki:Beehive_Tree | 2026-10-05 |
| Beehive count follows the mastery stars on the maintainer's account | 2 beehives now                                                                 | in-game           | 2026-10-05 |
| Honeycomb is produced                                               | per 100 drops of nectar, about 35 min if bushes are close                      | wiki:Beehive_Tree | 2026-10-05 |
| Nectar bush unlock and price                                        | level 39, 120 coins                                                            | wiki:Nectar_Bush  | 2026-10-05 |
| Nectar per bush                                                     | 500 drops in 2 harvests of 250; no growth cycle                                | wiki:Nectar_Bush  | 2026-10-05 |
| An empty bush wilts                                                 | another player can revive it for one final 250-drop harvest (helper gets 8 XP) | wiki:Nectar_Bush  | 2026-10-05 |
| Nectar is not stored by the player                                  | goes straight into the beehives                                                | wiki:Nectar_Bush  | 2026-10-05 |
| Distance between bush and beehive tree                              | farther = slower bees while online; no effect offline                          | wiki:Nectar_Bush  | 2026-10-05 |
| Nectar bush footprint                                               | 1x1                                                                            | in-game           | 2026-10-05 |

Layout consequence: nectar bushes belong next to the beehive tree (v0.6 support relation).

## Lobster pool and duck salon (fishing lake)

| Fact                                 | Value                                                               | Source                             | Checked    |
| ------------------------------------ | ------------------------------------------------------------------- | ---------------------------------- | ---------- |
| Lobster pool unlock and repair       | level 44; 80,000 coins, 2 days (or 65 diamonds), 32 XP              | wiki:Lobster_Pool                  | 2026-10-05 |
| Duck salon unlock and repair         | level 50; 90,000 coins, 2 d 5 h (or 68 diamonds), 34 XP             | wiki:Duck_Salon                    | 2026-10-05 |
| Seats (slots) at start               | 1, up to 6                                                          | wiki:Lobster_Pool, wiki:Duck_Salon | 2026-10-05 |
| Slot cost, lobster pool (ambiguous)  | text says coins; table shows 35, 37, 40, 42, 44 with a diamond icon | wiki:Lobster_Pool                  | 2026-10-05 |
| Slot cost, duck salon (ambiguous)    | text says coins; table shows 37, 40, 42, 44, 46 with a diamond icon | wiki:Duck_Salon                    | 2026-10-05 |
| Cannot be moved, rotated or mastered | -                                                                   | wiki:Lobster_Pool, wiki:Duck_Salon | 2026-10-05 |
| Catching a lobster                   | 6 h; at most 6 tails per 12 h with steady traps                     | wiki:Lobster_Pool                  | 2026-10-05 |
| Catching a duck                      | 2 h; at most 6 feathers per 5 h with steady traps                   | wiki:Duck_Salon                    | 2026-10-05 |
| Maintainer's slots                   | lobster pool 3, duck salon 1                                        | in-game                            | 2026-10-05 |
