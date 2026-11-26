// The profile check: one set of rules for the form, the import and a stored profile.
import { describe, expect, it } from "vitest";
import { newFarmProfile, setLocationValue, setLoginWindow, setPlayerValue } from "./profile";
import { checkProfile, checkValue, fieldRange, maxLevel, ruleMessage, type Bounds } from "./check";

// the shape of web/public/py/defaults.json (`python -m src web-files`)
const bounds: Bounds = {
  locations: {
    chicken_coop: { name: "Chicken Coop", type: "animal", animal_capacity: 6 },
    bakery: { name: "Bakery", type: "production", max_slots: 9 },
    lobster_pool: { name: "Lobster pool", type: "animal" },
    apple_tree: { name: "Apple tree", type: "tree" },
  },
  limits: {
    "1": { fields: 6, copies: { chicken_coop: 1, bakery: 0 } },
    "3": { fields: 9, copies: { chicken_coop: 3, bakery: 1 } },
    "40": { fields: 63, copies: { chicken_coop: 3, bakery: 1 } },
  },
};

const EN = {
  wholeNumber: "Enter a whole number",
  range: "Between {min} and {max}",
  max: "At most {max} at level {level}",
  min: "At least {min}",
  step: "In steps of {step} ({min}, {next}, …)",
  summary: "{n} fields are invalid",
};

describe("maxLevel", () => {
  it("is the highest level of the data", () => {
    expect(maxLevel(bounds)).toBe(40);
  });
  it("is 1 without level limits, never -Infinity", () => {
    expect(maxLevel({ ...bounds, limits: {} })).toBe(1);
  });
});

describe("whole numbers", () => {
  it("accepts null (the level default) and whole numbers", () => {
    expect(checkValue("player.fields_owned", null, bounds, 3)).toBeNull();
    expect(checkValue("player.fields_owned", 4, bounds, 3)).toBeNull();
  });

  it("refuses fractions and text", () => {
    const error = { path: "player.fields_owned", value: 2.5, rule: "wholeNumber", params: {} };
    expect(checkValue("player.fields_owned", 2.5, bounds, 3)).toEqual(error);
    expect(checkValue("player.fields_owned", Number.NaN, bounds, 3)).toMatchObject({ rule: "wholeNumber" });
  });
});

describe("ranges", () => {
  it("slots: 1 to the machine's maximum (9), lobster pool and duck salon 1 to 6", () => {
    expect(checkValue("locations.bakery.slots", 9, bounds, 3)).toBeNull();
    expect(checkValue("locations.bakery.slots", 10, bounds, 3)).toEqual({
      path: "locations.bakery.slots",
      value: 10,
      rule: "range",
      params: { min: 1, max: 9 },
    });
    expect(checkValue("locations.lobster_pool.slots", 7, bounds, 50)).toMatchObject({
      rule: "range",
      params: { min: 1, max: 6 },
    });
  });

  it("mastery stars 0 to 3, beehives 1 to 4, fishing spots 0 to 15, logins 1 to 24", () => {
    expect(checkValue("locations.bakery.mastery_stars", 4, bounds, 3)).toMatchObject({ params: { min: 0, max: 3 } });
    expect(checkValue("locations.chicken_coop.beehives", 0, bounds, 3)).toMatchObject({ params: { min: 1, max: 4 } });
    expect(checkValue("player.fishing_spots_unlocked", 16, bounds, 3)).toMatchObject({ params: { min: 0, max: 15 } });
    expect(checkValue("planner.production.login_window.logins", 25, bounds, 3)).toMatchObject({
      params: { min: 1, max: 24 },
    });
  });

  it("level: empty is not the default, it is an error", () => {
    expect(checkValue("player.level", null, bounds, 3)).toMatchObject({ rule: "wholeNumber" });
  });

  it("level: 1 to the highest level of the data", () => {
    expect(checkValue("player.level", 0, bounds, 3)).toMatchObject({ rule: "range", params: { min: 1, max: 40 } });
    expect(checkValue("player.level", 41, bounds, 3)).toMatchObject({ rule: "range", params: { min: 1, max: 40 } });
  });
});

