import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import en from "../../content/en.json";
import hu from "../../content/hu.json";
import { NOTE_PATTERNS, translateWarning } from "./warnings";

const names = {
  location: (id: string) => ({ bakery: "Bakery", chicken_coop: "Chicken coop" })[id] ?? id,
  storage: (name: string) => (name === "barn_capacity" ? hu.profiles.barn : hu.profiles.silo),
};

describe("translateWarning", () => {
  it("turns the planner's notes into the page language", () => {
    const notes = hu.profiles.notes;
    expect(
      translateWarning(
        "src.planner: Player config: barn_capacity is not set; storage limits are unknown",
        notes,
        names,
      ),
    ).toBe("Pajta kapacitása nincs megadva: a terv nem számol a tárolóhellyel.");
    expect(
      translateWarning(
        "src.planner: Player config: locations.bakery: owned=3 exceeds the 1 copies available at level 20",
        notes,
        names,
      ),
    ).toBe("Bakery: 3 darab van megadva, de a 20. szinten csak 1 érhető el.");
    expect(
      translateWarning(
        "src.planner: Player config: locations.chicken_coop: animals=9 exceeds 1 x 6 places",
        notes,
        names,
      ),
    ).toBe("Chicken coop: 9 állat van megadva, de csak 1 × 6 hely van.");
    expect(
      translateWarning(
        "src.planner: Plan: the owned trees and bushes alone fill 120 silo places per login, more than the 90 planned for production",
        notes,
        names,
      ),
    ).toBe("A fák és bokrok termése belépésenként 120 silóhelyet foglal, több mint a termelésre szánt 90.");
  });

  it("keeps an unknown note in English, without the logger name", () => {
    expect(translateWarning("src.planner: Something new", hu.profiles.notes, names)).toBe("Something new");
  });

  it("has a text for every note in both languages", () => {
    for (const [key] of NOTE_PATTERNS) {
      expect(en.profiles.notes[key], key).toBeTruthy();
      expect(hu.profiles.notes[key], key).toBeTruthy();
    }
  });

  it("still matches the messages of the Python core", () => {
    // the patterns copy these texts; a reworded message must update warnings.ts
    const python = ["../src/config.py", "../src/api/core.py", "../src/planner/quantities.py"]
      .map((f) => readFileSync(new URL(`../../${f}`, import.meta.url), "utf-8"))
      .join("\n");
    for (const fragment of [
      "is not set; storage limits are unknown",
      'fields "\n                f"available at level {cfg.level}',
      "copies available at level",
      "slots set but no copy owned",
      "slots do not apply to",
      'places"',
      "unlocks at level",
      "unknown location id",
      "silo places per",
      "more than the {room:.0f} planned for production",
    ]) {
      expect(python, fragment).toContain(fragment);
    }
  });
});
