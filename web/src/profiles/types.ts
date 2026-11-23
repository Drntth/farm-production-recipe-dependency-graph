// The farm profile JSON, as `python -m src farm-profile` (src/farm_profile.py,
// farm_profile_json) writes it. An omitted key means "the level default";
// null is never written (clearing a value removes the key).

/** Versions of the parts, from CURRENT in src/schema.py. */
export const SCHEMA_VERSIONS = {
  farm_profile: 1,
  player: 1,
  profile_map: 1,
  design: 1,
  planner: 2,
} as const;

/** The player's state of one location type (LocationProgress in src/config.py). */
export interface LocationProgress {
  owned?: number;
  slots?: number;
  mastery_stars?: number;
  workbench_level?: number;
  animals?: number;
  beehives?: number;
}

export type LocationField = keyof LocationProgress;

export type MasterySystem = "stars" | string;

export interface PlayerConfig {
  schema_version: number;
  level: number;
  mastery_system?: MasterySystem;
  barn_capacity?: number;
  silo_capacity?: number;
  fields_owned?: number;
  fishing_spots_unlocked?: number;
  locations?: Record<string, LocationProgress>;
}

/** Top-level player fields that hold one optional number. */
export type PlayerNumberField = "barn_capacity" | "silo_capacity" | "fields_owned" | "fishing_spots_unlocked";

/** The player's part of the farm map (ProfileMap in src/layout/farm_map.py). */
export interface ProfileMap {
  schema_version: number;
  unlocked?: string[];
  zones?: unknown[];
  current?: unknown[];
  background?: unknown;
  [key: string]: unknown;
}

/** Layout settings (config/design.json); every key but the version is optional. */
export interface DesignSettings {
  schema_version: number;
  [key: string]: unknown;
}

/** Planner settings (config/planner.json); every key but the version is optional. */
export interface PlannerSettings {
  schema_version: number;
  [key: string]: unknown;
}

export interface FarmProfile {
  schema_version: number;
  name?: string;
  player: PlayerConfig;
  profile_map: ProfileMap;
  design: DesignSettings;
  planner: PlannerSettings;
  templates: Record<string, { schema_version: number; [key: string]: unknown }>;
}
