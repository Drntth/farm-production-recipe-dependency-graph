import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { PLACEHOLDER_ID, drawingFor, drawingIds } from "./item-drawings";

const UI_DESIGN = fileURLToPath(new URL("../../../docs/ui-design.md", import.meta.url));
const ITEMS_DIR = fileURLToPath(new URL("../assets/items/", import.meta.url));

/** Ids in the "First round" table of docs/ui-design.md (the backticked names of its rows). */
function firstRoundIds(): string[] {
  const md = readFileSync(UI_DESIGN, "utf8");
  const section = md.slice(md.indexOf("First round (v2.5)"), md.indexOf("Missing after v2.5"));
  return [...section.matchAll(/^\|[^\n]*$/gm)]
    .map((m) => m[0])
    .filter((row) => /`[a-z_]+`/.test(row) && !row.startsWith("| Unlock"))
    .flatMap((row) => [...row.matchAll(/`([a-z_]+)`/g)].map((m) => m[1]));
}

const SVG_NS = "http://www.w3.org/2000/svg";
const FILL_OR_STROKE = /^(none|#[0-9a-fA-F]{6}|var\(--[a-z0-9-]+, #[0-9a-fA-F]{6}\))$/;
const PALETTE = ["outline", "wood", "soil", "grass", "wheat", "sky", "water", "accent", "accent-2", "gold"];

/**
 * Strict well-formedness check without a DOM: every tag is matched and closed in order,
 * the document has exactly one root, and no text or stray `<` / `&` is left outside tags.
 */
function parseStrict(xml: string): { name: string; attrs: Record<string, string> }[] {
  const body = xml.replace(/<\?xml[^>]*\?>/, "").replace(/<!--[\s\S]*?-->/g, "");
  const tagRe = /<(\/?)([A-Za-z][\w.-]*)((?:\s+[A-Za-z_:][\w:.-]*\s*=\s*"[^"<]*")*)\s*(\/?)>/g;
  const stack: string[] = [];
  const elements: { name: string; attrs: Record<string, string> }[] = [];
  let rootClosed = false;
  for (const m of body.matchAll(tagRe)) {
    const [, closing, name, attrText, selfClosing] = m;
    if (closing) {
      expect(stack.pop(), `closing </${name}>`).toBe(name);
      if (stack.length === 0) rootClosed = true;
      continue;
    }
    expect(rootClosed, `element <${name}> after the root`).toBe(false);
    const attrs: Record<string, string> = {};
    for (const a of attrText.matchAll(/([A-Za-z_:][\w:.-]*)\s*=\s*"([^"<]*)"/g)) attrs[a[1]] = a[2];
    elements.push({ name, attrs });
    if (!selfClosing) stack.push(name);
    else if (stack.length === 0) rootClosed = true;
  }
  expect(stack, "unclosed elements").toEqual([]);
  expect(body.replace(tagRe, "").replace(/\s+/g, ""), "text or stray markup outside tags").toBe("");
  return elements;
}

describe("item drawings", () => {
  const files = readdirSync(ITEMS_DIR).filter((f) => f.endsWith(".svg"));

  it("has a drawing for each of the 28 first-round ids", () => {
    const ids = firstRoundIds();
    expect(ids).toHaveLength(28);
    for (const id of ids) expect(files, `${id}.svg`).toContain(`${id}.svg`);
  });

  it("has a neutral placeholder drawing", () => {
    expect(files).toContain(`${PLACEHOLDER_ID}.svg`);
  });

  it.each(files)("%s is a well-formed SVG with a 24 x 24 viewBox", (file) => {
    const svg = readFileSync(ITEMS_DIR + file, "utf8");
    const elements = parseStrict(svg);
    expect(elements[0].name).toBe("svg");
    expect(elements[0].attrs.viewBox).toBe("0 0 24 24");
    expect(elements[0].attrs.xmlns).toBe(SVG_NS);
  });

  it.each(files)("%s has no image, text, script, links, data URIs or raster", (file) => {
    const svg = readFileSync(ITEMS_DIR + file, "utf8");
    const names = parseStrict(svg).map((e) => e.name);
    for (const forbidden of ["image", "text", "tspan", "script", "foreignObject", "style", "use"]) {
      expect(names, `<${forbidden}>`).not.toContain(forbidden);
    }
    expect(svg).not.toMatch(/href\s*=/);
    expect(svg).not.toMatch(/data:/i);
    // the SVG namespace URI is not a link
    expect(svg.replace(SVG_NS, "")).not.toMatch(/https?:/i);
    expect(svg).not.toMatch(/@import|<!ENTITY|<!DOCTYPE/i);
  });

  it.each(files)("%s has no ids and no url(#…) references (inline drawings share the page's ids)", (file) => {
    const svg = readFileSync(ITEMS_DIR + file, "utf8");
    expect(parseStrict(svg).filter((e) => "id" in e.attrs)).toEqual([]);
    expect(svg).not.toMatch(/url\(\s*#/);
  });

  it.each(files)("%s takes its outline from --outline, never from --fg", (file) => {
    const svg = readFileSync(ITEMS_DIR + file, "utf8");
    expect(svg).not.toMatch(/var\(--fg/);
    expect(svg).toMatch(/var\(--outline, #2a2116\)/);
  });

  it.each(files)("%s uses only outline, palette variables with fallbacks, or none", (file) => {
    const svg = readFileSync(ITEMS_DIR + file, "utf8");
    // colours as attributes or as style declarations (CSS variables work only in the style form)
    const values: string[] = [];
    for (const e of parseStrict(svg)) {
      for (const key of ["fill", "stroke"]) if (e.attrs[key] !== undefined) values.push(e.attrs[key]);
      for (const d of (e.attrs.style ?? "").matchAll(/(fill|stroke)\s*:\s*([^;]+)/g)) values.push(d[2].trim());
    }
    for (const value of values) {
      expect(value, `${file}`).toMatch(FILL_OR_STROKE);
      const v = value.match(/^var\(--([a-z0-9-]+),/);
      if (v) expect(PALETTE, `${file}`).toContain(v[1]);
    }
  });
});

describe("drawingFor", () => {
  it("returns the own drawing for a known id", () => {
    const drawing = drawingFor("field");
    expect(drawing.placeholder).toBe(false);
    expect(drawing.svg).toContain("<svg");
  });

  it("falls back to the placeholder for an unknown id", () => {
    const drawing = drawingFor("no_such_item");
    expect(drawing.placeholder).toBe(true);
    expect(drawing.svg).toBe(drawingFor(PLACEHOLDER_ID).svg);
  });

  it("lists the ids without the placeholder", () => {
    expect(drawingIds()).toHaveLength(readdirSync(ITEMS_DIR).length - 1);
    expect(drawingIds()).not.toContain(PLACEHOLDER_ID);
  });
});
