// The level pages load from static files only (no Pyodide), show the layout
// (a pan / zoom farm view; a still map without JavaScript) and the plan on two
// tabs (never both on one page), the legal footer, and fit a phone screen, in English (site root) and Hungarian (/hu/), light and dark; the
// main menu (hamburger on a phone) reaches the "How it works" and "Usage" pages;
// sections fade in on scroll, except under reduced motion or without JavaScript.
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

test("every page has the Fan Content Policy notice, the data licence, the portfolio link and the versions", async ({
  page,
}) => {
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
  test(`level page: layout and plan tabs without Pyodide, never both on one page (${home})`, async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (r) => requests.push(r.url()));
    const href = await firstLevel(page, home);
    const planSummary = home === "./" ? "Plan summary" : "A terv összefoglalója";
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/^(Level \d+|\d+\. szint)$/);
    await expect(page.getByTestId("key-figures")).toBeVisible();
    const tabs = page.getByTestId("tabs").getByRole("link");
    await expect(tabs).toHaveCount(2);
    await expect(tabs.first()).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("blocks").locator("li").first()).toBeVisible();
    await expect(page.getByTestId("plan-brief").locator("dd")).toHaveCount(3);
    await expect(page.getByTestId("login-groups")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: planSummary })).toHaveCount(0);
    await expect(page.getByTestId("next-level")).toHaveAttribute("href", /\/levels\/\d+\/$/);
    const map = page.getByTestId("farm-view");
    await map.scrollIntoViewIfNeeded();
    await expect(map).toBeVisible();
    await expect(map.locator("g.fv-block").first()).toBeVisible();
    const svg = await page.getByTestId("layout-download").getAttribute("href");
    expect(svg).toMatch(/\/layouts\/\d+\.svg$/);
    expect((await page.request.get(svg!)).ok()).toBe(true);
    await noHorizontalScroll(page);

    await page.getByTestId("plan-brief").getByRole("link").click();
    await expect(page).toHaveURL(/\/levels\/\d+\/plan\/$/);
    await expect(tabs.last()).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("login-groups").locator("details").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: planSummary })).toBeVisible();
    await expect(page.getByTestId("blocks")).toHaveCount(0);
    await expect(page.getByTestId("farm-view")).toHaveCount(0);
    await expect(page.getByTestId("next-level")).toHaveAttribute("href", /\/levels\/\d+\/plan\/$/);
    await noHorizontalScroll(page);
    await tabs.first().click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));

    expect(requests.filter((u) => /pyodide/i.test(u))).toEqual([]);
    const origins = new Set(requests.map((u) => new URL(u).origin));
    expect([...origins]).toEqual([new URL(page.url()).origin]);
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

test("plan tab: summary and login times first, then the login actions per building, collapsed", async ({ page }) => {
  await page.goto(`${await firstLevel(page)}plan/`);
  const summary = page.getByTestId("plan-summary");
  const groups = page.getByTestId("login-groups");
  const above = await summary.boundingBox();
  const below = await groups.boundingBox();
  expect(above!.y).toBeLessThan(below!.y);
  await expect(summary.getByTestId("login-times").locator("li").first()).toHaveText(/^\d\d:\d\d$/);

  const details = groups.locator("details");
  expect(await details.count()).toBeGreaterThan(1);
  expect(await details.evaluateAll((all) => all.filter((d) => (d as HTMLDetailsElement).open).length)).toBe(0);
  // one group per building: no building twice
  const ids = await details.evaluateAll((all) => all.map((d) => d.getAttribute("data-group")));
  expect(new Set(ids).size).toBe(ids.length);

  const machine = groups.locator("details", { has: page.locator(".item") }).first();
  const items = machine.locator(".item").first();
  await expect(items).toBeHidden();
  await machine.locator("summary").click();
  await expect(machine).toHaveAttribute("open", "");
  await expect(items).toBeVisible();
  await machine.locator("summary").press("Enter");
  await expect(machine).not.toHaveAttribute("open", "");
  await noHorizontalScroll(page);
});

