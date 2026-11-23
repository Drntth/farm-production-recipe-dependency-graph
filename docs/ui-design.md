# UI design rules

Interface rules for the web app (`web/`), set in v2.5. Every page and form follows them; a change of a rule is a decision in [v2-design.md](v2-design.md). Terms (input rule, profile check, concept icon, item drawing, export reminder) are defined in [CONTEXT.md](../CONTEXT.md). Sources are listed at the end; a rule without a source is a project decision.

## Users and devices

| Point     | Rule                                                                                                                                              |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Who       | Hay Day players: first the owner, later the public (v3)                                                                                           |
| Where     | on the phone or the tablet, often while playing; desktop second                                                                                   |
| Input     | touch first; every control also works with a mouse and the keyboard                                                                               |
| Main jobs | look at a level recommendation (layout, plan); fill in a farm profile and plan it; later edit the layout                                          |
| Look      | the portfolio stack, the summer farm palette, Fredoka + Nunito (Hungarian headings in Nunito), light and dark theme, English and Hungarian (v2.2) |

## Input rules

One rule per profile field. Empty (`null`) always means "level default" or "the planner decides", never an error.

| Kind         | When                           | Control                                                                  |
| ------------ | ------------------------------ | ------------------------------------------------------------------------ |
| Dropdown     | 5-10 valid values, all known   | `<select>`; first entry "level default (X)" or "recommended" (`null`)    |
| Button row   | 2-4 valid values               | one toggle button per value (one radio group), plus "level default"      |
| Whole number | many valid values in a range   | `<input type="number" inputmode="numeric">` with `min`, `max` and `step` |
| Time         | the login window start and end | `<input type="time">` (unchanged)                                        |

| Field               | Valid values                               | Control                   |
| ------------------- | ------------------------------------------ | ------------------------- |
| level               | 1 … the highest level in the data          | whole number              |
| copies (`owned`)    | 0 … the level's copy limit                 | dropdown                  |
| slots               | 1-9; lobster pool and duck salon 1-6       | dropdown                  |
| mastery stars       | 0-3                                        | button row (★)            |
| beehives            | 1-4                                        | button row                |
| fishing spots       | 0-15                                       | whole number              |
| logins per day      | 1-24                                       | whole number              |
| barn, silo capacity | empty (no limit) or 50-1500 in steps of 25 | whole number, `step="25"` |
| fields owned        | 0 … the level's field count                | whole number              |
| animals             | 0 … `animal_capacity` × copies             | whole number              |

Bounds come from the data (`level_limits.json`, `animal_capacity`) and the game facts ([production-buildings.md](game-facts/production-buildings.md), [storage.md](game-facts/storage.md), [fishing-lake.md](game-facts/fishing-lake.md), [animals.md](game-facts/animals.md)), never from a constant in the component. No test depends on the number of levels (the CI builds levels 1, 20 and 40).

## Validation and error messages

- One **profile check** (`web/src/profiles/`) for the form, the import and a stored profile.
- An **invalid value** is never stored and never clamped. The typed text stays in the field.
- When: after the player leaves the field (`change` / blur), not while typing.
- At the field: a red border, `aria-invalid="true"`, and a short message under the field linked with `aria-describedby`. The message says how to fix it.
- At the top of the form: a summary (`role="alert"`) as soon as one field is invalid: "N fields are invalid" and one link per field. A link opens the closed group (`<details>`) and moves the focus to the field.
- Calculate is disabled while a field is invalid; the summary says why.
- Import: a file with an invalid value is refused; the message lists location, field, value and the valid range. Nothing is stored.
- Stored profile with an invalid value (an older version, edited by hand): loaded, the fields marked as above, not planned until fixed.
- The schema version check stays first; it only checks the file format.

Message templates (both languages in `web/content/*.json`, same keys):

| Key           | English                               | Hungarian                              |
| ------------- | ------------------------------------- | -------------------------------------- |
| `wholeNumber` | Enter a whole number                  | Egész számot adj meg                   |
| `range`       | Between {min} and {max}               | {min} és {max} között                  |
| `max`         | At most {max} at level {level}        | Legfeljebb {max} a(z) {level}. szinten |
| `step`        | In steps of {step} ({min}, {next}, …) | {step}-esével ({min}, {next}, …)       |
| `summary`     | {n} fields are invalid                | {n} mező hibás                         |

## Concept icons and legend

- A **concept icon** is a Lucide icon (`@iconify-json/lucide`, already a dev dependency) for an idea, never for a game object.
- In Svelte islands a small `Icon.svelte` takes only the icons used from the icon data; no new package.
- Always icon plus a short visible keyword (1-2 words). The full name is the accessible name; the visible keyword is part of it (Label in Name).
- With a pointer (`@media (hover: hover)`) a tooltip shows the full name and a short explanation. On touch there is no tooltip, so nothing needed is only in a tooltip.
- Each form has a **legend**: a closed `<details>` at the top listing the icons and what an empty field means. It replaces the long hint paragraph.

