// Page side of the planner worker: created on the first call.
import type { PlanResult, Progress, WorkerRequest, WorkerResponse } from "./messages";

export type { PlanResult, Progress, WorkerRequest, WorkerResponse } from "./messages";

interface Pending {
  resolve: (value: PlanResult) => void;
  reject: (reason: Error) => void;
}

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, Pending>();
const progressListeners = new Set<(progress: Progress) => void>();
let ready = false;
let readyWaiters: Array<{ resolve: () => void; reject: (reason: Error) => void }> = [];

function handle(message: WorkerResponse): void {
  switch (message.type) {
    case "progress":
      progressListeners.forEach((listener) => listener(message));
      break;
    case "ready":
      ready = true;
      readyWaiters.forEach((w) => w.resolve());
      readyWaiters = [];
      break;
    case "result": {
      const { id, type: _type, ...result } = message;
      pending.get(id)?.resolve(result);
      pending.delete(id);
      break;
    }
    case "error":
      if (message.id === null) {
        // the start failed: fail every waiting request; the next call retries
        pending.forEach((p) => p.reject(new Error(message.message)));
        pending.clear();
        readyWaiters.forEach((w) => w.reject(new Error(message.message)));
        readyWaiters = [];
        worker?.terminate();
        worker = null;
      } else {
        pending.get(message.id)?.reject(new Error(message.message));
        pending.delete(message.id);
      }
      break;
  }
}

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL("./planner.worker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (event: MessageEvent<WorkerResponse>) => handle(event.data);
  }
  return worker;
}

/** Subscribe to the loading progress; returns the unsubscribe function. */
export function onProgress(listener: (progress: Progress) => void): () => void {
  progressListeners.add(listener);
  return () => progressListeners.delete(listener);
}

/** Start loading Pyodide (also done by the first `planFarmProfile`). */
export function warmUp(): Promise<void> {
  if (ready) return Promise.resolve();
  const waiting = new Promise<void>((resolve, reject) => readyWaiters.push({ resolve, reject }));
  getWorker().postMessage({ type: "init" } satisfies WorkerRequest);
  return waiting;
}

/** Production plan of a farm profile JSON object; rejects with the Python error. */
export function planFarmProfile(profile: unknown): Promise<PlanResult> {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    getWorker().postMessage({ type: "plan", id, profile } satisfies WorkerRequest);
  });
}
