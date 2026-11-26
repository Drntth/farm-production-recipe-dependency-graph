// The profile check: the input rules of docs/ui-design.md for one value of a farm
// profile, used by the form, the import and a stored profile. Pure: no DOM, no IndexedDB.
// The bounds come from web/public/py/defaults.json (`python -m src web-files`); the
// fixed game ranges below have no data field and are cited from the game-facts docs.
import { fill } from "../i18n";
import { loginWindow } from "./profile";
import type { FarmProfile } from "./types";

/** One location of defaults.json: `animal_capacity` and `max_slots` only where the data has them. */
export interface LocationBounds {
  name?: string;
  type: string;
  animal_capacity?: number;
  max_slots?: number;
}

/** The copies unlocked and the fields granted at one level (`limits` in defaults.json). */
export interface LevelLimits {
  fields: number | null;
  /** location id → copies unlocked at the level */
  copies: Record<string, number>;
}

export interface Bounds {
  locations: Record<string, LocationBounds>;
  /** level (as a string key) → limits of that level */
  limits: Record<string, LevelLimits>;
}

export type RuleKey = "wholeNumber" | "range" | "max" | "min" | "step";

/** One invalid value: where it is, what was given and which rule it breaks. */
export interface FieldError {
  /** `player.level`, `player.barn_capacity`, `locations.<id>.<field>`, `planner.production.login_window.logins` */
  path: string;
  value: unknown;
  rule: RuleKey;
  params: Record<string, number>;
}

/** The min, max and step of a field (the input attributes); max is absent when the level gives none. */
export interface FieldRange {
  min: number;
  max?: number;
  step?: number;
}

interface Spec extends FieldRange {
  /** the max comes from the level (copies, fields, animals): its message names the level */
  levelBound?: boolean;
}

// Fixed ranges without a data field (see docs/game-facts/*.md and docs/ui-design.md).
const STARS: [number, number] = [0, 3]; // production-buildings.md: mastery stars
const BEEHIVES: [number, number] = [1, 4]; // animals.md: beehive tree, 1 at start, up to 4
const FISHING_SPOTS: [number, number] = [0, 15]; // fishing-lake.md: fishing spots
const LOGINS: [number, number] = [1, 24]; // the daily login window of the planner
const STORAGE: FieldRange = { min: 50, max: 1500, step: 25 }; // storage.md: barn and silo
const SLOTS_DEFAULT = 9; // production-buildings.md: maximum slots per machine copy
/** Maximum slots of locations without `max_slots` in the data (production-buildings.md). */
const SLOTS_FIXED: Record<string, number> = { lobster_pool: 6, duck_salon: 6 };

const PLAYER_NUMBERS = ["barn_capacity", "silo_capacity", "fields_owned", "fishing_spots_unlocked"] as const;

/** The highest level of the data (the level limits go up to it). */
export function maxLevel(bounds: Bounds): number {
  // no limits in the data: level 1 only, never -Infinity (every level invalid)
  return Math.max(1, ...Object.keys(bounds.limits).map(Number));
}

function between(min: number, max: number): Spec {
  return { min, max };
}

/** The rule of one field; undefined for a field the check does not know. */
function specFor(path: string, bounds: Bounds, level: number): Spec | undefined {
  const limit = bounds.limits[String(level)];
  if (path === "player.level") return between(1, maxLevel(bounds));
  if (path === "player.barn_capacity" || path === "player.silo_capacity") return { ...STORAGE };
  if (path === "player.fields_owned")
    return limit?.fields == null ? { min: 0 } : { min: 0, max: limit.fields, levelBound: true };
  if (path === "player.fishing_spots_unlocked") return between(...FISHING_SPOTS);
  if (path === "planner.production.login_window.logins") return between(...LOGINS);

  const match = /^locations\.([a-z0-9_]+)\.([a-z_]+)$/.exec(path);
  if (!match) return undefined;
  const [, id, field] = match;
  const location = bounds.locations[id];
  const copies = limit?.copies[id];
  switch (field) {
    case "owned":
      return copies === undefined ? { min: 0 } : { min: 0, max: copies, levelBound: true };
    case "slots":
      return between(1, location?.max_slots ?? SLOTS_FIXED[id] ?? SLOTS_DEFAULT);
    case "mastery_stars":
      return between(...STARS);
    case "beehives":
      return between(...BEEHIVES);
    case "animals": {
      const capacity = location?.animal_capacity;
      if (capacity === undefined || copies === undefined) return { min: 0 };
      return { min: 0, max: capacity * copies, levelBound: true };
    }
    default:
      return undefined;
  }
}

/** The error of one value at *path*, or null (also for null = the level default). */
export function checkValue(path: string, value: unknown, bounds: Bounds, level: number): FieldError | null {
  const spec = specFor(path, bounds, level);
  if (!spec) return null;
  const fail = (rule: RuleKey, params: Record<string, number>): FieldError => ({ path, value, rule, params });
  // the level is never empty: null (the level default) does not exist for it
  if (value === null || value === undefined) return path === "player.level" ? fail("wholeNumber", {}) : null;
  if (typeof value !== "number" || !Number.isInteger(value)) return fail("wholeNumber", {});
  if (value < spec.min) {
    return spec.max === undefined ? fail("min", { min: spec.min }) : fail("range", { min: spec.min, max: spec.max });
  }
  if (spec.max !== undefined && value > spec.max) {
    return spec.levelBound ? fail("max", { max: spec.max, level }) : fail("range", { min: spec.min, max: spec.max });
  }
  if (spec.step !== undefined && (value - spec.min) % spec.step !== 0) {
    return fail("step", { step: spec.step, min: spec.min, next: spec.min + spec.step });
  }
  return null;
}

/** The min, max and step of a field at *level* (for the input attributes). */
export function fieldRange(path: string, bounds: Bounds, level: number): FieldRange {
  const spec = specFor(path, bounds, level) ?? { min: 0 };
  const range: FieldRange = { min: spec.min };
  if (spec.max !== undefined) range.max = spec.max;
  if (spec.step !== undefined) range.step = spec.step;
  return range;
}

/** Every invalid value of a profile (a new, imported or stored one), in profile order. */
export function checkProfile(profile: FarmProfile, bounds: Bounds): FieldError[] {
  const level = profile.player.level;
  const errors: FieldError[] = [];
  const check = (path: string, value: unknown) => {
    const error = checkValue(path, value, bounds, level);
    if (error) errors.push(error);
  };
  check("player.level", level);
  for (const field of PLAYER_NUMBERS) check(`player.${field}`, profile.player[field]);
  for (const [id, row] of Object.entries(profile.player.locations ?? {})) {
    // a hand-edited file: a clear message (shown by the import) instead of a TypeError
    if (typeof row !== "object" || row === null || Array.isArray(row)) {
      throw new Error(`The location "${id}" is not an object`);
    }
    for (const [field, value] of Object.entries(row)) check(`locations.${id}.${field}`, value);
  }
  check("planner.production.login_window.logins", loginWindow(profile).logins);
  return errors;
}

/** The message of an error in the page language: the template of its rule, filled. */
export function ruleMessage(error: FieldError, templates: Record<RuleKey, string>): string {
  return fill(templates[error.rule], error.params);
}
