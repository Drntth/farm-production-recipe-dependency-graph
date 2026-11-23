// Messages between the page and the planner worker (`client.ts`).

/** The `production_plan` outcome of one farm profile (Python: `plan_farm_profile`). */
export interface PlanResult {
  /** The `schedule.json` payload. */
  result: Record<string, unknown>;
  /** Output files by path: `capacity.json`, `schedule.json`, `schedule.md`. */
  files: Record<string, string>;
  /** Warnings logged while planning, `"<logger>: <message>"`. */
  warnings: string[];
}

/** `init` starts loading Pyodide (answered by `ready`); `profile` is a farm profile JSON object. */
export type WorkerRequest = { type: "init" } | { type: "plan"; id: number; profile: unknown };

export interface Progress {
  type: "progress";
  stage: "runtime" | "packages" | "core";
  fraction: number;
}

export type WorkerResponse =
  | Progress
  | { type: "ready" }
  | ({ type: "result"; id: number } & PlanResult)
  /** `id` null: the start failed (no request to answer). */
  | { type: "error"; id: number | null; message: string };
