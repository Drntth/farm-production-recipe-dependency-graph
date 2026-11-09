// Build-time access to the level recommendations (`python -m src recommend`).
// Read from RECOMMENDATIONS_DIR, else ../output/recommendations; nothing of
// it is loaded in the browser except the pages and the layout SVGs.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export interface IndexRow {
  level: number;
  blocks: number;
  blocks_not_placed: number;
  logins_per_day: number;
}

export interface RecommendationIndex {
  schema_version: number;
  game_version: string | null;
  core_version: string | null;
  levels: IndexRow[];
}

export interface BlockLocation {
  id: string;
  name: string;
  copies: number;
  reserved: number;
  source: string;
  /** share of the production hours in use, 0-1 */
  busy?: number;
  /** product id → items per hour */
  per_hour?: Record<string, number>;
}

/** Goods per hour from one block to another; tiles_apart null if one is not placed. */
export interface FlowLink {
  source: string;
  target: string;
  per_hour: number;
  tiles_apart: number | null;
}

export interface Block {
  id: string;
  name: string;
  placed: boolean;
  locations: BlockLocation[];
  fields: { count: number; reserved: number; crops: string[] } | null;
}

/** One placed copy on the map (tile coordinates, footprint after rotation). */
export interface LayoutItem {
  location_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotated: boolean;
  reserved: boolean;
}

/** A block as the layout placed it; `frame` is null for an unplaced block. */
export interface LayoutBlock {
  id: string;
  name: string;
  frame: { x: number; y: number; width: number; height: number } | null;
  items: LayoutItem[];
}

export interface LoginItem {
  recipe_id?: string;
  resource_id?: string;
  per_login: number;
  per_day: number;
  count?: number;
  every_n_logins?: number;
}

export interface LoginAction {
  step: number;
  action: string;
  what?: string;
  location_id?: string;
  slots?: number;
  items?: LoginItem[];
}

export interface Combined {
  level: number;
  summary: {
    logins_per_day: number;
    login_times: string[];
    production_hours_per_hour: number;
    fields_used: number;
    blocks: number;
    blocks_not_placed: string[];
    strategy: string;
    reserve_ratio: number;
  };
  blocks: Block[];
  flow_links: FlowLink[];
  weighted_flow_distance: number;
  layout: { blocks: LayoutBlock[] };
  expansion: {
    lookahead_levels: number;
    upcoming: { location_id: string; kind: string; unlock_level: number; count: number }[];
  };
  warnings: string[];
  schedule: {
    logins_per_day: number;
    logins_suggested: boolean;
    login_times: string[];
    day_gap_hours: number;
    night_gap_hours: number;
    last_login: {
      time: string;
      items: { recipe_id?: string; location_id?: string; resource_id?: string; hours: number }[];
    } | null;
    login_options: {
      logins: number;
      longest_gap_hours: number;
      production_hours_per_hour: number;
      balance_per_day: number;
    }[];
    recommendations: {
      fields: { available: number; owned: number; used_by_plan: number };
      trees_and_bushes: Record<string, { resource_id: string; plants: number; source: string }>;
    };
    actions_per_login: LoginAction[];
    external_per_day: Record<string, number>;
    warnings: string[];
  };
}

export interface Recommendation {
  schema_version: number;
  level: number;
  game_version: string | null;
  core_version: string | null;
  blocks_not_placed: string[];
  combined: Combined;
}

/** `map.json`: the base map every level is laid out on (rects are `[x, y, w, h]`). */
export interface MapView {
  schema_version: number;
  width: number;
  height: number;
  usable: [number, number, number, number][];
  usable_bounds: [number, number, number, number] | null;
  farm_outline: [number, number, number, number][];
  fixed: { id: string; name: string; x: number; y: number; width: number; height: number }[];
}

// the schema versions this site reads (src/schema.py)
const INDEX_VERSION = 2;
const LEVEL_VERSION = 2;
const MAP_VERSION = 1;

export function recommendationsDir(): string {
  return resolve(process.cwd(), process.env.RECOMMENDATIONS_DIR ?? "../output/recommendations");
}

function readJson<T extends { schema_version: number }>(name: string, version: number): T {
  const path = resolve(recommendationsDir(), name);
  const data = JSON.parse(readFileSync(path, "utf-8")) as T;
  if (data.schema_version !== version) {
    throw new Error(`${path}: schema_version ${data.schema_version}, this site reads ${version}`);
  }
  return data;
}

export function loadIndex(): RecommendationIndex {
  return readJson<RecommendationIndex>("index.json", INDEX_VERSION);
}

export function loadLevel(level: number): Recommendation {
  return readJson<Recommendation>(`level_${level}.json`, LEVEL_VERSION);
}

export function loadMap(): MapView {
  return readJson<MapView>("map.json", MAP_VERSION);
}

export function loadLevelSvg(level: number): string {
  return readFileSync(resolve(recommendationsDir(), `level_${level}.svg`), "utf-8");
}

/** `apple_juice` → `Apple juice` (the level JSON carries ids only). */
export function label(id: string): string {
  const text = id.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** A path below the site base (GitHub Pages serves the site in a subdirectory). */
export function url(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}/${path.replace(/^\//, "")}`;
}

/** Buildings first unlocked since the previous listed level: its look-ahead (kind `new`). */
export function newBuildings(levels: number[]): Map<number, string[]> {
  const out = new Map<number, string[]>();
  levels.forEach((level, i) => {
    if (i === 0) return;
    // listed levels may skip some (--levels 1,20,40): everything unlocked since the previous one
    const prev = levels[i - 1];
    const upcoming = loadLevel(prev).combined.expansion.upcoming;
    out.set(
      level,
      upcoming
        .filter((u) => u.kind === "new" && u.unlock_level > prev && u.unlock_level <= level)
        .map((u) => u.location_id),
    );
  });
  return out;
}
