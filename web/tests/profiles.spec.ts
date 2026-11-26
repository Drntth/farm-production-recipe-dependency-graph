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
  const rows40 = await form.locator("[data-location]").count();
  await page
    .getByTestId("profile-tabs")
    .getByRole("tab", { name: /^Small / })
    .click();
  await expect(form.getByRole("heading", { level: 2 })).toHaveText("Small");
  expect(await form.locator("[data-location]").count()).toBeLessThan(rows40);

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

/** Inputs and the page itself fit the screen width: nothing to scroll sideways. */
async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const out = [...document.querySelectorAll("main input:not(.sr-only), main button, main summary")]
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.left < -1 || r.right > width + 1))
      .map(({ el }) => el.getAttribute("aria-label") ?? el.getAttribute("data-testid") ?? el.outerHTML.slice(0, 60));
    return { page: document.documentElement.scrollWidth - width, out };
  });
  expect(overflow.out).toEqual([]);
  expect(overflow.page).toBeLessThanOrEqual(0);
}

test("the farm profile form fits a phone and a tablet", async ({ page }) => {
  await page.goto("hu/profiles/");
  await createProfile(page, "Telefon", 60);
  const form = page.getByTestId("profile-form");
  await form.evaluate((el) => el.querySelectorAll("details").forEach((d) => (d.open = true)));
  await expectNoSidewaysScroll(page);
  // the placeholders say who gives the value
  await expect(page.getByTestId("player-barn_capacity")).toHaveAttribute("placeholder", "nincs megadva");
  await expect(form.locator('[data-location] input[placeholder="a tervező adja"]').first()).toBeVisible();
});

for (const scale of [1.3, 1.6]) {
  test(`the farm profile form fits with large text (${scale * 100}%)`, async ({ page }) => {
    // the narrowest common Android width (CSS px) on the phone project
    if (test.info().project.name === "mobile") await page.setViewportSize({ width: 360, height: 780 });
    // Android text scaling: a larger root font size, every rem grows with it
    await page.addInitScript((s) => {
      document.addEventListener("DOMContentLoaded", () => (document.documentElement.style.fontSize = `${16 * s}px`));
    }, scale);
    await page.goto("hu/profiles/");
    await createProfile(page, "Nagy betű", 60);
    await page
      .getByTestId("profile-form")
      .evaluate((el) => el.querySelectorAll("details").forEach((d) => (d.open = true)));
    await expectNoSidewaysScroll(page);
  });
}

test("an exported farm profile imports unchanged", async ({ page }) => {
  await page.goto("hu/profiles/");
  await createProfile(page, "Export", 25);
  const beehives = page.locator('[data-location="beehive_tree"] input[data-field="beehives"]');
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
  // the first call: loading and planning timed apart (not the same number twice)
  const [load, planning] = ((await page.getByTestId("timing").innerText()).match(/\d+(\.\d+)?/g) ?? []).map(Number);
  expect(planning).toBeLessThan(load);
  // the planner's notes in the page language, not the Python log text
  await expect(page.getByTestId("notes")).toContainText("Barn capacity is not set");
  await expect(page.getByTestId("notes")).not.toContainText("Player config");

  await createProfile(page, "Late", 50);
  await expect(plan).toHaveCount(0);
  await page.getByTestId("calculate").click();
  await expect(plan.getByTestId("login-times").locator("li").first()).toBeVisible({ timeout: 60_000 });
  expect(await plan.innerText()).not.toBe(early);
  await expect(page.getByTestId("timing")).toContainText("plan in");

  await page.getByTestId("player-fields_owned").fill("3");
  await page.getByTestId("player-fields_owned").blur();
  await expect(page.getByTestId("stale")).toBeVisible();

  // the plan on a phone: nothing to scroll sideways
  await page.setViewportSize({ width: 390, height: 844 });
  await plan.evaluate((el) => el.querySelectorAll("details").forEach((d) => (d.open = true)));
  await expectNoSidewaysScroll(page);
});

