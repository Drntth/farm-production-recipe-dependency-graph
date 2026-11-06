// The level pages load from static files only (no Pyodide), show the plan,
// the login steps, the layout and the legal footer, and fit a phone screen.
import { expect, type Page, test } from "@playwright/test";

const FAN_POLICY = "https://supercell.com/en/fan-content-policy/";

async function firstLevel(page: Page): Promise<string> {
  await page.goto("./");
  const link = page.locator("tbody a").first();
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
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Level recommendations");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await noHorizontalScroll(page);
});

test("every page has the Fan Content Policy notice and the data licence", async ({ page }) => {
  for (const path of ["./", await firstLevel(page)]) {
    await page.goto(path);
    const footer = page.locator("footer");
    await expect(footer).toContainText("This material is unofficial and is not endorsed by Supercell.");
    await expect(footer.locator(`a[href="${FAN_POLICY}"]`)).toBeVisible();
    await expect(footer.getByRole("link", { name: "CC BY-SA 3.0" })).toBeVisible();
  }
});

test("level page shows plan, logins and layout without Pyodide", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  const href = await firstLevel(page);
  await page.goto(href);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/^Level \d+$/);
  await expect(page.getByRole("heading", { name: "Plan" })).toBeVisible();
  await expect(page.locator("ol.actions li").first()).toBeVisible();
  const img = page.locator("img.layout");
  await img.scrollIntoViewIfNeeded();
  await expect(img).toBeVisible();
  expect(await img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true);
  expect(requests.filter((u) => /pyodide/i.test(u))).toEqual([]);
  const origins = new Set(requests.map((u) => new URL(u).origin));
  expect([...origins]).toEqual([new URL(page.url()).origin]);
  await noHorizontalScroll(page);
});

test("level picker opens the chosen level", async ({ page }) => {
  await page.goto("./");
  const options = page.locator("#level-select option");
  const last = await options.last().getAttribute("value");
  await page.selectOption("#level-select", last!);
  await page.getByRole("button", { name: "Show" }).click();
  await expect(page).toHaveURL(new RegExp(`/levels/${last}/$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`Level ${last}`);
});
