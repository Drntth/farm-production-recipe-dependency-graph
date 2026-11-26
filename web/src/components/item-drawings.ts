// Own-made item drawings (src/assets/items/<id>.svg), loaded at build time as raw SVG text.
// A missing drawing falls back to the neutral placeholder.
const modules = import.meta.glob("../assets/items/*.svg", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export const PLACEHOLDER_ID = "placeholder";

const byId = new Map<string, string>();
for (const [path, svg] of Object.entries(modules)) {
  const id = path.slice(path.lastIndexOf("/") + 1).replace(/\.svg$/, "");
  byId.set(id, svg);
}

/** The drawing for a data id; `placeholder` is true when the id has none of its own. */
export function drawingFor(id: string): { svg: string; placeholder: boolean } {
  const own = byId.get(id);
  if (own !== undefined) return { svg: own, placeholder: false };
  return { svg: byId.get(PLACEHOLDER_ID) ?? "", placeholder: true };
}

/** Ids that have their own drawing (without the placeholder). */
export function drawingIds(): string[] {
  return [...byId.keys()].filter((id) => id !== PLACEHOLDER_ID);
}
