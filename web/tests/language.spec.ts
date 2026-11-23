// The Hungarian pages carry no English UI text: every English string of
// content/en.json that has a Hungarian translation must not show up on /hu/
// (text, aria-label, title, alt, placeholder), the hidden menu and closed
// sections included. Game item names stay English until v2.5 and are not UI strings.
import { expect, type Page, test } from "@playwright/test";
import en from "../content/en.json" with { type: "json" };
import hu from "../content/hu.json" with { type: "json" };

type Tree = string | Tree[] | { [key: string]: Tree };

/** Pieces of the English strings that differ in Hungarian, long enough not to be a name. */
function englishPieces(a: Tree, b: Tree, out: Set<string> = new Set()): Set<string> {
  if (typeof a === "string") {
    if (a !== b) {
      for (const piece of a.split(/\{\w+\}/)) {
        const p = piece.trim().replace(/[.:,;]$/, "");
        if (p.length >= 12 && p.includes(" ")) out.add(p);
      }
    }
  } else if (Array.isArray(a)) {
    a.forEach((x, i) => englishPieces(x, (b as Tree[])[i], out));
  } else {
    for (const k of Object.keys(a)) englishPieces(a[k], (b as Record<string, Tree>)[k], out);
  }
  return out;
}

const PIECES = [...englishPieces(en as Tree, hu as Tree)];

async function pageText(page: Page): Promise<string> {
  return page.evaluate(() => {
    const parts: string[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.parentElement?.closest("script, style, template")) parts.push(n.textContent ?? "");
    }
    for (const el of document.querySelectorAll("[aria-label], [title], [alt], [placeholder]")) {
      for (const a of ["aria-label", "title", "alt", "placeholder"]) parts.push(el.getAttribute(a) ?? "");
    }
    return parts.join("\n").replace(/\s+/g, " ");
  });
}

async function expectHungarian(page: Page) {
  const text = await pageText(page);
  expect(PIECES.filter((p) => text.includes(p))).toEqual([]);
}

test.describe("Hungarian pages have no English UI text", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== "desktop", "the text is the same on every screen size");
  });

  test("the check knows the English strings", () => {
    expect(PIECES.length).toBeGreaterThan(50);
  });

  test("the check finds English text on an English page", async ({ page }) => {
    await page.goto("profiles/");
    const text = await pageText(page);
    expect(PIECES.filter((p) => text.includes(p)).length).toBeGreaterThan(3);
  });

  for (const path of ["hu/", "hu/how-it-works/", "hu/usage/"]) {
    test(path, async ({ page }) => {
      await page.goto(path);
      await expectHungarian(page);
    });
  }

  test("hu/levels/<n>/ and its plan", async ({ page }) => {
    await page.goto("hu/");
    const href = await page.getByTestId("level-card").last().getAttribute("href");
    await page.goto(href!);
    await expectHungarian(page);
    await page.goto(`${href}plan/`);
    await expectHungarian(page);
  });

  test("hu/profiles/ with a farm profile", async ({ page }) => {
    await page.goto("hu/profiles/");
    await expectHungarian(page);
    const form = page.getByTestId("new-profile");
    await form.getByRole("textbox", { name: "Név" }).fill("Magyar");
    await form.getByRole("spinbutton", { name: "Szint" }).fill("60");
    await form.getByRole("button", { name: "Létrehozás" }).click();
    await expect(page.getByTestId("profile-form")).toBeVisible();
    await expectHungarian(page);
  });
});
