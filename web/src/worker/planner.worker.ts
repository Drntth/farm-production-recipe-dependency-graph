/// <reference lib="webworker" />
// Module Web Worker: Pyodide with the Python core (`public/py/core.zip`,
// built by `python -m src web-files`). Message types: ./messages.ts.
import type { PyodideInterface } from "pyodide";
import type { PlanResult, Progress, WorkerRequest, WorkerResponse } from "./messages";

const PYODIDE_VERSION = "314.0.8";
const CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
// networkx by its wheel URL: its Pyodide lock entry pulls in matplotlib
const NETWORKX_WHEEL = `${CDN}networkx-3.6.1-py3-none-any.whl`;
const PACKAGES = ["numpy", "scipy", "pydantic", NETWORKX_WHEEL];

const base = import.meta.env.BASE_URL.replace(/\/?$/, "/");
const post = (message: WorkerResponse) => self.postMessage(message);
const progress = (stage: Progress["stage"], fraction: number) => post({ type: "progress", stage, fraction });

async function fetchOk(url: string): Promise<Response> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response;
}

async function start(): Promise<PyodideInterface> {
  progress("runtime", 0);
  const { loadPyodide } = (await import(/* @vite-ignore */ `${CDN}pyodide.mjs`)) as typeof import("pyodide");
  const pyodide = await loadPyodide({ indexURL: CDN });
  progress("packages", 0.2);
  await pyodide.loadPackage(PACKAGES);
  progress("core", 0.8);
  const [zip, bundle] = await Promise.all([
    fetchOk(`${base}py/core.zip`).then((r) => r.arrayBuffer()),
    fetchOk(`${base}py/data_bundle.json`).then((r) => r.text()),
  ]);
  pyodide.unpackArchive(zip, "zip");
  pyodide.globals.set("bundle_text", bundle);
  pyodide.runPython(`
import json
from src.api.browser import plan_farm_profile

_bundle = json.loads(bundle_text)
del bundle_text

def plan_json(profile_text):
    return json.dumps(plan_farm_profile(_bundle, json.loads(profile_text)))
`);
  progress("core", 1);
  return pyodide;
}

// created on the first request, shared by all of them
let pyodideReady: Promise<PyodideInterface> | null = null;

function plan(pyodide: PyodideInterface, profile: unknown): PlanResult {
  const planJson = pyodide.globals.get("plan_json");
  try {
    return JSON.parse(planJson(JSON.stringify(profile)));
  } finally {
    planJson.destroy();
  }
}

self.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const request = event.data;
  const id = request.type === "plan" ? request.id : null;
  let pyodide: PyodideInterface;
  try {
    if (!pyodideReady) {
      pyodideReady = start();
      pyodideReady.then(
        () => post({ type: "ready" }),
        () => undefined, // reported by the awaiting request below
      );
    }
    pyodide = await pyodideReady;
  } catch (error) {
    pyodideReady = null; // only a failed start is retried by the next request
    post({ type: "error", id, message: String(error) });
    return;
  }
  if (request.type !== "plan") return;
  try {
    post({ type: "result", id: request.id, ...plan(pyodide, request.profile) });
  } catch (error) {
    // a planner error (invalid profile, no solution): Pyodide stays loaded
    post({ type: "error", id, message: String(error) });
  }
};
