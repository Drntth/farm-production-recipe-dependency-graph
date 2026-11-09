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
4. **Quantities** (`quantities.py`): a linear program (scipy, HiGHS) over the rates per hour. Fields, animals and trees are only served at a login, so a cycle lasts until the first login after it ends (with even gaps: the growth time rounded up to whole gaps; with a night gap: the best repeating loop of logins, an optimistic estimate that assumes the player restarts each line at its best login). Machines keep running through their queue; with uneven gaps a machine's queue limits each kind of gap on its own, so in the long night gap it stops once its queue is done. The goods made in any gap between two logins must fit into `storage_share` of the barn and silo (default 50 %, the rest is stock). Four solves, each keeping the previous result:
   1. every good gets the same spare amount per hour (`balance`);
   2. goods without a production model (ores from the mine, fish) are used only as much as that balance needs, because their supply is unknown;
   3. idle machines and animals are filled (maximum production hours);
   4. the fewest fields and recommended trees / bushes for that plan.
5. **Schedule** (`schedule.py`): the logins of a day are spread evenly over the login window (`production.login_window`, default 07:00-23:00); the night until the next start is one long gap. The plan is solved for 1, 2, 3, 4, 5, 6, 8, 10, 12, 16 and 24 logins a day; more logins always produce more (busy hours grow almost linearly), so the suggestion looks only at up to 8 logins: the fewest that keep 80 % of the best production time among them (`min_efficiency`), or `login_window.logins` fixes the number (both in [`config/planner.json`](../settings.md)). For that number it gives the login times, the day and night gap, and the **last login**: the planned items longer than a day gap, longest first (at most 10), worth starting at the last login of the day so they finish during the night. It also lists:
   - **recommendations**: fields (available, owned, used by the plan; without an owned count every granted field is recommended, since a field costs 1 coin), trees and bushes, and the feeder bushes to plant per day: nectar bushes for the beehive trees (5 honeycomb per bush) and peanut bushes for the squirrel houses (2000 pods per bush, 300 per peanut);
   - **actions of every login**: collect → feed animals → plant fields → fill the machine queues, upstream machines first → sell or deliver the surplus (the 15 largest surplus goods).

   Counts per login come from the mean gap (24 h / logins), so with a night gap a login by day needs fewer and the last login of the day more; they are rounded, and an item made less than 0.5 times per login is given as "1 every N logins".
6. Writes `output/capacity.json`, `output/schedule.json` and `output/schedule.md`.

Recipes with inputs that are not goods (vouchers, diamonds, lures, fishing spots) are not planned; `schedule.json` lists them under `plan.skipped_recipes`.

## Outputs

- Recommended production quantities and ratios
- What to produce, how much, and in which order
- So that available space is well utilised and raw materials stay available for both further production and order fulfilment
- Suggested logins per day and their times in the player's login window, derived from crop growth times and machine processing times
- Ordered action sequences (plant → harvest → feed → process …)

Top-level keys of the files:

- `capacity.json`: `level`, `barn_capacity`, `silo_capacity`, `fields`, `fields_source`, `locations`, `recipes`, `crops`, `fruits`, `hives`.
- `schedule.json`: `level`, `logins_per_day`, `logins_suggested`, `login_times` (`HH:MM`), `day_gap_hours`, `night_gap_hours`, `last_login` (`time` and `items` with `hours`; `null` without a night gap), `storage`, `login_options` (every candidate number of logins with its longest gap and result), `recommendations`, `actions_per_login`, `external_per_day`, `warnings`, `plan` (the solved rates, utilization, surplus and `skipped_recipes`) and `settings` (the `production` settings used: `login_window`, `storage_share`, `min_efficiency`).

## Machine mastery

Mastery modifies production times, so it is modelled as a pluggable modifier chosen by `mastery_system` in the player config:

- `stars` (default): the classic 3-star mastery. The data holds both the base time and the full-mastery time of every recipe (`production_time_3star_seconds`). At three stars the planner uses that time; below three it applies the building's speed-up from `data/mastery_bonuses.json` (the feed mill, lure workbench and net maker are 5 % / 10 % faster at one / two stars, other machines only get coin and XP bonuses there).
- `workbench`: Building Mastery / Workbench, introduced in game version 1.72 (August 2026) with a gradual rollout. Its bonuses are not known yet, so the planner uses the base times and logs a warning.
