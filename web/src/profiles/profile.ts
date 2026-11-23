// Pure farm profile logic: no IndexedDB, no DOM. Functions return new objects.
import {
  SCHEMA_VERSIONS,
  type FarmProfile,
  type LocationField,
  type LocationProgress,
  type PlayerConfig,
  type PlayerNumberField,
} from "./types";

type Json = Record<string, unknown>;
type Migration = (profile: Json) => Json;

/** version → migration to version + 1; empty until the format changes. */
export const MIGRATIONS: Record<number, Migration> = {};

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** A minimal valid profile: only the level in the player part, the rest at defaults. */
export function newFarmProfile(name: string, level: number): FarmProfile {
  return {
    schema_version: SCHEMA_VERSIONS.farm_profile,
    name,
    player: { schema_version: SCHEMA_VERSIONS.player, level },
    profile_map: { schema_version: SCHEMA_VERSIONS.profile_map },
    design: { schema_version: SCHEMA_VERSIONS.design },
    planner: { schema_version: SCHEMA_VERSIONS.planner },
    templates: {},
  };
}

/** Same profile with another player level; location overrides outside *unlockedLocationIds* are dropped. */
export function setLevel(profile: FarmProfile, level: number, unlockedLocationIds: Iterable<string>): FarmProfile {
  const unlocked = new Set(unlockedLocationIds);
  const player = { ...profile.player, level };
  if (player.locations) {
    const kept = Object.entries(player.locations).filter(([id]) => unlocked.has(id));
    if (kept.length > 0) player.locations = Object.fromEntries(kept);
    else delete player.locations;
  }
  return { ...profile, player };
}

/** Sets one value of a location; null (or undefined) removes the key, and an empty location is removed. */
export function setLocationValue(
  profile: FarmProfile,
  locationId: string,
  field: LocationField,
  value: number | null | undefined,
): FarmProfile {
  const locations = { ...profile.player.locations };
  const entry: LocationProgress = { ...locations[locationId] };
  if (value === null || value === undefined) delete entry[field];
  else entry[field] = value;
  if (Object.keys(entry).length > 0) locations[locationId] = entry;
  else delete locations[locationId];
  const player: PlayerConfig = { ...profile.player, locations };
  if (Object.keys(locations).length === 0) delete player.locations;
  return { ...profile, player };
}

/** Sets a top-level number of the player (barn, silo, fields, fishing spots); null clears it. */
export function setPlayerValue(
  profile: FarmProfile,
  field: PlayerNumberField,
  value: number | null | undefined,
): FarmProfile {
  const player = { ...profile.player };
  if (value === null || value === undefined) delete player[field];
  else player[field] = value;
  return { ...profile, player };
}

export type LoginWindowField = "start" | "end" | "logins";

/** The planner's daily login window (`production.login_window`); null removes the key (= default). */
export function loginWindow(profile: FarmProfile): Partial<Record<LoginWindowField, string | number>> {
  const production = (profile.planner.production ?? {}) as Json;
  return { ...((production.login_window ?? {}) as Json) } as Partial<Record<LoginWindowField, string | number>>;
}

/** Sets one value of the login window; null (or undefined) removes it, empty parts are removed. */
export function setLoginWindow(
  profile: FarmProfile,
  field: LoginWindowField,
  value: string | number | null | undefined,
): FarmProfile {
  const window: Json = loginWindow(profile);
  if (value === null || value === undefined || value === "") delete window[field];
  else window[field] = value;
  const production: Json = { ...((profile.planner.production ?? {}) as Json) };
  if (Object.keys(window).length > 0) production.login_window = window;
  else delete production.login_window;
  const { production: _old, ...rest } = profile.planner;
  const planner = Object.keys(production).length > 0 ? { ...rest, production } : rest;
  return { ...profile, planner };
}

/** Same profile with another name; an empty name is removed. */
export function setName(profile: FarmProfile, name: string): FarmProfile {
  const { name: _old, ...rest } = profile;
  return name ? { ...rest, name } : rest;
}

/**
 * The profile at the current schema version. A current one passes unchanged,
 * an older one runs through MIGRATIONS, a newer one or a malformed one is an Error.
 */
export function migrate(json: unknown): FarmProfile {
  if (!isObject(json)) throw new Error("The farm profile must be a JSON object");
  // like src/schema.py: a missing version is version 1
  let version = json.schema_version ?? 1;
  if (typeof version !== "number" || !Number.isInteger(version) || version < 1) {
    throw new Error(`schema_version must be a positive integer, got ${JSON.stringify(version)}`);
  }
  const target = SCHEMA_VERSIONS.farm_profile;
  if (version > target) {
    throw new Error(
      `The farm profile has schema_version ${version}, this version reads up to ${target}; update the app`,
    );
  }
  let data: Json = json;
  while (version < target) {
    const step = MIGRATIONS[version];
    if (!step) throw new Error(`No migration for the farm profile from schema_version ${version}`);
    data = step(data);
    version += 1;
  }
  return check({ ...data, schema_version: target });
}

/** Basic shape check of a profile at the current version. */
function check(data: Json): FarmProfile {
  const { player } = data;
  if (!isObject(player)) throw new Error("The farm profile has no player part");
  if (typeof player.level !== "number" || !Number.isInteger(player.level) || player.level < 1) {
    throw new Error("player.level must be a positive integer");
  }
  if (player.locations !== undefined && !isObject(player.locations)) {
    throw new Error("player.locations must be an object");
  }
  for (const key of ["profile_map", "design", "planner", "templates"] as const) {
    if (data[key] !== undefined && !isObject(data[key])) throw new Error(`${key} must be an object`);
  }
  if (data.name !== undefined && typeof data.name !== "string") throw new Error("name must be a string");
  const profile = data as unknown as FarmProfile;
  return {
    ...profile,
    player: { ...profile.player, schema_version: profile.player.schema_version ?? SCHEMA_VERSIONS.player },
    profile_map: profile.profile_map ?? { schema_version: SCHEMA_VERSIONS.profile_map },
    design: profile.design ?? { schema_version: SCHEMA_VERSIONS.design },
    planner: profile.planner ?? { schema_version: SCHEMA_VERSIONS.planner },
    templates: profile.templates ?? {},
  };
}

/** The profile as a pretty JSON file for `--farm-profile` (no internal ids). */
export function exportJson(profile: FarmProfile): string {
  return JSON.stringify(profile, null, 2) + "\n";
}

/** Parses, checks and migrates a farm profile file; throws an Error with a clear message. */
export function importJson(text: string): FarmProfile {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error("The file is not valid JSON");
  }
  return migrate(json);
}
