import { describe, expect, it } from "vitest";
import { DAY_MS, lastExportAgo, needsReminder } from "./backup";

const NOW = 100 * DAY_MS;

describe("export reminder", () => {
  it("shows for a profile never exported", () => {
    expect(needsReminder({ updated: NOW - 1 }, NOW)).toBe(true);
  });

  it("stays hidden right after an export, also after a later change", () => {
    expect(needsReminder({ updated: NOW - 5, exported: NOW - 10 }, NOW)).toBe(false);
    expect(needsReminder({ updated: NOW - 10, exported: NOW - 5 }, NOW)).toBe(false);
  });

  it("shows when the profile changed after an export older than 7 days", () => {
    expect(needsReminder({ updated: NOW - 1, exported: NOW - 8 * DAY_MS }, NOW)).toBe(true);
  });

  it("stays hidden for an old export when nothing changed since", () => {
    expect(needsReminder({ updated: NOW - 9 * DAY_MS, exported: NOW - 8 * DAY_MS }, NOW)).toBe(false);
  });

  it("the 7 days are the limit: 7 days exactly is not yet old", () => {
    expect(needsReminder({ updated: NOW - 1, exported: NOW - 7 * DAY_MS }, NOW)).toBe(false);
  });
});

describe("last export text", () => {
  it("is relative, in the page language", () => {
    expect(lastExportAgo(NOW - 3 * DAY_MS, NOW, "en")).toBe("3 days ago");
    expect(lastExportAgo(NOW - 3 * DAY_MS, NOW, "hu")).toBe("3 nappal ezelőtt");
    expect(lastExportAgo(NOW - 2 * 3600_000, NOW, "en")).toBe("2 hours ago");
    expect(lastExportAgo(NOW - 5 * 60_000, NOW, "en")).toBe("5 minutes ago");
  });

  it("says now for the last minute", () => {
    expect(lastExportAgo(NOW - 10_000, NOW, "en")).toBe("now");
  });
});
