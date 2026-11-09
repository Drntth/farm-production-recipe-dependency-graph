// Static site of the level recommendations; deployed to GitHub Pages.
// English at the root, Hungarian under /hu/ (src/i18n.ts).
import svelte from "@astrojs/svelte";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";
import icon from "astro-icon";

export default defineConfig({
  site: "https://drntth.github.io",
  base: "/farm-production-recipe-dependency-graph",
  trailingSlash: "always",
  integrations: [svelte(), icon()],
  vite: { plugins: [tailwindcss()] },
});