describe("limits of the level", () => {
  it("copies and fields: at most the level's limit, with the level", () => {
    expect(checkValue("locations.chicken_coop.owned", 3, bounds, 3)).toBeNull();
    expect(checkValue("locations.chicken_coop.owned", 4, bounds, 3)).toEqual({
      path: "locations.chicken_coop.owned",
      value: 4,
      rule: "max",
      params: { max: 3, level: 3 },
    });
    expect(checkValue("player.fields_owned", 10, bounds, 3)).toMatchObject({
      rule: "max",
      params: { max: 9, level: 3 },
    });
  });

  it("animals: at most animal_capacity x the copies of the level", () => {
    expect(checkValue("locations.chicken_coop.animals", 18, bounds, 3)).toBeNull();
    expect(checkValue("locations.chicken_coop.animals", 19, bounds, 3)).toMatchObject({
      rule: "max",
      params: { max: 18, level: 3 },
    });
  });

  it("without a known limit only the lower bound applies", () => {
    expect(checkValue("locations.apple_tree.owned", 50, bounds, 3)).toBeNull();
    expect(checkValue("locations.apple_tree.owned", -1, bounds, 3)).toEqual({
      path: "locations.apple_tree.owned",
      value: -1,
      rule: "min",
      params: { min: 0 },
    });
  });
});

describe("steps", () => {
  it("barn and silo: 50 to 1500 in steps of 25, or empty", () => {
    expect(checkValue("player.barn_capacity", null, bounds, 3)).toBeNull();
    expect(checkValue("player.barn_capacity", 75, bounds, 3)).toBeNull();
    expect(checkValue("player.barn_capacity", 60, bounds, 3)).toEqual({
      path: "player.barn_capacity",
      value: 60,
      rule: "step",
      params: { step: 25, min: 50, next: 75 },
    });
    expect(checkValue("player.silo_capacity", 40, bounds, 3)).toMatchObject({
      rule: "range",
      params: { min: 50, max: 1500 },
    });
    expect(checkValue("player.silo_capacity", 1600, bounds, 3)).toMatchObject({ rule: "range" });
  });
});

describe("fieldRange (the input attributes)", () => {
  it("gives min, max and step; no max when the limit is unknown", () => {
    expect(fieldRange("player.barn_capacity", bounds, 3)).toEqual({ min: 50, max: 1500, step: 25 });
    expect(fieldRange("locations.chicken_coop.owned", bounds, 3)).toEqual({ min: 0, max: 3 });
    expect(fieldRange("locations.apple_tree.owned", bounds, 3)).toEqual({ min: 0 });
    expect(fieldRange("locations.lobster_pool.slots", bounds, 50)).toEqual({ min: 1, max: 6 });
  });
});

describe("checkProfile", () => {
  it("a valid profile has no errors", () => {
    let p = newFarmProfile("a", 3);
    p = setLocationValue(p, "chicken_coop", "owned", 2);
    p = setPlayerValue(p, "barn_capacity", 500);
    expect(checkProfile(p, bounds)).toEqual([]);
  });

  it("a location row that is not an object gives a clear error, not a TypeError", () => {
    const p = newFarmProfile("a", 3);
    const broken = { ...p, player: { ...p.player, locations: { chicken_coop: null } } } as unknown as typeof p;
    expect(() => checkProfile(broken, bounds)).toThrow('The location "chicken_coop" is not an object');
  });

  it("lists every invalid value of a stored profile, in profile order", () => {
    let p = newFarmProfile("a", 3);
    p = setLocationValue(p, "chicken_coop", "owned", 4);
    p = setPlayerValue(p, "barn_capacity", 60);
    p = setLoginWindow(p, "logins", 30);
    expect(checkProfile(p, bounds).map((e) => [e.path, e.rule])).toEqual([
      ["player.barn_capacity", "step"],
      ["locations.chicken_coop.owned", "max"],
      ["planner.production.login_window.logins", "range"],
    ]);
  });
});

describe("ruleMessage", () => {
  it("fills the template of the error's rule", () => {
    const error = checkValue("locations.bakery.slots", 10, bounds, 3);
    expect(error && ruleMessage(error, EN)).toBe("Between 1 and 9");
    const max = checkValue("locations.chicken_coop.owned", 4, bounds, 3);
    expect(max && ruleMessage(max, EN)).toBe("At most 3 at level 3");
    const step = checkValue("player.barn_capacity", 60, bounds, 3);
    expect(step && ruleMessage(step, EN)).toBe("In steps of 25 (50, 75, …)");
  });
});
