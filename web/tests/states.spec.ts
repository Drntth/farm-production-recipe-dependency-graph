// What the pages do when a script fails to load (route.abort). The home and level pages read
// their data at build time (no runtime fetch), so there is no loading or empty state to show:
// a failed island script must leave the content and the plain links working. The My farms
// page's states (loading, error) are tested with its own spec (profiles.spec.ts).
import { expect, type Page, test } from "@playwright/test";

async function firstLevelHref(page: Page): Promise<string> {
  await page.goto("./");
  const href = await page.getByTestId("level-card").first().getAttribute("href");
  expect(href).toBeTruthy();
  return href!;
}

test.describe("pages whose island script fails to load", () => {
  test.beforeEach(({}, info) => {
    test.skip(info.project.name === "tablet", "the phone and desktop projects cover the layouts");
  });

  test("level page: the farm view script fails, the figures, the tabs and the plan link stay", async ({ page }) => {
    await page.route(/\/_astro\/FarmView\.[^/]+\.js$/, (route) => route.abort());
    const href = await firstLevelHref(page);
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByTestId("key-figures")).toBeVisible();
    await expect(page.getByTestId("tabs").getByRole("link")).toHaveCount(2);
    await page.getByTestId("plan-brief").getByRole("link").click();
    await expect(page).toHaveURL(/\/plan\/$/);
    await expect(page.getByTestId("login-groups").locator("details").first()).toBeVisible();
  });

  test("level page: the level picker script fails, the previous and next links still navigate", async ({ page }) => {
    await page.route(/\/_astro\/LevelPicker\.[^/]+\.js$/, (route) => route.abort());
    const href = await firstLevelHref(page);
    await page.goto(href);
    await expect(page.getByTestId("next-level")).toBeVisible();
    await page.getByTestId("next-level").click();
    await expect(page).toHaveURL(/\/levels\/\d+\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("home page: the level picker script fails, the level cards still list and link", async ({ page }) => {
    await page.route(/\/_astro\/LevelPicker\.[^/]+\.js$/, (route) => route.abort());
    await page.goto("./");
    const cards = page.getByTestId("level-card");
    expect(await cards.count()).toBeGreaterThan(0);
    await cards.first().click();
    await expect(page).toHaveURL(/\/levels\/\d+\/$/);
  });

  test("plan tab without any script: the login groups open and close natively", async ({ page }) => {
    await page.route(/\/_astro\/[^/]+\.js$/, (route) => route.abort());
    const href = await firstLevelHref(page);
    await page.goto(`${href}plan/`);
    const group = page.getByTestId("login-groups").locator("details").first();
    await expect(group).not.toHaveAttribute("open", "");
    await group.locator("summary").click();
    await expect(group).toHaveAttribute("open", "");
    await group.locator("summary").click();
    await expect(group).not.toHaveAttribute("open", "");
  });
});
