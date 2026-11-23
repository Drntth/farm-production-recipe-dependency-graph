// Helpers without Node APIs, so client islands can import them too (data.ts
// reads files at build time and re-exports these).

/** `apple_juice` → `Apple juice` (the level JSON carries ids only). */
export function label(id: string): string {
  const text = id.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** A path below the site base (GitHub Pages serves the site in a subdirectory). */
export function url(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}/${path.replace(/^\//, "")}`;
}
