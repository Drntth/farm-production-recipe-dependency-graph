// Only with SITE_URL (npm run test:live): the deployed site is the expected build.
// EXPECTED_COMMIT (CI: the deployed commit), else the local `git rev-parse HEAD`.
import { execSync } from "node:child_process";
import { expect, test } from "@playwright/test";

test("the live site serves the expected build", async ({ request }, info) => {
  test.skip(!process.env.SITE_URL, "only against a deployed site (SITE_URL)");
  test.skip(info.project.name !== "desktop", "one check is enough");
  const expected = process.env.EXPECTED_COMMIT ?? execSync("git rev-parse HEAD", { encoding: "utf-8" }).trim();
  test.setTimeout(360_000);
  // the Pages CDN may serve the previous build for a few minutes after a deploy
  const live = async () => {
    const response = await request.get(`version.json?t=${Date.now()}`);
    return response.ok() ? ((await response.json()) as { commit: string }).commit : "no version.json";
  };
  await expect
    .poll(live, {
      message: "the live site is another build: wait for the Pages deploy, or push first",
      timeout: process.env.CI ? 300_000 : 10_000,
      intervals: [5_000, 15_000, 30_000],
    })
    .toBe(expected);
});
