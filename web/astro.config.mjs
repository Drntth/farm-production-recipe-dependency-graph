// Static site of the level recommendations; deployed to GitHub Pages.
import svelte from "@astrojs/svelte";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://drntth.github.io",
  base: "/farm-production-recipe-dependency-graph",
  trailingSlash: "always",
  integrations: [svelte()],
});
