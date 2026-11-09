// Two languages: English at the site root, Hungarian under /hu/. Every UI string
// lives in content/<lang>.json with the same keys (tests/test_web_content.py);
// game item names come from the data and stay English.
import en from "../content/en.json";
import hu from "../content/hu.json";
import { url } from "./data";

export type Lang = "en" | "hu";
export const LANGS: Lang[] = ["en", "hu"];
export type Content = typeof en;

const CONTENT: Record<Lang, Content> = { en, hu };

export function content(lang: Lang): Content {
  return CONTENT[lang];
}

/** `{name}` placeholders → values: `fill("Level {n}", { n: 3 })`. */
export function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

/** A site path in one language: `localePath("hu", "levels/3/")` → `<base>/hu/levels/3/`. */
export function localePath(lang: Lang, path: string): string {
  const clean = path.replace(/^\//, "");
  return url(lang === "hu" ? `hu/${clean}` : clean);
}

/** The same page in the other language, from the current URL path. */
export function switchPath(pathname: string, to: Lang): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  let rest = pathname.startsWith(base) ? pathname.slice(base.length) : pathname;
  rest = rest.replace(/^\/hu(\/|$)/, "/");
  return localePath(to, rest);
}

export function hours(value: number, lang: Lang): string {
  const u = content(lang).units;
  const number = (n: number) => n.toLocaleString(lang === "hu" ? "hu-HU" : "en-GB", { maximumFractionDigits: 2 });
  return value < 1 ? fill(u.minutes, { n: Math.round(value * 60) }) : fill(u.hours, { n: number(value) });
}

export function number(value: number, lang: Lang, digits = 1): string {
  return value.toLocaleString(lang === "hu" ? "hu-HU" : "en-GB", { maximumFractionDigits: digits });
}