test("the level switch stays on the plan tab", async ({ page }) => {
  await page.goto(`${await firstLevel(page)}plan/`);
  const last = await page.locator("#level-select option").last().getAttribute("value");
  await page.selectOption("#level-select", last!);
  await expect(page).toHaveURL(new RegExp(`/levels/${last}/plan/$`));
  await expect(page.getByTestId("tabs").getByRole("link").last()).toHaveAttribute("aria-current", "page");
  await page.locator("a[data-lang-switch]").click();
  await expect(page).toHaveURL(new RegExp(`/hu/levels/${last}/plan/$`));
});

async function viewBox(page: Page): Promise<number[]> {
  const value = await page.getByTestId("farm-view").getAttribute("viewBox");
  return value!.split(" ").map(Number);
}

/** Waits until the farm view's viewBox differs from *before*; returns the new one. */
async function changed(page: Page, before: number[], what: (b: number[], a: number[]) => boolean): Promise<number[]> {
  await expect.poll(async () => what(before, await viewBox(page))).toBe(true);
  return viewBox(page);
}

const zoomedIn = (b: number[], a: number[]) => a[2] < b[2] - 1e-6;
const zoomedOut = (b: number[], a: number[]) => a[2] > b[2] + 1e-6;
const moved = (b: number[], a: number[]) => Math.abs(a[2] - b[2]) < 1e-6 && (a[0] !== b[0] || a[1] !== b[1]);

test("the farm view zooms and moves by mouse, touch, buttons and keys", async ({ page }) => {
  await page.goto(await firstLevel(page));
  const controls = page.getByTestId("farm-controls");
  await expect(controls).toBeVisible();
  const box = page.getByRole("group", { name: /^Farm layout for level \d+$/ });
  await box.scrollIntoViewIfNeeded();
  const home = await viewBox(page);
  const r = (await box.boundingBox())!;
  const cx = r.x + r.width / 2;
  const cy = r.y + r.height / 2;

  // buttons
  let v = home;
  await controls.getByRole("button", { name: "Zoom in" }).click();
  v = await changed(page, v, zoomedIn);
  await controls.getByRole("button", { name: "Zoom out" }).click();
  v = await changed(page, v, zoomedOut);
  await controls.getByRole("button", { name: "Reset the view" }).click();
  await expect.poll(() => viewBox(page)).toEqual(home);

  // mouse: wheel zooms, drag moves
  await page.mouse.move(cx, cy);
  await page.mouse.wheel(0, -300);
  v = await changed(page, home, zoomedIn);
  await page.mouse.down();
  await page.mouse.move(cx + 60, cy + 30, { steps: 5 });
  await page.mouse.up();
  v = await changed(page, v, moved);

  // touch: one finger moves, two fingers pinch
  const touch = (type: string, id: number, x: number, y: number) =>
    box.dispatchEvent(type, {
      pointerId: id,
      pointerType: "touch",
      isPrimary: id === 1,
      clientX: x,
      clientY: y,
      button: 0,
    });
  await touch("pointerdown", 1, cx, cy);
  await touch("pointermove", 1, cx - 40, cy);
  await touch("pointerup", 1, cx - 40, cy);
  v = await changed(page, v, moved);
  await touch("pointerdown", 1, cx - 20, cy);
  await touch("pointerdown", 2, cx + 20, cy);
  await touch("pointermove", 2, cx + 80, cy);
  await touch("pointerup", 2, cx + 80, cy);
  await touch("pointerup", 1, cx - 20, cy);
  v = await changed(page, v, zoomedIn);

  // keyboard: 0 resets, + / - zoom, arrows move
  await box.focus();
  await page.keyboard.press("0");
  await expect.poll(() => viewBox(page)).toEqual(home);
  await page.keyboard.press("+");
  v = await changed(page, home, zoomedIn);
  await page.keyboard.press("-");
  v = await changed(page, v, zoomedOut);
  await page.keyboard.press("ArrowRight");
  v = await changed(page, v, moved);
  await page.keyboard.press("ArrowUp");
  await changed(page, v, moved);
});