| Concept               | Lucide icon           |
| --------------------- | --------------------- |
| copies                | `copy`                |
| slots                 | `list-ordered`        |
| mastery star          | `star`                |
| animals               | `paw-print`           |
| fields                | `wheat`               |
| fishing spots         | `fishing-hook`        |
| logins per day        | `log-in`              |
| login window          | `alarm-clock`         |
| export (save to file) | `download`            |
| import                | `upload`              |
| last export           | `hard-drive-download` |
| invalid value         | `circle-alert`        |
| warning, reminder     | `triangle-alert`      |
| loading               | `loader-circle`       |
| more information      | `info`                |

Checked in `@iconify-json/lucide` 1.2.147 (2026-11-23): every name above exists. Lucide has no `silo` and no `barn`; barn and silo are game objects anyway and get item drawings.

## Item drawings

- An **item drawing** is an own-made SVG that looks like the in-game object, so the player recognises it. Never a game screenshot, a game asset or a trace of one (Supercell Fan Content Policy).
- Style: flat fills, a thick dark outline (2 px at 24 px), 2-3 fills from the site palette (`--wood`, `--soil`, `--grass`, `--wheat`, `--sky`, `--water`, `--accent`, `--gold`), a slight three-quarter view like the game, `viewBox="0 0 24 24"`, readable at 24 px and 48 px, on the light and the dark theme.
- Files: `web/src/assets/items/<id>.svg`, named by the data `id` (the fishing spot, a profile field and no location, is `fishing_spot.svg`); written by hand, no embedded raster, no text.
- Where a drawing is missing: a neutral **placeholder drawing** and the game item name.
- Tests: every drawing is valid SVG with the 24 × 24 viewBox; a missing one falls back to the placeholder.

First round (v2.5): what the farm profile form shows up to level 40, plus barn, silo and fishing spot (28):

| Unlock level  | Drawings                                                                                                                      |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 1-10          | `chicken_coop`, `field`, `feed_mill`, `bakery`, `cow_pasture`, `dairy`, `sugar_mill`, `popcorn_pot`, `bbq_grill`, `pig_pen`   |
| 11-25         | `pie_oven`, `sheep_pasture`, `loom`, `sewing_machine`, `cake_oven`, `smelter`, `lamb_pasture`                                 |
| 26-40         | `juice_press`, `ice_cream_maker`, `doner_kebab_stand`, `goat_yard`, `jam_maker`, `jeweler`, `beehive_tree`, `honey_extractor` |
| storage, lake | `barn`, `silo`, `fishing_spot`                                                                                                |

Missing after v2.5: every other building, shelter, tree and bush, and all goods. They are added later, a few at a time; the list is the data minus `web/src/assets/items/`.

## Language

- Every text of the site is in English and Hungarian (`web/content/en.json`, `hu.json`, same keys).
- **Game item names** stay English on every page: the game has no Hungarian language ([farm.md](game-facts/farm.md)), so a Hungarian name would not match the game.
- `tests/language.spec.ts` checks that no English UI string is left on a `/hu/` page; game item names come from the data, not from `en.json`, so they do not trip it.

## Data safety

Farm profiles live in the browser (IndexedDB). The browser may delete them; only an exported file survives everything.

| Browser                            | What happens to stored data                                                                                                                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Safari, every iOS browser (WebKit) | script-written storage (IndexedDB too) is deleted after 7 days of Safari use without a visit to the site (since iOS 13.4 / Safari 13.1); home-screen web apps: probably exempt (unverified)                         |
| Safari 17+                         | `persist()` is granted by heuristics (for example a home-screen web app), without a prompt; whether a grant lifts the 7-day rule: unverified                                                                        |
| Chromium (Chrome, Brave Android)   | best-effort data is evicted under storage pressure, least recently used first; `persist()` is granted without a prompt by engagement, install, bookmark or notification permission; a persisted site is not evicted |
| Brave                              | "forget me when I close this site" (Forgetful Browsing; Shred in newer Android versions, unverified) deletes IndexedDB when the site is closed                                                                      |
| Firefox                            | `persist()` asks the user; a persisted site is not evicted                                                                                                                                                          |

Rules:

- `navigator.storage.persist()` is called once, after the first save (a player action); the result is kept silently.
- Every farm profile shows its **last export** ("Saved to a file 3 days ago" / "never").
- **Export reminder**: a notice (not a dialog) on the profile when it changed since the last export and that export is older than 7 days or missing; one button exports. The 7 days follow the Safari rule; it is a rule, not a setting.
- The export date is kept in IndexedDB beside the profile, not in the profile file (the file format and its schema version stay as they are).
- The Usage page names the export as the backup and the home-screen install on iOS as a help.

