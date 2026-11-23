// "My farms": farm profiles in IndexedDB (kept over a reload), a form that follows
// the level, JSON export → import unchanged, no Pyodide before the first
// calculation; then (network: Pyodide from the CDN) two profiles get their own plans.
import { expect, type Page, test } from "@playwright/test";

async function createProfile(page: Page, name: string, level: number) {
  const form = page.getByTestId("new-profile");
  await form.getByRole("textbox", { name: /^(Name|Név)$/ }).fill(name);
  await form.getByRole("spinbutton", { name: /^(Level|Szint)$/ }).fill(String(level));
  await form.getByRole("button", { name: /^(Create|Létrehozás)$/ }).click();
  await expect(page.getByTestId("profile-tabs").getByRole("tab", { name: new RegExp(`^${name} `) })).toHaveAttribute(
    "aria-selected",
    "true",
  );
}

test("two farm profiles side by side, kept over a reload; the form follows the level", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("profiles/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("My farms");
  await createProfile(page, "Small", 10);
  await createProfile(page, "Big", 40);

  const form = page.getByTestId("profile-form");
  // a level-40 location missing at level 10
  const rows40 = await form.locator("tr[data-location]").count();
  await page
    .getByTestId("profile-tabs")
    .getByRole("tab", { name: /^Small / })
    .click();
  await expect(form.getByRole("heading", { level: 2 })).toHaveText("Small");
  expect(await form.locator("tr[data-location]").count()).toBeLessThan(rows40);

  // empty = level default (the placeholder); a value is stored
  const fields = page.getByTestId("player-fields_owned");
  await expect(fields).toHaveValue("");
  expect(Number(await fields.getAttribute("placeholder"))).toBeGreaterThan(0);
  await fields.fill("7");
  await fields.blur();

  await page.reload();
  const tabs = page.getByTestId("profile-tabs").getByRole("tab");
  await expect(tabs).toHaveCount(2);
  await expect(tabs.filter({ hasText: /^Small / })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("player-fields_owned")).toHaveValue("7");

  await page.getByTestId("level").fill("12");
  await page.getByTestId("level").blur();
  await expect(tabs.filter({ hasText: /^Small · Level 12$/ })).toBeVisible();
  expect(requests.filter((u) => /pyodide/i.test(u))).toEqual([]);
});

test("an exported farm profile imports unchanged", async ({ page }) => {
  await page.goto("hu/profiles/");
  await createProfile(page, "Export", 25);
  const beehives = page.locator('tr[data-location="beehive_tree"] input[data-field="beehives"]');
  if (await beehives.count()) {
    await beehives.fill("2");
    await beehives.blur();
  }
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export").click()]);
  const text = await (await download.createReadStream()).toArray().then((c) => Buffer.concat(c).toString("utf-8"));
  const exported = JSON.parse(text);
  expect(exported.name).toBe("Export");
  expect(exported.player.level).toBe(25);

  await page
    .getByTestId("import")
    .setInputFiles({ name: "x.json", mimeType: "application/json", buffer: Buffer.from(text) });
  await expect(page.getByTestId("profile-tabs").getByRole("tab")).toHaveCount(2);
  const [again] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export").click()]);
  const text2 = await (await again.createReadStream()).toArray().then((c) => Buffer.concat(c).toString("utf-8"));
  expect(text2).toBe(text);

  await page
    .getByTestId("import")
    .setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from("{") });
  await expect(page.getByRole("alert")).toContainText("Az import nem sikerült");
});

test("two farm profiles give their own plans (Pyodide)", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the Pyodide download runs once, on desktop");
  test.setTimeout(180_000);
  await page.goto("profiles/");
  await createProfile(page, "Early", 15);
  await page.getByTestId("calculate").click();
  const plan = page.getByTestId("profile-plan");
  await expect(plan.getByTestId("login-times").locator("li").first()).toHaveText(/^\d\d:\d\d$/, { timeout: 150_000 });
  const early = await plan.innerText();

  await createProfile(page, "Late", 50);
  await expect(plan).toHaveCount(0);
  await page.getByTestId("calculate").click();
  await expect(plan.getByTestId("login-times").locator("li").first()).toBeVisible({ timeout: 60_000 });
  expect(await plan.innerText()).not.toBe(early);
  await expect(page.getByTestId("timing")).toContainText("plan in");

  await page.getByTestId("player-fields_owned").fill("3");
  await page.getByTestId("player-fields_owned").blur();
  await expect(page.getByTestId("stale")).toBeVisible();
});