test("blocks: map and card highlight each other; selecting one zooms to it and opens its details", async ({ page }) => {
  await page.goto(await firstLevel(page));
  await expect(page.getByTestId("farm-controls")).toBeVisible();
  const map = page.getByTestId("farm-view");
  const blocks = map.locator("g.fv-block");
  const id = (await blocks.first().getAttribute("data-block"))!;
  const block = map.locator(`g[data-block="${id}"]`);
  const card = page.locator(`[data-card="${id}"]`);
  const button = card.getByRole("button");
  await expect(button).toHaveAttribute("aria-pressed", "false");

  // two-way highlight: card → map, map → card
  await card.hover();
  await expect(block).toHaveClass(/fv-hot/);
  await page.mouse.move(0, 0);
  await expect(block).not.toHaveClass(/fv-hot/);
  await block.scrollIntoViewIfNeeded();
  await block.locator("polygon.fv-frame").hover({ force: true });
  await expect(card).toHaveClass(/fv-hot/);

  // keyboard: Enter on the card selects, Esc closes and keeps the focus on the card
  const home = await viewBox(page);
  await button.focus();
  await expect(block).toHaveClass(/fv-hot/);
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-pressed", "true");
  const details = page.getByTestId("block-details");
  await expect(details).toBeVisible();
  await expect(details.getByRole("heading")).toHaveText((await button.textContent())!.trim());
  if ((await blocks.count()) > 1) await expect(blocks.nth(1)).toHaveClass(/fv-dim/);
  await changed(page, home, zoomedIn);
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  await expect(button).toBeFocused();
  await expect(blocks.nth(1)).not.toHaveClass(/fv-dim/);

  // a click on the map selects; × closes
  await page.getByRole("button", { name: "Reset the view" }).click();
  await block.locator("polygon.fv-frame").click({ force: true });
  await expect(details).toBeVisible();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await details.getByRole("button", { name: "Close the block details" }).click();
  await expect(details).toHaveCount(0);
  await expect(button).toHaveAttribute("aria-pressed", "false");

  // a drag that starts on a block moves the view, it does not select
  const r = (await block.locator("polygon.fv-frame").boundingBox())!;
  await page.mouse.move(r.x + r.width / 2, r.y + r.height / 2);
  await page.mouse.down();
  await page.mouse.move(r.x + r.width / 2 + 50, r.y + r.height / 2 + 20, { steps: 5 });
  await page.mouse.up();
  await expect(details).toHaveCount(0);
});

test("without JavaScript the farm view is a still map with the block cards and a download link", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(await firstLevel(page));
  await expect(page.getByTestId("farm-view")).toBeVisible();
  await expect(page.getByTestId("farm-view").locator("g.fv-block").first()).toBeAttached();
  await expect(page.getByTestId("farm-controls")).toHaveCount(0);
  await expect(page.getByTestId("blocks").locator("li").first()).toBeVisible();
  await expect(page.getByTestId("layout-download")).toBeVisible();
  await expect(page.getByTestId("plan-brief")).toHaveCSS("opacity", "1");
  await context.close();
});

test("sections below the fold fade in when scrolled to, at once under reduced motion", async ({ page }) => {
  const href = await firstLevel(page);
  await page.goto(href);
  const last = page.locator(".reveal").last();
  await expect(last).not.toBeInViewport();
  await expect(last).not.toHaveClass(/is-visible/);
  await expect(last).toHaveCSS("opacity", "0");
  await last.scrollIntoViewIfNeeded();
  await expect(last).toHaveClass(/is-visible/);
  await expect(last).toHaveCSS("opacity", "1");

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(href);
  await expect(page.locator(".reveal").last()).toHaveCSS("opacity", "1");
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
