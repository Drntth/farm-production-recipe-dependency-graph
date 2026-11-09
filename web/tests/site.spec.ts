// The level pages load from static files only (no Pyodide), show the layout,
// the login steps, the plan and the legal footer, and fit a phone screen,
// in English (site root) and Hungarian (/hu/), light and dark; the main menu
// (hamburger on a phone) reaches the "How it works" and "Usage" pages.
import { expect, type Page, test } from "@playwright/test";

const FAN_POLICY = "https://supercell.com/en/fan-content-policy/";
const FAN_TEXT = "This material is unofficial and is not endorsed by Supercell.";

async function firstLevel(page: Page, home = "./"): Promise<string> {
  await page.goto(home);
  const link = page.getByTestId("level-card").first();
  const href = await link.getAttribute("href");
  expect(href).toBeTruthy();
  return href!;
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

test("home page lists the levels", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Farm layout and production plan for every level");
  await expect(page.getByTestId("level-card").first()).toBeVisible();
  await noHorizontalScroll(page);
});

test("Hungarian home page", async ({ page }) => {
  await page.goto("hu/");
  await expect(page.locator("html")).toHaveAttribute("lang", "hu");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Farmelrendezés és termelési terv minden szintre");
  await expect(page.getByTestId("level-card").first()).toHaveAttribute("href", /\/hu\/levels\/\d+\/$/);
  await noHorizontalScroll(page);
});

test("every page has the Fan Content Policy notice, the data licence, the portfolio link and the versions", async ({ page }) => {
  const pages = ["./", await firstLevel(page), "hu/", await firstLevel(page, "hu/"), "how-it-works/", "hu/usage/"];
  for (const path of pages) {
    await page.goto(path);
    const footer = page.locator("footer");
    // the policy's own wording, in English on the Hungarian pages too
    await expect(footer).toContainText(FAN_TEXT);
    await expect(footer.locator(`a[href="${FAN_POLICY}"]`)).toBeVisible();
    await expect(footer.getByRole("link", { name: "CC BY-SA 3.0" })).toBeVisible();
    await expect(footer.getByTestId("portfolio-link")).toHaveAttribute("href", /^https:\/\/drntth\.github\.io\//);
    await expect(footer.getByTestId("versions")).toContainText(/(Game|Játék) .+(Planner|Tervező) /);
  }
});

for (const home of ["./", "hu/"]) {
  test(`level page shows layout, logins and plan without Pyodide (${home})`, async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (r) => requests.push(r.url()));
    const href = await firstLevel(page, home);
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/^(Level \d+|\d+\. szint)$/);
    await expect(page.getByTestId("key-figures")).toBeVisible();
    await expect(page.getByTestId("blocks").locator("li").first()).toBeVisible();
    await expect(page.locator("ol.actions > li").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: home === "./" ? "Plan details" : "A terv részletei" })).toBeVisible();
    await expect(page.getByTestId("next-level")).toHaveAttribute("href", /\/levels\/\d+\/$/);
    const img = page.locator("img.layout");
    await img.scrollIntoViewIfNeeded();
    await expect(img).toBeVisible();
    expect(await img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true);
    expect(requests.filter((u) => /pyodide/i.test(u))).toEqual([]);
    const origins = new Set(requests.map((u) => new URL(u).origin));
    expect([...origins]).toEqual([new URL(page.url()).origin]);
    await noHorizontalScroll(page);
  });
}

test("level picker opens the chosen level in the page's language", async ({ page }) => {
  for (const [home, show, title] of [
    ["./", "Show", (n: string) => `Level ${n}`],
    ["hu/", "Mutasd", (n: string) => `${n}. szint`],
  ] as const) {
    await page.goto(home);
    const last = await page.locator("#level-select option").last().getAttribute("value");
    await page.selectOption("#level-select", last!);
    await page.getByRole("button", { name: show }).click();
    await expect(page).toHaveURL(new RegExp(`${home === "hu/" ? "/hu" : ""}/levels/${last}/$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title(last!));
  }
});

test("the level switch on a level page opens the chosen and the next level", async ({ page }) => {
  await page.goto(await firstLevel(page, "hu/"));
  const last = await page.locator("#level-select option").last().getAttribute("value");
  await page.selectOption("#level-select", last!);
  await expect(page).toHaveURL(new RegExp(`/hu/levels/${last}/$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`${last}. szint`);
  await expect(page.getByTestId("next-level")).toHaveCount(0);
  await page.goto(await firstLevel(page));
  const heading = await page.getByRole("heading", { level: 1 }).textContent();
  await page.getByRole("link", { name: /^Next level: / }).click();
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(heading!);
});

test("main menu reaches every page; a phone gets a hamburger", async ({ page, isMobile }) => {
  for (const [home, how, usage] of [
    ["./", "How it works", "Usage"],
    ["hu/", "Hogyan működik", "Használat"],
  ] as const) {
    for (const [name, url] of [
      [how, /\/how-it-works\/$/],
      [usage, /\/usage\/$/],
    ] as const) {
      await page.goto(home);
      const header = page.locator("header");
      if (isMobile) {
        await expect(header.locator(".nav-pill")).toBeHidden();
        const toggle = page.locator("#menu-toggle");
        await toggle.click();
        await expect(toggle).toHaveAttribute("aria-expanded", "true");
        await page.locator("#mobile-menu").getByRole("link", { name }).click();
      } else {
        await expect(page.locator("#menu-toggle")).toBeHidden();
        await header.locator(".nav-pill").getByRole("link", { name }).click();
      }
      await expect(page).toHaveURL(url);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
      await expect(header.locator('[aria-current="page"]').first()).toContainText(name);
      await expect(page.locator("ol > li").first()).toBeVisible();
      await noHorizontalScroll(page);
    }
  }
});

test("language switch opens the same page in the other language", async ({ page }) => {
  const href = await firstLevel(page);
  await page.goto(href);
  await page.locator("a[data-lang-switch]").click();
  await expect(page).toHaveURL(new RegExp(`/hu${href.replace(/^.*?(\/levels\/)/, "$1")}$`));
  await expect(page.locator("html")).toHaveAttribute("lang", "hu");
  await page.locator("a[data-lang-switch]").click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
});

test("dark mode toggle is remembered and keeps the page readable", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("./");
  const html = page.locator("html");
  await expect(html).not.toHaveClass(/dark/);
  await page.locator("#theme-toggle").click();
  await expect(html).toHaveClass(/dark/);
  for (const path of ["hu/", await firstLevel(page)]) {
    await page.goto(path);
    await expect(html).toHaveClass(/dark/);
    await noHorizontalScroll(page);
  }
  await page.locator("#theme-toggle").click();
  await expect(html).not.toHaveClass(/dark/);
});
