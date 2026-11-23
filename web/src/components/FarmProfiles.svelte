<script lang="ts">
  // Farm profiles in the browser: a list kept in IndexedDB, a form that follows the
  // level (an empty field = the level default, shown as the placeholder), JSON
  // export / import, and the production plan of the active profile from the
  // Pyodide worker (loaded on the first calculation).
  import { onMount } from "svelte";
  import type { Combined } from "../data";
  import { content, fill, number, type Lang } from "../i18n";
  import { url } from "../paths";
  import PlanView from "./PlanView.svelte";
  import {
    exportJson,
    importJson,
    loginWindow,
    newFarmProfile,
    setLevel,
    setLocationValue,
    setLoginWindow,
    setName,
    setPlayerValue,
    type LoginWindowField,
  } from "../profiles/profile";
  import { createProfileStore, requestPersist, type StoredProfile } from "../profiles/store";
  import type { FarmProfile, LocationField, LocationProgress, PlayerNumberField } from "../profiles/types";
  import { onProgress, planFarmProfile, type Progress } from "../worker/client";

  interface Props {
    lang: Lang;
  }
  let { lang }: Props = $props();
  const c = $derived(content(lang));
  const t = $derived(c.profiles);

  /** `python -m src web-files`: level-default player profiles and location names. */
  interface Defaults {
    schema_version: number;
    locations: Record<string, { name: string; type: string }>;
    levels: Record<string, { fields_owned?: number | null; locations: Record<string, LocationProgress> }>;
  }
  interface PlanState {
    schedule: Combined["schedule"];
    warnings: string[];
    /** the exported profile the plan was made from, to tell a stale plan */
    from: string;
    loadSeconds: number | null;
    planSeconds: number;
  }

  const GROUPS = ["production", "animal", "tree", "bush", "other"] as const;
  const FIELDS: LocationField[] = ["owned", "slots", "mastery_stars", "animals", "beehives"];
  const BOUNDS: Partial<Record<LocationField, [number, number?]>> = {
    owned: [0],
    slots: [1, 9],
    mastery_stars: [0, 3],
    animals: [0],
    beehives: [1, 4],
  };
  const PLAYER_FIELDS: [PlayerNumberField, "barn" | "silo" | "fields" | "fishing", number][] = [
    ["barn_capacity", "barn", 1],
    ["silo_capacity", "silo", 1],
    ["fields_owned", "fields", 0],
    ["fishing_spots_unlocked", "fishing", 0],
  ];

  const store = createProfileStore();
  let defaults = $state<Defaults | null>(null);
  let records = $state<StoredProfile[]>([]);
  let activeId = $state<string | undefined>(undefined);
  let persisted = $state<boolean | null>(null);
  let message = $state("");
  let newName = $state("");
  let newLevel = $state<number | null>(null);
  let plans = $state<Record<string, PlanState>>({});
  let busy = $state(false);
  let progress = $state<Progress | null>(null);
  let workerLoaded = false;

  const maxLevel = $derived(defaults ? Math.max(...Object.keys(defaults.levels).map(Number)) : 1);
  const active = $derived(records.find((r) => r.id === activeId));
  const profile = $derived(active?.profile);
  const levelDefaults = $derived(profile && defaults ? defaults.levels[String(profile.player.level)] : undefined);
  const grouped = $derived.by(() => {
    if (!levelDefaults || !defaults) return [];
    const all = Object.entries(levelDefaults.locations);
    return GROUPS.map((group) => ({
      group,
      rows: all
        .filter(([id]) => (defaults!.locations[id]?.type ?? "other") === group)
        .map(([id, values]) => ({
          id,
          name: defaults!.locations[id]?.name ?? id,
          fields: FIELDS.filter((f) => f in values),
          values,
        })),
    })).filter((g) => g.rows.length > 0);
  });
  const plan = $derived(activeId ? plans[activeId] : undefined);
  const stale = $derived(!!plan && !!profile && plan.from !== exportJson(profile));

  onMount(() => {
    const off = onProgress((p) => (progress = p));
    (async () => {
      const response = await fetch(url("py/defaults.json"));
      defaults = (await response.json()) as Defaults;
      records = await store.list();
      const saved = await store.getActiveId();
      activeId = records.some((r) => r.id === saved) ? saved : records[0]?.id;
    })().catch((error) => (message = String(error)));
    return off;
  });

  async function save(next: FarmProfile, id = activeId) {
    if (!id) return;
    // a plain copy: IndexedDB cannot clone Svelte's state proxies
    const record = await store.put(id, $state.snapshot(next) as FarmProfile);
    records = [record, ...records.filter((r) => r.id !== id)];
    if (persisted === null) persisted = await requestPersist();
  }

  async function select(id: string) {
    activeId = id;
    await store.setActiveId(id);
  }

  async function add(next: FarmProfile) {
    const id = crypto.randomUUID();
    await save(next, id);
    await select(id);
    newName = "";
  }

  async function create(event: SubmitEvent) {
    event.preventDefault();
    if (!defaults || !newLevel) return;
    const level = Math.min(Math.max(1, Math.round(newLevel)), maxLevel);
    await add(newFarmProfile(newName.trim() || fill(t.defaultName, { n: records.length + 1 }), level));
  }

  async function remove() {
    if (!active || !window.confirm(fill(t.confirmRemove, { name: active.profile.name ?? "" }))) return;
    const id = active.id;
    await store.remove(id);
    delete plans[id];
    records = records.filter((r) => r.id !== id);
    if (records.length) await select(records[0].id);
    else {
      activeId = undefined;
      await store.setActiveId(undefined);
    }
  }

  function download() {
    if (!profile) return;
    const blob = new Blob([exportJson(profile)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    const stem = (profile.name ?? "farm").replace(/[^\p{L}\p{N}_-]+/gu, "_");
    link.download = `${stem}.farm-profile.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function upload(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    try {
      message = "";
      const imported = importJson(await file.text());
      // without level defaults the form cannot be shown (a newer game version)
      if (defaults && !defaults.levels[String(imported.player.level)]) {
        throw new Error(`level ${imported.player.level} is not in the data (1-${maxLevel})`);
      }
      await add(imported);
    } catch (error) {
      message = fill(t.importError, { error: error instanceof Error ? error.message : String(error) });
    }
  }

  /** "" → null (the level default), otherwise a whole number */
  function parse(value: string): number | null {
    if (value.trim() === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? Math.round(n) : null;
  }

  function changeLevel(input: HTMLInputElement) {
    if (!profile || !defaults) return;
    const n = parse(input.value);
    if (n === null || n < 1 || n > maxLevel || n === profile.player.level) {
      input.value = String(profile.player.level); // an out-of-range value is not kept
      return;
    }
    void save(setLevel(profile, n, Object.keys(defaults.levels[String(n)].locations)));
  }

  async function calculate() {
    if (!profile || !activeId) return;
    const id = activeId;
    const from = exportJson(profile);
    busy = true;
    message = "";
    const started = performance.now();
    try {
      const out = await planFarmProfile(JSON.parse(from));
      const total = (performance.now() - started) / 1000;
      // the first call includes loading Pyodide; the worker does not split the time
      const loadSeconds = workerLoaded ? null : total;
      workerLoaded = true;
      plans[id] = {
        schedule: out.result as unknown as Combined["schedule"],
        warnings: [...new Set(out.warnings)],
        from,
        loadSeconds,
        planSeconds: total,
      };
    } catch (error) {
      message = fill(t.error, { error: error instanceof Error ? error.message : String(error) });
    } finally {
      busy = false;
      progress = null;
    }
  }

  const seconds = (s: number) => number(s, lang, 1);
</script>

<section class="card mt-8 p-4 sm:p-6" aria-labelledby="profile-list">
  <h2 id="profile-list" class="section-title text-2xl">{t.list}</h2>
  {#if records.length === 0}
    <p class="muted mt-3">{t.empty}</p>
  {:else}
    <div class="mt-4 flex flex-wrap gap-2" role="tablist" aria-label={t.list} data-testid="profile-tabs">
      {#each records as r (r.id)}
        <button
          type="button"
          role="tab"
          class={r.id === activeId ? "btn btn-primary" : "btn btn-ghost"}
          aria-selected={r.id === activeId}
          onclick={() => select(r.id)}
        >
          {r.profile.name ?? "?"} · {fill(c.level.title, { n: r.profile.player.level })}
        </button>
      {/each}
    </div>
  {/if}

  <form class="mt-5 flex flex-wrap items-end gap-3" onsubmit={create} data-testid="new-profile">
    <h3 class="w-full text-lg">{t.newTitle}</h3>
    <label class="grid gap-1">
      <span class="text-sm font-semibold">{t.name}</span>
      <input
        class="field"
        bind:value={newName}
        maxlength="60"
        placeholder={fill(t.defaultName, { n: records.length + 1 })}
      />
    </label>
    <label class="grid gap-1">
      <span class="text-sm font-semibold">{t.level}</span>
      <input class="field w-24" type="number" min="1" max={maxLevel} required bind:value={newLevel} />
    </label>
    <button type="submit" class="btn btn-primary" disabled={!defaults}>{t.create}</button>
    <label class="btn btn-ghost cursor-pointer">
      {t.import}
      <input type="file" accept="application/json,.json" class="sr-only" onchange={upload} data-testid="import" />
    </label>
  </form>
  {#if message}<p class="warning mt-4" role="alert">{message}</p>{/if}
  {#if persisted !== null}
    <p class="muted mt-3 text-sm" data-testid="persisted">{persisted ? t.persisted : t.notPersisted}</p>
  {/if}
</section>

{#if profile && levelDefaults}
  <section class="card mt-8 p-4 sm:p-6" aria-labelledby="profile-form" data-testid="profile-form">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 id="profile-form" class="section-title text-2xl">{profile.name ?? "?"}</h2>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="btn btn-ghost" onclick={download} data-testid="export">{t.export}</button>
        <button type="button" class="btn btn-ghost" onclick={remove}>{t.remove}</button>
      </div>
    </div>
    <p class="muted mt-2 text-sm">{t.defaultHint}</p>

    <div class="mt-4 flex flex-wrap gap-3">
      <label class="grid gap-1">
        <span class="text-sm font-semibold">{t.name}</span>
        <input
          class="field"
          maxlength="60"
          value={profile.name ?? ""}
          onchange={(e) => save(setName(profile, e.currentTarget.value.trim()))}
        />
      </label>
      <label class="grid gap-1">
        <span class="text-sm font-semibold">{t.level}</span>
        <input
          class="field w-24"
          type="number"
          min="1"
          max={maxLevel}
          value={profile.player.level}
          onchange={(e) => changeLevel(e.currentTarget)}
          data-testid="level"
        />
      </label>
    </div>

    <h3 class="mt-6 text-lg">{t.storage}</h3>
    <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each PLAYER_FIELDS as [field, key, min] (field)}
        <label class="grid gap-1">
          <span class="text-sm font-semibold">{t[key]}</span>
          <input
            class="field"
            type="number"
            {min}
            value={profile.player[field] ?? ""}
            placeholder={field === "fields_owned" && levelDefaults.fields_owned != null
              ? String(levelDefaults.fields_owned)
              : t.notSet}
            onchange={(e) => save(setPlayerValue(profile, field, parse(e.currentTarget.value)))}
            data-testid={`player-${field}`}
          />
        </label>
      {/each}
    </div>

    <h3 class="mt-6 text-lg">{t.loginWindow}</h3>
    <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each [["start", "07:00"], ["end", "23:00"]] as [field, fallback] (field)}
        <label class="grid gap-1">
          <span class="text-sm font-semibold">{t[field as "start" | "end"]}</span>
          <input
            class="field"
            type="time"
            value={loginWindow(profile)[field as LoginWindowField] ?? fallback}
            onchange={(e) =>
              save(
                setLoginWindow(
                  profile,
                  field as LoginWindowField,
                  e.currentTarget.value === fallback ? null : e.currentTarget.value,
                ),
              )}
          />
        </label>
      {/each}
      <label class="grid gap-1">
        <span class="text-sm font-semibold">{t.logins}</span>
        <input
          class="field"
          type="number"
          min="1"
          max="24"
          value={loginWindow(profile).logins ?? ""}
          placeholder={t.suggested}
          onchange={(e) => save(setLoginWindow(profile, "logins", parse(e.currentTarget.value)))}
        />
      </label>
    </div>

    {#each grouped as g (g.group)}
      <details class="mt-6" open={g.group === "production"}>
        <summary class="cursor-pointer font-display text-lg font-semibold">
          {t.groups[g.group]} ({g.rows.length})
        </summary>
        <div class="table-wrap mt-2">
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">{t.name}</th>
                {#each FIELDS.filter((f) => g.rows.some((r) => r.fields.includes(f))) as f (f)}
                  <th scope="col">{t.fieldNames[f as keyof typeof t.fieldNames]}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each g.rows as row (row.id)}
                <tr data-location={row.id}>
                  <th scope="row">{row.name}</th>
                  {#each FIELDS.filter((f) => g.rows.some((r) => r.fields.includes(f))) as f (f)}
                    <td>
                      {#if row.fields.includes(f)}
                        <input
                          class="field w-20"
                          type="number"
                          min={BOUNDS[f]?.[0]}
                          max={BOUNDS[f]?.[1]}
                          aria-label={`${row.name}: ${t.fieldNames[f as keyof typeof t.fieldNames]}`}
                          value={profile.player.locations?.[row.id]?.[f] ?? ""}
                          placeholder={row.values[f] == null ? t.recommended : String(row.values[f])}
                          onchange={(e) => save(setLocationValue(profile, row.id, f, parse(e.currentTarget.value)))}
                          data-field={f}
                        />
                      {/if}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </details>
    {/each}

    <div class="mt-6 flex flex-wrap items-center gap-3">
      <button type="button" class="btn btn-primary" onclick={calculate} disabled={busy} data-testid="calculate">
        {busy ? t.calculating : t.calculate}
      </button>
      {#if busy && progress}
        <span class="muted text-sm" role="status">
          {fill(t.loading, { stage: t.stages[progress.stage] })}
        </span>
      {/if}
    </div>
  </section>

  {#if plan}
    <section class="card mt-8 p-4 sm:p-6" aria-labelledby="profile-plan">
      <h2 id="profile-plan" class="section-title text-2xl">{fill(t.planFor, { name: profile.name ?? "?" })}</h2>
      <p class="muted mt-2 text-sm" data-testid="timing">
        {fill(t.timing, {
          load: plan.loadSeconds === null ? "–" : seconds(plan.loadSeconds),
          plan: seconds(plan.planSeconds),
        })}
      </p>
      {#if stale}<p class="warning mt-3" data-testid="stale">{t.stale}</p>{/if}
      {#if plan.warnings.length > 0}
        <details class="mt-3">
          <summary class="cursor-pointer font-semibold">{t.warnings} ({plan.warnings.length})</summary>
          <ul class="item-list mt-2">
            {#each plan.warnings as w (w)}<li class="item">{w.replace(/^src\.[a-z_.]+: /, "")}</li>{/each}
          </ul>
        </details>
      {/if}
      <PlanView schedule={plan.schedule} {lang} />
    </section>
  {/if}
{/if}
