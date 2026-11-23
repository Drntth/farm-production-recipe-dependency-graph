// The commit the site was built from: the live-site tests (`npm run test:live`)
// check that GitHub Pages serves the expected build.
import { execSync } from "node:child_process";

function commit(): string {
  try {
    return execSync("git rev-parse HEAD", { encoding: "utf-8" }).trim();
  } catch {
    return "unknown"; // a build outside a git checkout
  }
}

export function GET(): Response {
  return new Response(JSON.stringify({ commit: commit() }), { headers: { "Content-Type": "application/json" } });
}
