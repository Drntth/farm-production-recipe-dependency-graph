// Accessibility of the pages (WCAG 2.2 A and AA, axe-core): home, a level page (layout and plan
// tab, taken from the built links), How it works, Usage and My farms; English and Hungarian,
// light and dark, phone and desktop. Also: main controls at least 44 x 44 CSS px on the phone,
// and no motion under prefers-reduced-motion. Exceptions are listed in EXCEPTIONS with a reason.
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** A rule switched off for one page of one language: `page` is the name used in pagesOf(), `rule` an axe rule id. */
interface Exception {
  lang: Lang;
  page: string;
  rule: string;
  reason: string;
}

// Empty: every finding of the pages is fixed. Add an entry only with a reason, and a TODO when temporary.
const EXCEPTIONS: Exception[] = [];

type Lang = "en" | "hu";
const HOME: Record<Lang, string> = { en: "./", hu: "hu/" };
const OTHER: Record<Lang, string[]> = {
  en: ["how-it-works/", "usage/", "profiles/"],
  hu: ["hu/how-it-works/", "hu/usage/", "hu/profiles/"],
};

/** The first level card of the home page: the level is never hard-coded. */
async function levelHref(page: Page, lang: Lang): Promise<string> {
  await page.goto(HOME[lang]);
  const href = await page.getByTestId("level-card").first().getAttribute("href");
  expect(href).toBeTruthy();
  return href!;
}

async function pagesOf(page: Page, lang: Lang): Promise<Array<{ name: string; path: string }>> {
  const level = await levelHref(page, lang);
  return [
    { name: "home", path: HOME[lang] },
    { name: "level", path: level },
    { name: "level plan", path: `${level}plan/` },
    ...OTHER[lang].map((path) => ({ name: path.replace(/\/$/, ""), path })),
  ];
}

function exceptionsFor(lang: Lang, name: string): string[] {
  return EXCEPTIONS.filter((e) => e.lang === lang && e.page === name).map((e) => e.rule);
}

function describeViolations(violations: Array<{ id: string; impact?: string | null; nodes: { target: unknown[] }[] }>) {
  return violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.nodes
        .slice(0, 3)
        .map((n) => n.target.join(" "))
        .join(" | ")}`,
  );
}

for (const lang of ["en", "hu"] as const) {
  for (const theme of ["light", "dark"] as const) {
    test.describe(`axe: ${lang}, ${theme} theme`, () => {
      test.beforeEach(async ({ page }) => {
        // the theme is read from localStorage before first paint (see Base.astro)
        await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
        // reveal animations are off, so the scan sees the final, visible content
        await page.emulateMedia({ reducedMotion: "reduce" });
      });

      test.beforeEach(({}, info) => {
        test.skip(info.project.name === "tablet", "the phone and desktop projects cover the layouts");
      });

      test(`every page has no WCAG 2.2 A/AA violation`, async ({ page }) => {
        // six scans with axe: slower than the default 30 s when the projects run in parallel
        test.setTimeout(180_000);
        // one report for all pages: a failing page does not hide the others
        const failures: Record<string, string[]> = {};
        for (const p of await pagesOf(page, lang)) {
          await page.goto(p.path);
          await expect(page.locator("main")).toBeVisible();
          const results = await new AxeBuilder({ page })
            .withTags(TAGS)
            .disableRules(exceptionsFor(lang, p.name))
            .analyze();
          const found = describeViolations(results.violations);
          if (found.length > 0) failures[p.name] = found;
        }
        expect(failures, `${lang}, ${theme} theme`).toEqual({});
      });
    });
  }
}

test.describe("controls and motion", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name === "tablet", "the phone and desktop projects cover the layouts");
  });

  test("main controls are at least 44 x 44 CSS px on the phone", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "touch targets are checked on the phone");
    const level = await levelHref(page, "en");
    const controls =
      "header button, header a.icon-btn, main button, main select, main a.btn, main a.icon-btn, main a.nav-link, main a.tile";
    for (const path of [HOME.en, level, `${level}plan/`, "how-it-works/", "usage/"]) {
      await page.goto(path);
      const boxes = await page.locator(controls).evaluateAll((els) =>
        els
          .filter((el) => (el as HTMLElement).offsetParent !== null)
          .map((el) => {
            const r = el.getBoundingClientRect();
            return {
              name: (el.textContent ?? el.getAttribute("aria-label") ?? el.tagName).trim().slice(0, 40),
              w: r.width,
              h: r.height,
            };
          }),
      );
      expect(boxes.length, `controls on ${path}`).toBeGreaterThan(0);
      const small = boxes.filter((b) => b.w < 44 || b.h < 44);
      expect(small, `controls below 44 px on ${path}`).toEqual([]);
    }
  });

  test("prefers-reduced-motion turns the motion off", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const level = await levelHref(page, "en");
    for (const path of [HOME.en, level, `${level}plan/`]) {
      await page.goto(path);
      const moving = await page.evaluate(() => {
        const out: string[] = [];
        for (const el of document.querySelectorAll<HTMLElement>("*")) {
          const s = getComputedStyle(el);
          const animated = s.animationName !== "none" && parseFloat(s.animationDuration) > 0;
          const moves = parseFloat(s.transitionDuration) > 0 && /transform|opacity|all/.test(s.transitionProperty);
          if (animated || moves) out.push(`${el.tagName.toLowerCase()}.${el.className}`.slice(0, 60));
        }
        return out.slice(0, 10);
      });
      expect(moving, `moving elements on ${path}`).toEqual([]);
      expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe("auto");
    }
    await page.goto(HOME.en);
    const hidden = await page
      .locator(".reveal")
      .evaluateAll((els) => els.filter((el) => getComputedStyle(el).opacity !== "1").length);
    expect(hidden).toBe(0);
  });
});
