// Pyodide smoke test: plan a fixed farm profile in Pyodide (npm `pyodide`,
// packages from the jsDelivr CDN) and compare it with native CPython.
//
//   python -m src web-files            # core.zip, data_bundle.json (once)
//   node web/scripts/pyodide-smoke.mjs # from the repository root
//
// Needs python (with requirements.txt) on PATH, or PYTHON=<executable>.
// Exit code 1 when the results differ.
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide, version } from "pyodide";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const webFiles = join(root, "web/public/py");
const workDir = join(root, "output/pyodide-smoke");
const cacheDir = join(workDir, "cache");
const python = process.env.PYTHON ?? "python";
const networkx = `https://cdn.jsdelivr.net/pyodide/v${version}/full/networkx-3.6.1-py3-none-any.whl`;

const t0 = performance.now();
const lap = (label, since) => console.log(`${label.padEnd(24)}${((performance.now() - since) / 1000).toFixed(1)} s`);

mkdirSync(cacheDir, { recursive: true });

// 1. native result
let t = performance.now();
const native = spawnSync(python, [join(root, "web/scripts/pyodide_smoke_expected.py"), workDir], {
  cwd: root,
  stdio: ["ignore", "inherit", "inherit"],
});
if (native.status !== 0) {
  console.error("The native step failed (is the python environment active?)");
  process.exit(2);
}
lap("native plan", t);
const profileText = readFileSync(join(workDir, "profile.json"), "utf8");
const expected = readFileSync(join(workDir, "expected.json"), "utf8");

// 2. Pyodide
t = performance.now();
const pyodide = await loadPyodide({ packageCacheDir: cacheDir });
lap(`pyodide ${version} ready`, t);
t = performance.now();
await pyodide.loadPackage(["numpy", "scipy", "pydantic", networkx]);
lap("packages", t);
t = performance.now();
const zip = readFileSync(join(webFiles, "core.zip"));
pyodide.unpackArchive(new Uint8Array(zip.buffer, zip.byteOffset, zip.byteLength), "zip"); // not a Buffer
pyodide.globals.set("bundle_text", readFileSync(join(webFiles, "data_bundle.json"), "utf8"));
pyodide.globals.set("profile_text", profileText);
pyodide.runPython(`
import json
from src.api.browser import plan_farm_profile
_bundle = json.loads(bundle_text)
`);
lap("core + bundle", t);
t = performance.now();
const actual = pyodide.runPython("json.dumps(plan_farm_profile(_bundle, json.loads(profile_text)))");
lap("plan (first run)", t);
t = performance.now();
pyodide.runPython("json.dumps(plan_farm_profile(_bundle, json.loads(profile_text)))");
lap("plan (warm)", t);
lap("total", t0);

// 3. compare
if (actual === expected) {
  console.log(`IDENTICAL (${expected.length} characters)`);
  process.exit(0);
}
let i = 0;
while (actual[i] === expected[i]) i++;
console.error(`DIFFERENT at character ${i}:`);
console.error(`  native:  ...${expected.slice(Math.max(0, i - 60), i + 80)}`);
console.error(`  pyodide: ...${actual.slice(Math.max(0, i - 60), i + 80)}`);
process.exit(1);
