import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { LUCIDE_ICONS } from "./icon-data";
import { buildIconData, readLucideIcons } from "../../scripts/generate-icon-data.mjs";

const UI_DESIGN = fileURLToPath(new URL("../../../docs/ui-design.md", import.meta.url));
const ICON_DATA = fileURLToPath(new URL("./icon-data.ts", import.meta.url));

/** Lucide names listed in the "Concept icons and legend" table of docs/ui-design.md. */
function documentedIcons(): string[] {
  const md = readFileSync(UI_DESIGN, "utf8");
  const section = md.slice(md.indexOf("## Concept icons and legend"), md.indexOf("## Item drawings"));
  const names: string[] = [];
  for (const line of section.split("\n")) {
    const m = line.match(/^\|[^|]+\|\s*`([a-z0-9-]+)`\s*\|/);
    if (m) names.push(m[1]);
  }
  return names;
}

describe("Icon data", () => {
  it("lists exactly the concept icons of docs/ui-design.md", () => {
    expect(documentedIcons()).toHaveLength(16);
    expect(Object.keys(LUCIDE_ICONS).sort()).toEqual([...documentedIcons()].sort());
  });

  it("every icon exists in @iconify-json/lucide and has a non-empty body", () => {
    const lucide = readLucideIcons();
    for (const name of Object.keys(LUCIDE_ICONS)) {
      expect(lucide.icons[name], name).toBeDefined();
      expect(LUCIDE_ICONS[name as keyof typeof LUCIDE_ICONS].body.length, name).toBeGreaterThan(0);
    }
  });

  it("the generated icon-data.ts is in sync with its generator", () => {
    expect(readFileSync(ICON_DATA, "utf8")).toBe(buildIconData(readLucideIcons(), documentedIcons()));
  });
});
