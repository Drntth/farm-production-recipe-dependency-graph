import { describe, expect, it } from "vitest";
import { newFarmProfile } from "./profile";
import { createProfileStore, memoryBackend, requestPersist } from "./store";

function fixture() {
  let t = 1000;
  return createProfileStore(memoryBackend(), () => ++t);
}

describe("profile store", () => {
  it("put, get, list, remove", async () => {
    const store = fixture();
    expect(await store.get("a")).toBeUndefined();
    const rec = await store.put("a", newFarmProfile("A", 5));
    expect(rec).toMatchObject({ id: "a", updated: 1001 });
    expect((await store.get("a"))?.profile.name).toBe("A");
    await store.put("a", newFarmProfile("A2", 6));
    expect((await store.get("a"))?.profile.player.level).toBe(6);
    expect(await store.list()).toHaveLength(1);
    await store.remove("a");
    expect(await store.list()).toEqual([]);
  });

  it("keeps two profiles side by side, newest first", async () => {
    const store = fixture();
    await store.put("a", newFarmProfile("A", 5));
    await store.put("b", newFarmProfile("B", 50));
    await store.put("a", newFarmProfile("A", 7));
    const rows = await store.list();
    expect(rows.map((r) => r.id)).toEqual(["a", "b"]);
    expect((await store.get("b"))?.profile.player.level).toBe(50);
  });

  it("stores the active id apart from the profiles", async () => {
    const store = fixture();
    expect(await store.getActiveId()).toBeUndefined();
    await store.put("a", newFarmProfile("A", 5));
    await store.setActiveId("a");
    expect(await store.getActiveId()).toBe("a");
    expect(await store.list()).toHaveLength(1);
    await store.remove("a");
    expect(await store.getActiveId()).toBeUndefined();
  });

  it("keeps the export time beside the profile, through later writes", async () => {
    const store = fixture();
    await store.put("a", newFarmProfile("A", 5));
    expect((await store.get("a"))?.exported).toBeUndefined();
    const marked = await store.markExported("a");
    expect(marked).toMatchObject({ updated: 1001, exported: 1002 });
    await store.put("a", newFarmProfile("A", 6));
    expect(await store.get("a")).toMatchObject({ updated: 1003, exported: 1002 });
    // the export time is not part of the profile file
    expect(JSON.stringify((await store.get("a"))?.profile)).not.toContain("exported");
  });
});

describe("stored profiles at an older schema version", () => {
  it("are migrated on read and written back", async () => {
    const backend = memoryBackend();
    const store = createProfileStore(backend, () => 1);
    const { schema_version: _v, ...old } = newFarmProfile("Old", 7);
    await backend.set("profile:o", { id: "o", profile: old, updated: 1 });
    const [record] = await store.list();
    expect(record.profile.schema_version).toBe(1);
    expect(((await backend.get("profile:o")) as { profile: { schema_version?: number } }).profile.schema_version).toBe(
      1,
    );
    expect((await store.get("o"))?.profile.name).toBe("Old");
  });
});

describe("requestPersist", () => {
  it("is false without navigator.storage", async () => {
    expect(await requestPersist()).toBe(false);
  });
});
