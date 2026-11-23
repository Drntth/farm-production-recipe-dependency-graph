// Mobile timing of the browser planner (npm run test:perf; needs the network,
// Pyodide from the CDN): a mid-range Android phone emulated with a 4x slower CPU
// and Wi-Fi-like network, the three runs of the manual measurement: cold (empty
// cache), warm (second calculation) and after a reload (cache kept, Pyodide
// starts again). Writes test-results/perf.json.
// The CPU slowdown hardly reaches the worker's WebAssembly (4x and 12x gave a
// warm plan of 1.6 and 1.9 s; the owner's phone 4.6 s), so the numbers track
// changes between runs; they are not phone numbers. Owner's phone, 2026-11-23:
// 23.2 s cold, 4.6 s warm, 20.9 s after a reload. Emulated (this machine, same
// day): 14.2 / 1.6 / 10.9 s. The budgets leave room for a slow CDN.
import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";

const BUDGET = { cold: 40, warm: 8, reload: 30 }; // seconds, load + plan (estimates)
const CPU_SLOWDOWN = 4; // the usual mid-range phone setting
// about 30 Mbit/s down, 15 up, 20 ms latency
const WIFI = { offline: false, latency: 20, downloadThroughput: (30e6 / 8) | 0, uploadThroughput: (15e6 / 8) | 0 };

async function calculate(page: Page): Promise<{ load: number | null; plan: number }> {
  const timing = page.getByTestId("timing");
  const before = (await timing.count()) ? await timing.innerText() : null;
  await page.getByTestId("calculate").click();
  // a new plan replaces the timing line (the old plan stays visible meanwhile)
  await expect(page.getByTestId("calculate")).toBeEnabled({ timeout: 240_000 });
  await expect.poll(() => timing.innerText(), { timeout: 240_000 }).not.toBe(before);
  const text = await timing.innerText();
  const [a, b] = (text.match(/\d+(?:\.\d+)?/g) ?? []).map(Number);
  // "Planner loaded in – s" on a warm call: only the plan time is a number
  return text.includes("–") ? { load: null, plan: a } : { load: a, plan: b };
}

test("the browser planner on an emulated mid-range phone", async ({ page }, info) => {
  test.skip(!process.env.PERF, "network and minutes: npm run test:perf");
  test.skip(info.project.name !== "mobile", "a phone measurement");
  test.setTimeout(600_000);
  const cdp = await page.context().newCDPSession(page);
  const throttle = async () => {
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU_SLOWDOWN });
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", WIFI);
  };
  await throttle();
  await page.goto("profiles/");
  const form = page.getByTestId("new-profile");
  await form.getByRole("textbox", { name: "Name" }).fill("Perf");
  await form.getByRole("spinbutton", { name: "Level" }).fill("60");
  await form.getByRole("button", { name: "Create" }).click();

  const cold = await calculate(page);
  const warm = await calculate(page);
  await page.reload();
  await throttle();
  const reload = await calculate(page);

  const total = (r: { load: number | null; plan: number }) => (r.load ?? 0) + r.plan;
  const result = {
    date: new Date().toISOString(),
    site: info.project.use.baseURL,
    device: "Pixel 7 (emulated)",
    cpuSlowdown: CPU_SLOWDOWN,
    network: WIFI,
    seconds: { cold, warm, reload },
    budget: BUDGET,
  };
  mkdirSync("test-results", { recursive: true });
  writeFileSync("test-results/perf.json", JSON.stringify(result, null, 2) + "\n");
  info.annotations.push({ type: "perf", description: JSON.stringify(result.seconds) });
  console.log(
    `perf: cold ${total(cold).toFixed(1)} s, warm ${total(warm).toFixed(1)} s, reload ${total(reload).toFixed(1)} s`,
  );

  expect(cold.load, "the first calculation shows the load time").not.toBeNull();
  expect(total(cold)).toBeLessThan(BUDGET.cold);
  expect(total(warm)).toBeLessThan(BUDGET.warm);
  expect(total(reload)).toBeLessThan(BUDGET.reload);
});
