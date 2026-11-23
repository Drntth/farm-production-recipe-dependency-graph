import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  exportJson,
  importJson,
  migrate,
  newFarmProfile,
  loginWindow,
  setLevel,
  setLocationValue,
  setName,
  setLoginWindow,
  setPlayerValue,
} from "./profile";
import { SCHEMA_VERSIONS } from "./types";

describe("newFarmProfile", () => {
  it("is minimal: only the level in the player part", () => {
    expect(newFarmProfile("Main farm", 12)).toEqual({
      schema_version: SCHEMA_VERSIONS.farm_profile,
      name: "Main farm",
      player: { schema_version: SCHEMA_VERSIONS.player, level: 12 },
      profile_map: { schema_version: SCHEMA_VERSIONS.profile_map },
      design: { schema_version: SCHEMA_VERSIONS.design },
      planner: { schema_version: SCHEMA_VERSIONS.planner },
      templates: {},
    });
  });
});

describe("setLevel", () => {
  it("drops overrides of locations not unlocked at the new level, keeps the rest", () => {
    let p = newFarmProfile("a", 30);
    p = setLocationValue(p, "bakery", "slots", 5);
    p = setLocationValue(p, "sushi_bar", "slots", 2);
    const lower = setLevel(p, 10, ["bakery"]);
    expect(lower.player.level).toBe(10);
    expect(lower.player.locations).toEqual({ bakery: { slots: 5 } });
    expect(p.player.level).toBe(30); // input unchanged
  });

  it("removes the locations key when nothing is left", () => {
    const p = setLocationValue(newFarmProfile("a", 30), "sushi_bar", "slots", 2);
    expect(setLevel(p, 5, []).player).not.toHaveProperty("locations");
  });
});

describe("null means level default", () => {
  it("setting null removes the key, then the empty location", () => {
    let p = setLocationValue(newFarmProfile("a", 5), "dairy", "slots", 8);
    p = setLocationValue(p, "dairy", "mastery_stars", 0); // 0 is a value, not a default
    p = setLocationValue(p, "dairy", "slots", null);
    expect(p.player.locations).toEqual({ dairy: { mastery_stars: 0 } });
    p = setLocationValue(p, "dairy", "mastery_stars", null);
    expect(p.player).not.toHaveProperty("locations");
    expect(exportJson(p)).not.toContain("null");
  });

  it("clears player numbers", () => {
    let p = setPlayerValue(newFarmProfile("a", 5), "barn_capacity", 500);
    expect(p.player.barn_capacity).toBe(500);
    p = setPlayerValue(p, "barn_capacity", null);
    expect(p.player).not.toHaveProperty("barn_capacity");
  });

  it("setName removes an empty name", () => {
    expect(setName(newFarmProfile("a", 1), "")).not.toHaveProperty("name");
    expect(setName(newFarmProfile("a", 1), "b").name).toBe("b");
  });
});

describe("migrate", () => {
  it("passes the current version", () => {
    const p = newFarmProfile("a", 3);
    expect(migrate(p)).toEqual(p);
  });

  it("treats a missing version as 1", () => {
    const { schema_version: _version, ...rest } = newFarmProfile("a", 3);
    expect(migrate(rest).schema_version).toBe(SCHEMA_VERSIONS.farm_profile);
  });

  it("rejects a newer version", () => {
    const p = { ...newFarmProfile("a", 3), schema_version: SCHEMA_VERSIONS.farm_profile + 1 };
    expect(() => migrate(p)).toThrow(/update the app/);
  });

  it("rejects malformed input", () => {
    expect(() => migrate(null)).toThrow();
    expect(() => migrate([])).toThrow();
    expect(() => migrate({ schema_version: "1", player: { level: 1 } })).toThrow(/schema_version/);
    expect(() => migrate({ schema_version: 0, player: { level: 1 } })).toThrow(/schema_version/);
    expect(() => migrate({ schema_version: 1 })).toThrow(/player/);
    expect(() => migrate({ schema_version: 1, player: { level: 0 } })).toThrow(/level/);
    expect(() => migrate({ schema_version: 1, player: { level: 2, locations: [] } })).toThrow(/locations/);
  });

  it("fills missing parts with defaults", () => {
    const p = migrate({ schema_version: 1, player: { level: 2 } });
    expect(p.planner.schema_version).toBe(SCHEMA_VERSIONS.planner);
    expect(p.templates).toEqual({});
  });
});

describe("export and import", () => {
  const rich = () => {
    let p = newFarmProfile("Farm B", 40);
    p = setPlayerValue(p, "fields_owned", 60);
    p = setLocationValue(p, "bakery", "slots", 7);
    p = setLocationValue(p, "bakery", "mastery_stars", 2);
    p = setLocationValue(p, "beehive_tree", "beehives", 2);
    return p;
  };

  it("round trips unchanged", () => {
    const p = rich();
    expect(importJson(exportJson(p))).toEqual(p);
  });

  it("matches the fixture used for the CLI check", () => {
    const text = readFileSync(new URL("./fixture.farm-profile.json", import.meta.url), "utf8");
    expect(exportJson(rich())).toBe(text);
  });

  it("throws clear errors on bad text", () => {
    expect(() => importJson("not json")).toThrow(/not valid JSON/);
    expect(() => importJson("{}")).toThrow(/player/);
  });
});

describe("setLoginWindow", () => {
  it("sets and clears login window values, dropping empty parts", () => {
    const base = newFarmProfile("A", 30);
    const set = setLoginWindow(setLoginWindow(base, "start", "08:00"), "logins", 4);
    expect(set.planner).toEqual({
      schema_version: SCHEMA_VERSIONS.planner,
      production: { login_window: { start: "08:00", logins: 4 } },
    });
    expect(loginWindow(set)).toEqual({ start: "08:00", logins: 4 });
    const cleared = setLoginWindow(setLoginWindow(set, "start", null), "logins", "");
    expect(cleared.planner).toEqual({ schema_version: SCHEMA_VERSIONS.planner });
    expect(base.planner).toEqual({ schema_version: SCHEMA_VERSIONS.planner });
  });

  it("keeps the other planner settings", () => {
    const base = newFarmProfile("A", 30);
    base.planner = { schema_version: SCHEMA_VERSIONS.planner, production: { storage_share: 0.4 } };
    const set = setLoginWindow(base, "end", "22:00");
    expect(set.planner.production).toEqual({ storage_share: 0.4, login_window: { end: "22:00" } });
    expect(setLoginWindow(set, "end", null).planner.production).toEqual({ storage_share: 0.4 });
  });
});
