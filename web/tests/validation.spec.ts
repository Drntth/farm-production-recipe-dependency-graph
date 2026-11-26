// Validation of the farm profile form: an invalid value is marked, listed in the
// summary (with links to the fields) and never stored; Calculate waits for valid
// values; an import with invalid values is refused with the list and stores nothing;
// a stored invalid profile loads with its fields marked. The level limit is read
// from the page, so the test does not depend on the number of levels in the data.
import { expect, type Page, test } from "@playwright/test";

const PAGES = [
  { lang: "en", path: "profiles/", summary: /^\d+ fields are invalid$/, create: /^Create$/ },
  { lang: "hu", path: "hu/profiles/", summary: /^\d+ mező hibás$/, create: /^Létrehozás$/ },
] as const;

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

for (const { lang, path, summary } of PAGES) {
  test.describe(`farm profile validation (${lang})`, () => {
    test("a typed value above the level limit is marked, listed, not stored; Calculate waits", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Check", 10);

      const level = page.getByTestId("level");
      const max = Number(await level.getAttribute("max"));
      expect(max).toBeGreaterThan(10);

      await level.fill(String(max + 1));
      await level.blur();
      await expect(level).toHaveAttribute("aria-invalid", "true");
      await expect(level).toHaveValue(String(max + 1));

      const list = page.getByTestId("invalid-summary");
      await expect(list.getByRole("paragraph")).toHaveText(summary);
      await expect(list.getByRole("link")).toHaveCount(1);
      await expect(page.getByTestId("calculate")).toBeDisabled();

      // not stored: after a reload the level is the stored one
      await page.reload();
      await expect(page.getByTestId("level")).toHaveValue("10");
      await expect(page.getByTestId("invalid-summary")).toHaveCount(0);
      await expect(page.getByTestId("calculate")).toBeEnabled();
    });

    test("a summary link opens the closed group and focuses its field", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Links", 25);

      // a tree is in the closed "tree" group; owned has only the lower bound 0
      const owned = page.locator('[data-location="apple_tree"] input[data-field="owned"]');
      const group = page.locator("details", { has: owned });
      // open the group to type, then close it again: the summary link must open it
      await group.locator("summary").click();
      await owned.fill("-1");
      await owned.blur();
      await expect(owned).toHaveAttribute("aria-invalid", "true");
      await group.locator("summary").click();
      await expect(owned).toBeHidden();
      expect(await group.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);

      await page.getByTestId("invalid-summary").getByRole("link").first().click();
      await expect(owned).toBeFocused();
      expect(await group.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(true);
    });

    test("an import with an invalid value is refused with the list and stores nothing", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Import", 25);
      const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export").click()]);
      const text = await (await download.createReadStream()).toArray().then((c) => Buffer.concat(c).toString("utf-8"));
      const exported = JSON.parse(text);
      exported.player.barn_capacity = 60; // a step of 25 from 50: 60 is not allowed

      await page.getByTestId("import").setInputFiles({
        name: "bad.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(exported)),
      });
      const refused = page.getByTestId("import-errors");
      await expect(refused).toBeVisible();
      await expect(refused.locator("li")).toHaveCount(1);
      await expect(refused.locator("li")).toContainText("60");
      await expect(page.getByTestId("profile-tabs").getByRole("tab")).toHaveCount(1);
    });

    test("a stored invalid profile loads with its field marked and Calculate disabled", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Seed", 25);
      // write a copy with an invalid barn capacity straight into IndexedDB (the form never stores it)
      await storeInvalid(page, { barn_capacity: 60 });
      await page.reload();

      const barn = page.getByTestId("player-barn_capacity");
      await expect(barn).toHaveValue("60");
      await expect(barn).toHaveAttribute("aria-invalid", "true");
      await expect(page.getByTestId("invalid-summary").getByRole("link")).toHaveCount(1);
      await expect(page.getByTestId("calculate")).toBeDisabled();
    });

    test("a summary link focuses a button row and the row names its error", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Stars", 25);
      await storeInvalid(page, { locations: { bakery: { mastery_stars: 5 } } });
      await page.reload();

      const row = page.locator('[data-location="bakery"] fieldset[data-field="mastery_stars"]');
      await page.getByTestId("invalid-summary").getByRole("link").first().click();
      await expect(row).toBeFocused();
      const described = await row.getAttribute("aria-describedby");
      expect(described).toBeTruthy();
      // the message names the allowed range
      await expect(page.locator(`[id="${described}"]`)).toContainText("3");
    });
  });
}

/** Writes a copy of the active profile with `patch` on its player straight into IndexedDB (the form never stores it). */
async function storeInvalid(page: Page, patch: Record<string, unknown>) {
  await page.evaluate(async (patch) => {
    const db = await new Promise<IDBDatabase>((ok, fail) => {
      const req = indexedDB.open("farm-production");
      req.onsuccess = () => ok(req.result);
      req.onerror = () => fail(req.error);
    });
    const tx = db.transaction("profiles", "readwrite");
    const store = tx.objectStore("profiles");
    const keys = await new Promise<IDBValidKey[]>((ok) => {
      const req = store.getAllKeys();
      req.onsuccess = () => ok(req.result);
    });
    const key = keys.find((k) => String(k).startsWith("profile:")) as string;
    const record = await new Promise<{ id: string; profile: { player: Record<string, unknown> } }>((ok) => {
      const req = store.get(key);
      req.onsuccess = () => ok(req.result);
    });
    record.id = "seeded";
    Object.assign(record.profile.player, patch);
    store.put(record, "profile:seeded");
    store.put("seeded", "active-profile-id");
    await new Promise<void>((ok) => (tx.oncomplete = () => ok()));
    db.close();
  }, patch);
}