## Accessibility

Target: WCAG 2.2 level AA.

| Rule                                                                                       | Basis                     | Checked by                                        |
| ------------------------------------------------------------------------------------------ | ------------------------- | ------------------------------------------------- |
| Text contrast 4.5:1 (large text 3:1), both themes                                          | 1.4.3 (AA)                | axe                                               |
| Borders of controls, focus ring, icons that carry meaning 3:1                              | 1.4.11 (AA)               | axe (partly), review                              |
| Main controls (buttons, dropdowns, button rows, links in the menu) at least 44 × 44 CSS px | 2.5.5 (AAA), project rule | own Playwright test (phone)                       |
| Every other target at least 24 × 24 CSS px or spaced                                       | 2.5.8 (AA)                | own Playwright test (phone)                       |
| Every input has a visible label; the accessible name contains it                           | 3.3.2 (A), 2.5.3 (A)      | axe                                               |
| Errors named in text at the field, with how to fix them                                    | 3.3.1 (A), 3.3.3 (AA)     | Playwright (validation tests)                     |
| Text at 200% without loss; no sideways scroll at 320 CSS px                                | 1.4.4 (AA), 1.4.10 (AA)   | `profiles.spec.ts` (130%, 160%, 360 px), extended |
| Everything works with the keyboard; the focus is visible                                   | 2.1.1 (A), 2.4.7 (AA)     | review, axe (partly)                              |
| Motion off with `prefers-reduced-motion` (fade-ins, farm view transitions)                 | 2.3.3 (AAA), project rule | own Playwright test                               |

Automated check: `@axe-core/playwright` (dev dependency, exact version) on every page, phone and desktop, both languages and both themes, with the WCAG 2.0 / 2.1 / 2.2 A and AA tags. A finding fails the test; an exception is listed in the test with its reason.

## Pages

| Rule                                                                                                         | Checked by                |
| ------------------------------------------------------------------------------------------------------------ | ------------------------- |
| One short intro (at most 2 sentences) per page; longer explanations in a closed section or on the Usage page | review (checklist below)  |
| Every view that loads data (level page, plan, My farms) has an empty, a loading and an error state           | Playwright, `route.abort` |
| Icons with keywords instead of sentences where a concept repeats (cards, form fields)                        | review                    |
| Usage page: the web app first (level pages, My farms, export as the backup), the CLI in a closed section     | review                    |
| No sideways scroll on phone, tablet and desktop, at 130% and 160% text                                       | Playwright                |

Review checklist for a changed page:

- [ ] The intro has at most 2 sentences; nothing needed is only in a tooltip.
- [ ] Repeated concepts use their concept icon and keyword; game objects their item drawing or the placeholder.
- [ ] Empty, loading and error states exist and have both languages.
- [ ] The Playwright projects (desktop, mobile, tablet) and the axe check pass in both languages and themes.

## Settled points

- Dropdown or not (2026-11-23): Baymard finds dropdowns a poor choice under 5 or over 10 options and bewildering over 20. So logins per day (24 values) and fishing spots (16) are whole numbers with a range, beehives (4) and mastery stars (4) a button row; copies and slots stay dropdowns (at most 10 values).
- Touch targets: the 44 px rule rests on WCAG 2.5.5; Material Design 3 (48 dp) and Apple HIG (44 pt) are often cited with the same size but were not read in the research. Not needed further: the rule is set.
- Safari: whether a home-screen web app or a granted `persist()` lifts the 7-day deletion has no primary source. Not needed further: the export reminder treats every browser as if it may delete the data.
- Fishing spot drawing: `fishing_spot.svg` (no location `id`; the profile field is `fishing_spots_unlocked`).
- Animals icon: `paw-print`.

## Sources

Read 2026-11-23.

- WCAG 2.2: <https://www.w3.org/TR/WCAG22/>; Target Size (Minimum): <https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html>
- GOV.UK Design System, error summary: <https://design-system.service.gov.uk/components/error-summary/>; select: <https://design-system.service.gov.uk/components/select/>
- Baymard, drop-down usability: <https://baymard.com/blog/drop-down-usability>
- Nielsen Norman Group, errors in forms: <https://www.nngroup.com/articles/errors-forms-design-guidelines/>; tooltips: <https://www.nngroup.com/articles/tooltip-guidelines/>
- WebKit, full third-party cookie blocking and more (7-day cap, 2020-03-24): <https://webkit.org/blog/10218/>; updates to storage policy (2023-08-10): <https://webkit.org/blog/14403/updates-to-storage-policy/>
- MDN, storage quotas and eviction criteria: <https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria>
- web.dev, persistent storage: <https://web.dev/articles/persistent-storage>
- Brave, forgetful browsing (2023-05-11): <https://brave.com/privacy-updates/25-forgetful-browsing/>