// Icons, legend and item drawings: the keyword is visible next to an icon and part of the accessible name
// (WCAG 2.5.3); the drawings are decorative because the name is printed next to them. Independent of the
// number of levels: the level is a fixed one that exists in every data set (25 of 40).
for (const { lang, path, owned } of [
  { lang: "en", path: "profiles/", owned: "Owned" },
  { lang: "hu", path: "hu/profiles/", owned: "Darab" },
]) {
  test.describe(`icons, legend and drawings (${lang})`, () => {
    test("the legend is closed and lists the icons and what an empty field means", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Legend", 25);
      const legend = page.getByTestId("legend");
      expect(await legend.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
      await legend.locator("summary").click();
      await expect(legend.locator("ul").first().locator("li")).toHaveCount(13);
      await expect(legend.locator("ul").first().locator("li svg").first()).toBeVisible();
      await expect(legend.getByText(owned, { exact: false }).first()).toBeVisible();
      await expect(legend.locator("ul").last().locator("li")).toHaveCount(3);
    });

    test("each location card shows its item drawing, decorative (the name is printed)", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Drawings", 25);
      const cards = await page.locator("[data-location]").count();
      expect(cards).toBeGreaterThan(0);
      await expect(page.locator("[data-location] .item-drawing")).toHaveCount(cards);
      await expect(page.locator("[data-location] .item-drawing[aria-hidden='true']")).toHaveCount(cards);
      expect(await page.locator("[data-location] .item-drawing svg").count()).toBeGreaterThanOrEqual(cards);
    });

    test("a field has its icon and keyword, and the accessible name contains the keyword", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Keyword", 25);
      const field = page.locator('[data-location] [data-field="owned"]').first();
      await expect(field).toHaveAttribute("aria-label", new RegExp(owned));
      const label = field.locator("xpath=ancestor::label[1]");
      await expect(label).toContainText(owned);
      expect(await label.locator("svg").count()).toBeGreaterThan(0);
    });

    test("every location field has its concept icon, beehives too", async ({ page }) => {
      await page.goto(path);
      // the beehive tree opens at level 39; the form data holds every game level
      await createProfile(page, "Every icon", 40);
      const beehives = page.locator('[data-location] fieldset[data-field="beehives"]');
      await expect(beehives).toHaveCount(1);
      await expect(beehives.locator("legend svg")).toHaveCount(1);
      for (const f of ["owned", "slots", "mastery_stars", "animals"]) {
        const field = page.locator(`[data-location] [data-field="${f}"]`).first();
        const holder = field.locator("xpath=ancestor-or-self::*[self::label or self::fieldset][1]");
        if (await field.count()) expect(await holder.locator("svg").count(), f).toBeGreaterThan(0);
      }
    });

    test("storage fields keep their names and show the barn, silo and fishing drawings", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Storage", 25);
      for (const field of ["barn_capacity", "silo_capacity", "fishing_spots_unlocked"]) {
        const input = page.getByTestId(`player-${field}`);
        const label = input.locator("xpath=ancestor::label[1]");
        await expect(label.locator(".item-drawing[aria-hidden='true']")).toHaveCount(1);
        await expect(input).toHaveAttribute("aria-label", /\S/);
      }
    });

    test("an invalid value shows the invalid icon in its message and in the summary", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Icons", 25);
      const barn = page.getByTestId("player-barn_capacity");
      await barn.fill("60");
      await barn.blur();
      await expect(page.locator("p.field-error").first().locator("svg")).toHaveCount(1);
      await expect(page.getByTestId("invalid-summary").locator("svg")).toHaveCount(1);
    });

    test("the full name and explanation show on hover only where a pointer can hover", async ({ page }) => {
      await page.goto(path);
      await createProfile(page, "Tooltip", 25);
      const concept = page
        .locator('[data-location] [data-field="owned"]')
        .first()
        .locator("xpath=ancestor::label[1]")
        .locator(".concept")
        .first();
      const tip = concept.locator(".concept-tip");
      const canHover = await page.evaluate(() => matchMedia("(hover: hover)").matches);
      if (canHover) {
        await concept.hover();
        await expect(tip).toBeVisible();
      } else {
        await expect(tip).toBeHidden();
      }
    });
  });
}

// The location cards on a phone, in both themes: the drawing fills its tile, a button row stays
// one short block (the value buttons side by side), and a dropdown shows its whole selected text.
for (const theme of ["light", "dark"]) {
  test(`location cards fit a phone (${theme})`, async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "the phone layout");
    await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
    await page.goto("hu/profiles/");
    // the beehive tree opens at level 39; the form data holds every game level
    await createProfile(page, "Phone", 40);
    const card = page.locator("[data-location]").first();

    const drawing = card.locator(".item-drawing");
    const tile = await drawing.boundingBox();
    const svg = await drawing.locator("svg").boundingBox();
    expect(svg!.width, "drawing inside its tile").toBeGreaterThanOrEqual(tile!.width * 0.7);

    const stars = card.locator('fieldset[data-field="mastery_stars"] label');
    const tops = await stars.evaluateAll((els) => els.slice(1).map((e) => Math.round(e.getBoundingClientRect().top)));
    expect(new Set(tops).size, "the star buttons in one row").toBe(1);

    for (const select of await card.locator("select").all()) {
      const fits = await select.evaluate((el: HTMLSelectElement) => {
        const ctx = document.createElement("canvas").getContext("2d")!;
        ctx.font = getComputedStyle(el).font;
        const text = ctx.measureText(el.selectedOptions[0].text).width;
        const cs = getComputedStyle(el);
        const inner = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        return text <= inner;
      });
      expect(fits, "the selected text of a dropdown is not cut").toBe(true);
    }
  });
}
