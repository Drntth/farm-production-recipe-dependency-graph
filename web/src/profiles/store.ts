// Farm profiles in IndexedDB (idb-keyval, own database). The backend is an
// interface so the logic can be tested with a Map.
import { createStore, del, entries, get, keys, set, type UseStore } from "idb-keyval";
import { migrate } from "./profile";
import type { FarmProfile } from "./types";

export interface StoredProfile {
  id: string;
  profile: FarmProfile;
  /** epoch milliseconds of the last write */
  updated: number;
}

export interface Backend {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
  del(key: string): Promise<void>;
  keys(): Promise<string[]>;
  entries(): Promise<[string, unknown][]>;
}

const DB_NAME = "farm-production";
const STORE_NAME = "profiles";
const ACTIVE_KEY = "active-profile-id";
const PROFILE_PREFIX = "profile:";

/** The IndexedDB backend (created lazily: IndexedDB exists in the browser only). */
export function idbBackend(dbName = DB_NAME, storeName = STORE_NAME): Backend {
  let store: UseStore | undefined;
  const s = () => (store ??= createStore(dbName, storeName));
  return {
    get: (key) => get(key, s()),
    set: (key, value) => set(key, value, s()),
    del: (key) => del(key, s()),
    keys: async () => (await keys(s())).map(String),
    entries: async () => (await entries(s())).map(([k, v]) => [String(k), v]),
  };
}

/** A Map-backed backend for tests. */
export function memoryBackend(map = new Map<string, unknown>()): Backend {
  return {
    get: async (key) => map.get(key),
    set: async (key, value) => void map.set(key, value),
    del: async (key) => void map.delete(key),
    keys: async () => [...map.keys()],
    entries: async () => [...map.entries()],
  };
}

export interface ProfileStore {
  list(): Promise<StoredProfile[]>;
  get(id: string): Promise<StoredProfile | undefined>;
  /** Writes (insert or replace) and stamps `updated`. */
  put(id: string, profile: FarmProfile): Promise<StoredProfile>;
  remove(id: string): Promise<void>;
  getActiveId(): Promise<string | undefined>;
  setActiveId(id: string | undefined): Promise<void>;
}

export function createProfileStore(backend: Backend = idbBackend(), now: () => number = Date.now): ProfileStore {
  /** A stored profile at the current schema version; a migrated one is written back. */
  async function current(record: StoredProfile): Promise<StoredProfile> {
    let profile: FarmProfile;
    try {
      profile = migrate(record.profile);
    } catch {
      return record; // kept as stored: an import or export still shows the error
    }
    if (JSON.stringify(profile) === JSON.stringify(record.profile)) return record;
    const migrated = { ...record, profile };
    await backend.set(PROFILE_PREFIX + record.id, migrated);
    return migrated;
  }
  return {
    async list() {
      const rows = await backend.entries();
      const records = rows.filter(([key]) => key.startsWith(PROFILE_PREFIX)).map(([, value]) => value as StoredProfile);
      return (await Promise.all(records.map(current))).sort((a, b) => b.updated - a.updated);
    },
    async get(id) {
      const record = (await backend.get(PROFILE_PREFIX + id)) as StoredProfile | undefined;
      return record && current(record);
    },
    async put(id, profile) {
      const record: StoredProfile = { id, profile, updated: now() };
      await backend.set(PROFILE_PREFIX + id, record);
      return record;
    },
    async remove(id) {
      await backend.del(PROFILE_PREFIX + id);
      if ((await backend.get(ACTIVE_KEY)) === id) await backend.del(ACTIVE_KEY);
    },
    async getActiveId() {
      const id = await backend.get(ACTIVE_KEY);
      return typeof id === "string" ? id : undefined;
    },
    async setActiveId(id) {
      if (id === undefined) await backend.del(ACTIVE_KEY);
      else await backend.set(ACTIVE_KEY, id);
    },
  };
}

/** Asks the browser not to evict the data; false when unavailable or refused. */
export async function requestPersist(): Promise<boolean> {
  try {
    if (typeof navigator === "undefined" || !navigator.storage?.persist) return false;
    return await navigator.storage.persist();
  } catch {
    return false;
  }
}
