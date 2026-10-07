# Data sources

Where the project's data comes from, and which part is scraped, hand-maintained or player-specific.

## Hay Day Fandom wiki (scraped)

The scraper uses the MediaWiki API (`https://hayday.fandom.com/api.php`), not the HTML pages, which avoids Cloudflare challenges. Requests are throttled (`--delay`, default 0.5 s). Every page used is recorded with its revision timestamp in `data/meta.json`.

| Wiki source                                | API call                   | Parser                                                               | Produces                                                                                   |
| ------------------------------------------ | -------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `Goods_List`                               | parse (HTML)               | `parsers/resources.py`, `parsers/recipes.py`, `parsers/locations.py` | resources, recipes, growth / production / 3-star times, field / tree / bush / mine sources |
| `Production_Buildings_List`                | parse (HTML)               | `parsers/locations.py`                                               | production buildings, footprints, copies per level                                         |
| `Animal_Shelters`                          | parse (HTML)               | `parsers/locations.py`                                               | farm animal shelters, `animal_capacity`, copies per level                                  |
| `Experience_Levels/Levels_X-Y`             | allpages + parse (HTML)    | `parsers/level_limits.py`                                            | field grants per level (`level_limits.json`)                                               |
| `Category:Fishing_Lake_Buildings`          | categorymembers            | `parsers/locations.py`                                               | `area: fishing_lake`                                                                       |
| `Category:Trees_and_Bushes` + member pages | categorymembers + wikitext | `parsers/locations.py`                                               | trees / bushes without goods (nectar bush), level from the infobox                         |
| all pages above                            | query revisions            | `wiki_client.py`, `writer.py`                                        | `data/meta.json`                                                                           |

### Goods List columns

`Name | Level | Max. price | Time | XP | Needs | Source | Per boat crate`. The Time column holds `base ★★★ mastered` (e.g. `30 min ★★★ 25 min`) for processed goods and the growth / animal time for raw goods. "Instant" is stored as 0.

Animal products with a feed in the Needs column (`Egg`: `Chicken feed (1)`) also become **feeding recipes** at their shelter, with the animal time as `production_time_seconds` and no 3-star time. The lobster pool and duck salon rows name the caught animal (`Lobster`, `Duck`); one animal is caught with exactly one trap (wiki: Lobster_Tail, Duck_Feather), so `normalizer.NEED_ALIASES` maps them to `lobster_trap` / `duck_trap`. The fishing lake row names `lure` (any lure) and `fishing_spot`, which are not goods; the loader lists such external inputs in one INFO line and they never become graph nodes.

## Read but not scraped

Pages that were read by hand for the facts in `docs/game-facts/`: Production_Buildings, Feed_Mill, Smelter, Lobster_Pool, Duck_Salon, Chicken_Coop, Beehive_Tree, Nectar_Bush, Barn, Silo, Farm, Crops, Expansion, Fishing_Lake, Town, Update, Birthday_Balloon_Maker, Category:Town_Buildings, Category:Service_Buildings.

Candidates for future scraping: the infobox `slots` of every production building (base slots, v0.7), town and service buildings (v0.8).

## Hand-maintained

| What                                              | Where                           | How                                              |
| ------------------------------------------------- | ------------------------------- | ------------------------------------------------ |
| Footprints the wiki lacks, `movable`, `rotatable` | `data/overrides/locations.json` | measured in game, see `data/overrides/README.md` |
| Game rules (slots, mastery, costs, …)             | `docs/game-facts/*.md`          | from wiki pages and in-game observation          |
| Game versions and wiki gaps                       | `docs/game-updates.md`          | after every game update                          |

## Player-specific

`config/player.json` (or the committed example): level, mastery system, barn / silo, fields, fishing spots, and per-location slots, mastery, copies, animals, beehives. See [player-profile.md](player-profile.md).

`config/farm_map.json` (or the committed example): the usable farm size, the positions of the fixed buildings (farmhouse, barn, silo, mine, …), the calibrated farm screenshot and the farm plots with their unlocked state, measured by the player with `tools/farm_map_editor.html`. See the README section "Farm map".

## Not available

| Source                         | Status                                                                                     | Checked    |
| ------------------------------ | ------------------------------------------------------------------------------------------ | ---------- |
| Official Hay Day API           | none; Supercell offers official APIs only for Clash of Clans, Clash Royale and Brawl Stars | 2026-10-05 |
| Reading the game client        | against the terms of service; not used                                                     | 2026-10-05 |
| Third-party Hay Day data sites | e.g. an unofficial MCP server based on hayday.info exists; not used, not verified          | 2026-10-05 |
