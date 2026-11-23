import { defineConfig } from "vitest/config";

// Unit tests next to the sources; web/tests/ holds the Playwright specs.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
