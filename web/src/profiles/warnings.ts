// The planner's notes (Python log warnings, English) in the page language.
// The patterns copy the messages of src/config.py, src/api/core.py and
// src/planner/quantities.py; warnings.test.ts fails when one is reworded.
import { fill } from "../i18n";

const LOC = String.raw`^Player config: locations\.(?<location>[a-z0-9_]+): `;

/** Note key in `profiles.notes` → the English message it translates. */
export const NOTE_PATTERNS = [
  ["storageNotSet", /^Player config: (?<storage>barn_capacity|silo_capacity) is not set; storage limits are unknown$/],
  [
    "fieldsOver",
    /^Player config: fields_owned=(?<value>\d+) exceeds the (?<max>\d+) fields available at level (?<level>\d+)$/,
  ],
  [
    "ownedOver",
    new RegExp(LOC + String.raw`owned=(?<value>\d+) exceeds the (?<max>\d+) copies available at level (?<level>\d+)$`),
  ],
  ["slotsOver", new RegExp(LOC + String.raw`slots=(?<value>\d+) exceeds (?<copies>\d+) x (?<per>\d+) slots$`)],
  ["slotsNoCopy", new RegExp(LOC + "slots set but no copy owned$")],
  ["slotsNotApply", new RegExp(LOC + "slots do not apply to [a-z_]+$")],
  ["animalsOver", new RegExp(LOC + String.raw`animals=(?<value>\d+) exceeds (?<copies>\d+) x (?<per>\d+) places$`)],
  ["notUnlocked", new RegExp(LOC + String.raw`unlocks at level (?<unlock>\d+), player is level (?<level>\d+)$`)],
  ["unknownLocation", new RegExp(LOC + "unknown location id$")],
  [
    "siloFull",
    /^Plan: the owned trees and bushes alone fill (?<fixed>\d+) silo places per login, more than the (?<room>\d+) planned for production$/,
  ],
] as const;

export type NoteKey = (typeof NOTE_PATTERNS)[number][0];

export interface NoteNames {
  /** Display name of a location id. */
  location: (id: string) => string;
  /** Label of `barn_capacity` / `silo_capacity`. */
  storage: (name: string) => string;
}

/** One warning `"<logger>: <message>"` in the page language; an unknown one stays English. */
export function translateWarning(raw: string, notes: Record<NoteKey, string>, names: NoteNames): string {
  const message = raw.replace(/^src\.[a-z_.]+: /, "");
  for (const [key, pattern] of NOTE_PATTERNS) {
    const groups = pattern.exec(message)?.groups;
    if (!groups && !pattern.test(message)) continue;
    const values: Record<string, string> = { ...groups };
    if (values.location) values.location = names.location(values.location);
    if (values.storage) values.storage = names.storage(values.storage);
    return fill(notes[key], values);
  }
  return message;
}
