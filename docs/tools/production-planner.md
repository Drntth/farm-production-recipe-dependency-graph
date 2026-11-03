# Production Planner

How the Production Planner (`src/planner/`) turns the player profile into quantities and a login schedule. Settings: [settings.md](../settings.md).

## Production Planner purpose

Produce a sustainable production plan and a practical action/login schedule for the player's level, using only static data. Farm only.

## Inputs (static only)

- Player profile: level, mastery system, barn and silo capacity, and per location the slots, mastery, owned copies, animals and beehives (see [Player configuration](../player-profile.md))
- Growth and production times (`growth_time_seconds`, `production_time_seconds`, `production_time_3star_seconds`)
- Fields and building / shelter copies available at that level (`level_limits.json`), animals per shelter (`animal_capacity`)
- Game rules such as slot limits and mastery effects ([docs/game-facts/](../README.md))

Values missing from the profile are filled with level defaults. Fields, trees and bushes left empty get a recommended count.

Live truck, boat, town or event orders are intentionally ignored.

## How it works

`python -m src.planner` (package `src/planner/`, never imports `src.layout`):

1. **Profile** (`profile.py`, option B of [docs/player-profile.md](../player-profile.md)): every `null` gets its level default (all unlocked copies, base slots × copies, 0 stars, full shelters, 1 beehive). Fields, trees and bushes without a count are left to the plan.
2. **Mastery** (`mastery.py`, see [Machine mastery](#machine-mastery)): the player's production time of every recipe.
3. **Capacity** (`capacity.py`): barn and silo, fields, and per location what runs in parallel and what queues. A machine produces one item at a time, so copies run in parallel and slots only queue; every animal produces on its own; the lobster pool and duck salon run one animal per slot. A planted crop gives two, so one planting adds one crop net. A tree / bush gives `lifetime_yield` goods over `lifetime_harvests` harvests, and every beehive one honeycomb per cycle. Values the wiki lacks are estimates for now, listed with their basis in [docs/wiki-gaps.md](../wiki-gaps.md).
4. **Quantities** (`quantities.py`): a linear program (scipy, HiGHS) over the rates per hour. Fields, animals and trees are only served at a login, so their cycle is the growth time rounded up to whole login intervals; machines keep running through their queue. The goods made between two logins must fit into `storage_share` of the barn and silo (default 50 %, the rest is stock). Four solves, each keeping the previous result:
   1. every good gets the same spare amount per hour (`balance`);
   2. goods without a production model (ores from the mine, fish) are used only as much as that balance needs, because their supply is unknown;
   3. idle machines and animals are filled (maximum production hours);
   4. the fewest fields and recommended trees / bushes for that plan.
5. **Schedule** (`schedule.py`): the plan is solved for the login intervals 0.5, 1, 2, 3, 4, 6, 8 and 12 h; the suggested interval is the longest one that keeps 80 % of the best production time (`min_efficiency`), or `login_interval` fixes it (both in [`config/planner.json`](../settings.md)). For that interval it lists:
   - **recommendations**: fields (available, owned, used by the plan; without an owned count every granted field is recommended, since a field costs 1 coin), trees and bushes, and the feeder bushes to plant per day: nectar bushes for the beehive trees (5 honeycomb per bush) and peanut bushes for the squirrel houses (2000 pods per bush, 300 per peanut);
   - **actions of every login**: collect → feed animals → plant fields → fill the machine queues, upstream machines first → sell or deliver the surplus (the 15 largest surplus goods).

   Counts are rounded per login; an item made less than 0.5 times per login is given as "1 every N logins".
6. Writes `output/capacity.json`, `output/schedule.json` and `output/schedule.md`.

Recipes with inputs that are not goods (vouchers, diamonds, lures, fishing spots) are not planned; `schedule.json` lists them under `plan.skipped_recipes`.

## Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested login frequency derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

Top-level keys of the files:

- `capacity.json`: `level`, `barn_capacity`, `silo_capacity`, `fields`, `fields_source`, `locations`, `recipes`, `crops`, `fruits`, `hives`.
- `schedule.json`: `level`, `login_interval_hours`, `logins_per_day`, `storage`, `intervals` (every candidate interval with its result), `recommendations`, `actions_per_login`, `external_per_day`, `warnings`, `plan` (the solved rates, utilization, surplus and `skipped_recipes`) and `settings` (the `production` settings used: `login_interval`, `storage_share`, `min_efficiency`).

## Machine mastery

Mastery modifies production times, so it is modelled as a pluggable modifier chosen by `mastery_system` in the player config:

- `stars` (default): the classic 3-star mastery. The data holds both the base time and the full-mastery time of every recipe (`production_time_3star_seconds`). At three stars the planner uses that time; below three it applies the building's speed-up from `data/mastery_bonuses.json` (the feed mill, lure workbench and net maker are 5 % / 10 % faster at one / two stars, other machines only get coin and XP bonuses there).
- `workbench`: Building Mastery / Workbench, introduced in game version 1.72 (August 2026) with a gradual rollout. Its bonuses are not known yet, so the planner uses the base times and logs a warning.
