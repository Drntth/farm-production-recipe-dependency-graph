// End-to-end tests of the built site (npm run build first), mobile and desktop.
import { defineConfig, devices } from "@playwright/test";

const PORT = 4321;
export const BASE = "/farm-production-recipe-dependency-graph/";

export default defineConfig({
  testDir: "tests",
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://localhost:${PORT}${BASE}` },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: `npm run preview -- --port ${PORT}`,
    url: `http://localhost:${PORT}${BASE}`,
    reuseExistingServer: !process.env.CI,
    // astro preview detaches into the background when it sees a coding agent
    // (astro/dist/cli/agent.js, detector: the am-i-vibing package); Playwright
    // needs it in the foreground. Other agents set other variables: if the
    // preview server detaches again, blank that agent's variable here too.
    env: { AI_AGENT: "", CLAUDECODE: "" },
  },
});
