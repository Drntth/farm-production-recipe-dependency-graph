<script lang="ts">
  // Farm profiles in the browser: a list kept in IndexedDB, a form that follows the
  // level (an empty field = the level default, shown as the placeholder), JSON
  // export / import, and the production plan of the active profile from the
  // Pyodide worker (loaded on the first calculation). Every value is checked by
  // the profile check (src/profiles/check.ts): an invalid one is not stored.
  import { onMount } from "svelte";
  import type { Combined } from "../data";
  import { content, fill, number, type Lang } from "../i18n";
  import { url } from "../paths";
  import PlanView from "./PlanView.svelte";
  import Icon from "./Icon.svelte";
  import ItemDrawing from "./ItemDrawing.svelte";
  import type { IconName } from "./icon-data";
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
  import {
    checkProfile,
    checkValue,
    fieldRange,
    ruleMessage,
    type Bounds,
    type FieldError,
    type FieldRange,
  } from "../profiles/check";
  import { createProfileStore, requestPersist, type StoredProfile } from "../profiles/store";
  import type { FarmProfile, LocationProgress, PlayerNumberField } from "../profiles/types";
  import { translateWarning } from "../profiles/warnings";
  import { loadTime, onProgress, planFarmProfile, type Progress } from "../worker/client";

  interface Props {
    lang: Lang;
  }
  let { lang }: Props = $props();
  const c = $derived(content(lang));
  const t = $derived(c.profiles);

  /** `python -m src web-files`: level defaults, location facts and the form limits per level. */
  interface Defaults extends Bounds {
    schema_version: number;
    locations: Record<string, { name: string; type: string; animal_capacity?: number; max_slots?: number }>;
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
  /** One location card: the fields the level has for it. */
  interface Row {
    id: string;
    name: string;
    fields: Field[];
    values: LocationProgress;
  }

  const GROUPS = ["production", "animal", "tree", "bush", "other"] as const;
  const FIELDS = ["owned", "slots", "mastery_stars", "animals", "beehives"] as const;
  type Field = (typeof FIELDS)[number];
  /** The keyword of a field or action; the texts are in profiles.concepts. */
  type Concept =
    | "copies"
    | "slots"
    | "stars"
    | "animals"
    | "beehives"
    | "fields"
    | "fishing"
    | "logins"
    | "loginWindow"
    | "export"
    | "import"
    | "invalid"
    | "loading";
  /** Concept icons of docs/ui-design.md. */
  const ICONS: Record<Concept, IconName> = {
    copies: "copy",
    slots: "list-ordered",
    stars: "star",
    animals: "paw-print",
    beehives: "hexagon",
    fields: "wheat",
    fishing: "fishing-hook",
    logins: "log-in",
    loginWindow: "alarm-clock",
    export: "download",
    import: "upload",
    invalid: "circle-alert",
    loading: "loader-circle",
  };
  const FIELD_CONCEPT: Record<Field, Concept> = {
    owned: "copies",
    slots: "slots",
    mastery_stars: "stars",
    animals: "animals",
    beehives: "beehives",
  };
  /** Storage fields with a concept icon, and the item drawing printed next to their label. */
  const STORAGE_CONCEPT: Partial<Record<PlayerNumberField, Concept>> = {
    fields_owned: "fields",
    fishing_spots_unlocked: "fishing",
  };
  const STORAGE_DRAWING: Partial<Record<PlayerNumberField, string>> = {
    barn_capacity: "barn",
    silo_capacity: "silo",
    fishing_spots_unlocked: "fishing_spot",
  };
  const LEGEND_CONCEPTS: Concept[] = [
    "copies",
    "slots",
    "stars",
    "animals",
    "beehives",
    "fields",
    "fishing",
    "logins",
    "loginWindow",
    "export",
    "import",
    "invalid",
    "loading",
  ];
  const PLAYER_FIELDS: [PlayerNumberField, "barn" | "silo" | "fields" | "fishing"][] = [
    ["barn_capacity", "barn"],
    ["silo_capacity", "silo"],
    ["fields_owned", "fields"],
    ["fishing_spots_unlocked", "fishing"],
  ];

  const store = createProfileStore();
  let defaults = $state<Defaults | null>(null);
  let records = $state<StoredProfile[]>([]);
  let activeId = $state<string | undefined>(undefined);
  let persisted = $state<boolean | null>(null);
  let message = $state("");
  /** typed text of the invalid fields, not stored: path → text and the value that was checked */
  let drafts = $state<Record<string, { text: string; value: number | null }>>({});
  let importErrors = $state<{ label: string; value: string; text: string }[]>([]);
  let newName = $state("");
  let newLevel = $state("");
  let newLevelError = $state<FieldError | null>(null);
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
        .map(([id, values]): Row => ({
          id,
          name: defaults!.locations[id]?.name ?? id,
          fields: FIELDS.filter((f) => f in values),
          values,
        })),
    })).filter((g) => g.rows.length > 0);
  });
  const plan = $derived(activeId ? plans[activeId] : undefined);
  const stale = $derived(!!plan && !!profile && plan.from !== exportJson(profile));
  /** every invalid value: the stored profile's, and the typed ones that are not stored */
  const errors = $derived.by(() => {
    const out: Record<string, FieldError> = {};
    if (!defaults || !profile) return out;
    for (const error of checkProfile(profile, defaults)) out[error.path] = error;
    for (const [path, draft] of Object.entries(drafts)) {
      const error = checkValue(path, draft.value, defaults, profile.player.level);
      if (error) out[path] = error;
    }
    return out;
  });
  const errorList = $derived(Object.values(errors));

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
    drafts = {};
    importErrors = [];
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
    if (!defaults || !newLevel || newLevelError) return;
    await add(newFarmProfile(newName.trim() || fill(t.defaultName, { n: records.length + 1 }), Number(newLevel)));
  }

  /** The new profile's level: checked on change, kept as text until it is valid. */
  function checkNewLevel(input: HTMLInputElement) {
    newLevelError = defaults ? checkValue("player.level", valueOf(input), defaults, 1) : null;
    if (!newLevelError) newLevel = input.value;
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
    if (!file || !defaults) return;
    message = "";
    importErrors = [];
    try {
      // the schema version first (importJson), then every value against the limits
      const imported = importJson(await file.text());
      const invalid = checkProfile(imported, defaults);
      if (invalid.length > 0) {
        importErrors = invalid.map((e) => ({
          label: labelOf(e.path),
          value: String(e.value),
          text: ruleMessage(e, t.validation),
        }));
        return;
      }
      await add(imported);
    } catch (error) {
      message = fill(t.importError, { error: error instanceof Error ? error.message : String(error) });
    }
  }

  /** "" → null (the level default); otherwise the number as typed (never rounded), NaN for text. */
  function parse(text: string): number | null {
    return text.trim() === "" ? null : Number(text);
  }

  /** The value of an input; a text the browser refuses (badInput) is NaN, not the level default. */
  function valueOf(input: HTMLInputElement | HTMLSelectElement): number | null {
    return input instanceof HTMLInputElement && input.validity.badInput ? Number.NaN : parse(input.value);
  }

  /** A typed value: stored when valid; an invalid one stays in the field with its message. */
  function commit(path: string, input: HTMLInputElement | HTMLSelectElement, apply: (value: number | null) => unknown) {
    if (!defaults || !profile) return;
    const value = valueOf(input);
    if (checkValue(path, value, defaults, profile.player.level)) {
      drafts = { ...drafts, [path]: { text: input.value, value } };
      return;
    }
    drafts = Object.fromEntries(Object.entries(drafts).filter(([p]) => p !== path));
    void apply(value);
  }

  function changeLevel(value: number | null) {
    if (!profile || !defaults || value === null || value === profile.player.level) return;
    const data = defaults;
    // typed values that are still invalid at the new level stay in their fields
    drafts = Object.fromEntries(Object.entries(drafts).filter(([p, d]) => checkValue(p, d.value, data, value)));
    void save(setLevel(profile, value, Object.keys(data.levels[String(value)].locations)));
  }

  async function calculate() {
    if (!profile || !activeId || errorList.length > 0) return;
    const id = activeId;
    const from = exportJson(profile);
    busy = true;
    message = "";
    const started = performance.now();
    try {
      const out = await planFarmProfile(JSON.parse(from));
      const total = (performance.now() - started) / 1000;
      // the first call includes loading Pyodide: shown apart from the planning
      const loadSeconds = workerLoaded ? null : loadTime();
      workerLoaded = true;
      plans[id] = {
        schedule: out.result as unknown as Combined["schedule"],
        warnings: [...new Set(out.warnings)],
        from,
        loadSeconds,
        planSeconds: loadSeconds === null ? total : Math.max(total - loadSeconds, 0),
      };
    } catch (error) {
      message = fill(t.error, { error: error instanceof Error ? error.message : String(error) });
    } finally {
      busy = false;
      progress = null;
    }
  }

  /** The text of a typed or stored value; a draft shows what was typed. */
  function display(path: string, stored: unknown): string {
    return drafts[path]?.text ?? (stored == null ? "" : String(stored));
  }

  function rangeOf(path: string): FieldRange {
    return defaults && profile ? fieldRange(path, defaults, profile.player.level) : { min: 0 };
  }

  /** The integers from..to; a stored value outside them stays selectable, so it stays visible. */
  function choices(from: number, to: number, stored: number | null | undefined): number[] {
    const list = Array.from({ length: Math.max(to - from + 1, 0) }, (_, i) => from + i);
    if (stored != null && !list.includes(stored)) list.push(stored);
    return list.sort((a, b) => a - b);
  }

  function defaultLabel(value: number | null | undefined): string {
    return value == null ? t.recommended : fill(t.levelDefault, { value });
  }

  const LOGINS_PATH = "planner.production.login_window.logins";
  const loginsRange = $derived(rangeOf(LOGINS_PATH));

  const fieldId = (path: string) => "f-" + path.replace(/[^a-z0-9]+/gi, "-");
  const errorId = (path: string) => `${fieldId(path)}-error`;

  /** The name of a field in the summary: "Bakery: Slots", "Barn capacity", … */
  function labelOf(path: string): string {
    if (path === "player.level") return t.level;
    if (path === "planner.production.login_window.logins") return t.logins;
    const [head, id, field] = path.split(".");
    if (head === "locations") return `${defaults?.locations[id]?.name ?? id}: ${t.fieldNames[field as Field]}`;
    const known = PLAYER_FIELDS.find(([f]) => f === id);
    // an unknown field shows its path rather than a wrong name
    return known ? t[known[1]] : path;
  }

  /** Opens the closed group of the field, then moves the focus to it. */
  function focusField(event: MouseEvent, path: string) {
    event.preventDefault();
    const field = document.getElementById(fieldId(path));
    const group = field?.closest("details");
    if (group) group.open = true;
    field?.focus();
  }

  const seconds = (s: number) => number(s, lang, 1);
  const noteNames = {
    location: (id: string) => defaults?.locations[id]?.name ?? id,
    storage: (name: string) => (name === "barn_capacity" ? t.barn : t.silo),
  };
</script>

{#snippet concept(key: Concept)}
  {@const c = t.concepts[key]}
  {@const icon = ICONS[key]}
  <span class="concept">
    <Icon name={icon} size={16} />
    <span>{c.keyword}</span>
    <span class="concept-tip" aria-hidden="true"><strong>{c.name}</strong>. {c.help}</span>
  </span>
{/snippet}

{#snippet fieldMessage(path: string)}
  {#if errors[path] && defaults}
    <p id={errorId(path)} class="field-error mt-1 flex items-start gap-1.5 text-sm">
      <Icon name="circle-alert" size={16} /><span>{ruleMessage(errors[path], t.validation)}</span>
    </p>
  {/if}
{/snippet}

{#snippet locationField(row: Row, f: Field)}
  {@const path = `locations.${row.id}.${f}`}
  {@const label = `${row.name}: ${t.concepts[FIELD_CONCEPT[f]].keyword}`}
  {@const stored = profile?.player.locations?.[row.id]?.[f]}
  {@const r = rangeOf(path)}
  {@const copies = defaults?.limits[String(profile?.player.level)]?.copies[row.id]}
  {#if f === "mastery_stars" || f === "beehives"}
    {@const options = f === "beehives" ? [1, 2, 3, 4] : [0, 1, 2, 3]}
    <!-- the summary link focuses the row (tabindex -1), its error is read with it -->
    <fieldset
      id={fieldId(path)}
      tabindex="-1"
      class="col-span-full min-w-0"
      aria-describedby={errors[path] ? errorId(path) : undefined}
      data-field={f}
    >
      <legend class="muted text-xs font-semibold">{@render concept(FIELD_CONCEPT[f])}</legend>
      <div class="mt-1 flex flex-wrap gap-1">
        <!-- the default on its own line, the values side by side below it -->
        <label class="btn btn-ghost basis-full has-focus-visible:outline-2 has-focus-visible:outline-offset-2">
          <input
            type="radio"
            class="sr-only"
            name={path}
            value=""
            checked={stored == null}
            onchange={(e) => commit(path, e.currentTarget, (v) => save(setLocationValue(profile!, row.id, f, v)))}
          />
          {defaultLabel(row.values[f])}
        </label>
        {#each options as v (v)}
          <label
            class={`${stored === v ? "btn btn-primary" : "btn btn-ghost"} flex-1 has-focus-visible:outline-2 has-focus-visible:outline-offset-2`}
          >
            <input
              type="radio"
              class="sr-only"
              name={path}
              value={String(v)}
              checked={stored === v}
              aria-invalid={errors[path] ? "true" : undefined}
              onchange={(e) => commit(path, e.currentTarget, (x) => save(setLocationValue(profile!, row.id, f, x)))}
            />
            {v}{f === "mastery_stars" ? "★" : ""}
          </label>
        {/each}
      </div>
      {@render fieldMessage(path)}
    </fieldset>
  {:else if f === "slots" || (f === "owned" && copies !== undefined)}
    {@const from = f === "slots" ? 1 : 0}
    {@const to = f === "slots" ? (r.max ?? from) : (copies ?? 0)}
    <div class="min-w-0">
      <label class="grid min-w-0 gap-1">
        <span class="muted text-xs font-semibold">{@render concept(FIELD_CONCEPT[f])}</span>
        <select
          id={fieldId(path)}
          class="field w-full min-w-0"
          aria-label={label}
          aria-invalid={errors[path] ? "true" : undefined}
          aria-describedby={errors[path] ? errorId(path) : undefined}
          value={stored == null ? "" : String(stored)}
          onchange={(e) => commit(path, e.currentTarget, (v) => save(setLocationValue(profile!, row.id, f, v)))}
          data-field={f}
        >
          <option value="">{defaultLabel(row.values[f])}</option>
          {#each choices(from, to, stored) as v (v)}
            <option value={String(v)}>{v}</option>
          {/each}
        </select>
      </label>
      {@render fieldMessage(path)}
    </div>
  {:else}
    <div class="min-w-0">
      <label class="grid min-w-0 gap-1">
        <span class="muted text-xs font-semibold">{@render concept(FIELD_CONCEPT[f])}</span>
        <input
          id={fieldId(path)}
          class="field w-full min-w-0"
          type="number"
          inputmode="numeric"
          min={r.min}
          max={r.max}
          step={r.step}
          aria-label={label}
          aria-invalid={errors[path] ? "true" : undefined}
          aria-describedby={errors[path] ? errorId(path) : undefined}
          value={display(path, stored)}
          placeholder={row.values[f] == null ? t.recommended : String(row.values[f])}
          onchange={(e) => commit(path, e.currentTarget, (v) => save(setLocationValue(profile!, row.id, f, v)))}
          data-field={f}
        />
      </label>
      {@render fieldMessage(path)}
    </div>
  {/if}
{/snippet}

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
    <label class="grid min-w-0 grow gap-1 sm:grow-0">
      <span class="text-sm font-semibold">{t.name}</span>
      <input
        class="field w-full min-w-0"
        bind:value={newName}
        maxlength="60"
        placeholder={fill(t.defaultName, { n: records.length + 1 })}
      />
    </label>
    <label class="grid gap-1">
      <span class="text-sm font-semibold">{t.level}</span>
      <input
        class="field w-24"
        type="number"
        inputmode="numeric"
        min="1"
        max={maxLevel}
        step="1"
        required
        value={newLevel}
        aria-invalid={newLevelError ? "true" : undefined}
        aria-describedby={newLevelError ? "new-level-error" : undefined}
        onchange={(e) => checkNewLevel(e.currentTarget)}
        data-testid="new-level"
      />
    </label>
    {#if newLevelError}
      <p id="new-level-error" class="field-error w-full text-sm">{ruleMessage(newLevelError, t.validation)}</p>
    {/if}
    <button type="submit" class="btn btn-primary" disabled={!defaults || !!newLevelError}>{t.create}</button>
    <label class="btn btn-ghost cursor-pointer">
      <Icon name="upload" size={18} />
      {t.import}
      <input
        type="file"
        accept="application/json,.json"
        class="sr-only"
        disabled={!defaults}
        onchange={upload}
        data-testid="import"
      />
    </label>
  </form>
  {#if message}<p class="warning mt-4" role="alert">{message}</p>{/if}
  {#if importErrors.length > 0}
    <div class="error-summary mt-4" role="alert" data-testid="import-errors">
      <p class="font-semibold">{t.importRefused}</p>
      <ul class="mt-2 list-disc pl-5">
        {#each importErrors as e, i (i)}
          <li>{e.label} ({e.value}): {e.text}</li>
        {/each}
      </ul>
    </div>
  {/if}
  {#if persisted !== null}
    <p class="muted mt-3 text-sm" data-testid="persisted">{persisted ? t.persisted : t.notPersisted}</p>
  {/if}
</section>

{#if profile && levelDefaults}
  <section class="card mt-8 p-4 sm:p-6" aria-labelledby="profile-form" data-testid="profile-form">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 id="profile-form" class="section-title text-2xl">{profile.name ?? "?"}</h2>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="btn btn-ghost" onclick={download} data-testid="export"
          ><Icon name="download" size={18} /> {t.export}</button
        >
        <button type="button" class="btn btn-ghost" onclick={remove}>{t.remove}</button>
      </div>
    </div>
    <details class="legend mt-3" data-testid="legend">
      <summary class="flex cursor-pointer items-center gap-2 font-semibold">
        <Icon name="info" size={18} />
        <span>{t.legend.title}</span>
      </summary>
      <ul class="mt-3 grid gap-2 sm:grid-cols-2">
        {#each LEGEND_CONCEPTS as key (key)}
          {@const c = t.concepts[key]}
          {@const icon = ICONS[key]}
          <li class="flex items-start gap-2 text-sm">
            <Icon name={icon} size={18} />
            <span><strong>{c.keyword}</strong>: {c.help}</span>
          </li>
        {/each}
      </ul>
      <p class="mt-3 text-sm font-semibold">{t.legend.empty}</p>
      <ul class="mt-1 grid gap-1 text-sm">
        <li><span class="muted">{t.legend.levelDefault}</span></li>
        <li><span class="muted">{t.legend.recommended}</span></li>
        <li><span class="muted">{t.legend.notSet}</span></li>
      </ul>
    </details>

    {#if errorList.length > 0}
      <div class="error-summary mt-4" role="alert" data-testid="invalid-summary">
        <p class="flex items-center gap-2 font-semibold">
          <Icon name="circle-alert" size={18} /><span>{fill(t.validation.summary, { n: errorList.length })}</span>
        </p>
        <ul class="mt-2 list-disc pl-5">
          {#each errorList as e (e.path)}
            <li>
              <a class="underline" href={`#${fieldId(e.path)}`} onclick={(event) => focusField(event, e.path)}
                >{labelOf(e.path)}</a
              >
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div class="mt-4 flex flex-wrap gap-3">
      <label class="grid min-w-0 grow gap-1 sm:grow-0">
        <span class="text-sm font-semibold">{t.name}</span>
        <input
          class="field w-full min-w-0"
          maxlength="60"
          value={profile.name ?? ""}
          onchange={(e) => save(setName(profile!, e.currentTarget.value.trim()))}
        />
      </label>
      <div class="min-w-0">
        <label class="grid gap-1">
          <span class="text-sm font-semibold">{t.level}</span>
          <input
            id={fieldId("player.level")}
            class="field w-24"
            type="number"
            inputmode="numeric"
            min="1"
            max={maxLevel}
            step="1"
            value={display("player.level", profile.player.level)}
            aria-invalid={errors["player.level"] ? "true" : undefined}
            aria-describedby={errors["player.level"] ? errorId("player.level") : undefined}
            onchange={(e) => commit("player.level", e.currentTarget, changeLevel)}
            data-testid="level"
          />
        </label>
        {@render fieldMessage("player.level")}
      </div>
    </div>

    <h3 class="mt-6 text-lg">{t.storage}</h3>
    <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each PLAYER_FIELDS as [field, key] (field)}
        {@const path = `player.${field}`}
        {@const r = rangeOf(path)}
        {@const drawing = STORAGE_DRAWING[field]}
        {@const concepted = STORAGE_CONCEPT[field]}
        <div class="min-w-0">
          <label class="grid min-w-0 gap-1">
            <span class="flex min-w-0 flex-wrap items-center gap-1.5 text-sm font-semibold [overflow-wrap:anywhere]">
              {#if drawing}<ItemDrawing id={drawing} name={t[key]} size={28} decorative />{/if}
              {#if concepted}{@render concept(concepted)}{:else}{t[key]}{/if}
            </span>
            <input
              id={fieldId(path)}
              class="field w-full min-w-0"
              type="number"
              inputmode="numeric"
              min={r.min}
              max={r.max}
              step={r.step}
              value={display(path, profile.player[field])}
              placeholder={field === "fields_owned" && levelDefaults.fields_owned != null
                ? String(levelDefaults.fields_owned)
                : t.notSet}
              aria-invalid={errors[path] ? "true" : undefined}
              aria-describedby={errors[path] ? errorId(path) : undefined}
              onchange={(e) => commit(path, e.currentTarget, (v) => save(setPlayerValue(profile!, field, v)))}
              aria-label={t[key]}
              data-testid={`player-${field}`}
            />
          </label>
          {@render fieldMessage(path)}
        </div>
      {/each}
    </div>

    <h3 class="mt-6 flex items-center gap-2 text-lg">
      <Icon name="alarm-clock" size={20} /><span>{t.loginWindow}</span>
    </h3>
    <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {#each [["start", "07:00"], ["end", "23:00"]] as [field, fallback] (field)}
        <label class="grid min-w-0 gap-1">
          <span class="text-sm font-semibold">{t[field as "start" | "end"]}</span>
          <input
            class="field w-full min-w-0"
            type="time"
            value={loginWindow(profile)[field as LoginWindowField] ?? fallback}
            onchange={(e) =>
              save(
                setLoginWindow(
                  profile!,
                  field as LoginWindowField,
                  e.currentTarget.value === fallback ? null : e.currentTarget.value,
                ),
              )}
          />
        </label>
      {/each}
      <div class="min-w-0">
        <label class="grid min-w-0 gap-1">
          <span class="text-sm font-semibold">{@render concept("logins")}</span>
          <input
            id={fieldId(LOGINS_PATH)}
            aria-label={t.logins}
            class="field w-full min-w-0"
            type="number"
            inputmode="numeric"
            min={loginsRange.min}
            max={loginsRange.max}
            step={loginsRange.step}
            value={display(LOGINS_PATH, loginWindow(profile).logins)}
            placeholder={t.suggested}
            aria-invalid={errors[LOGINS_PATH] ? "true" : undefined}
            aria-describedby={errors[LOGINS_PATH] ? errorId(LOGINS_PATH) : undefined}
            onchange={(e) => commit(LOGINS_PATH, e.currentTarget, (v) => save(setLoginWindow(profile!, "logins", v)))}
          />
        </label>
        {@render fieldMessage(LOGINS_PATH)}
      </div>
    </div>

    {#each grouped as g (g.group)}
      <details class="mt-6" open={g.group === "production"}>
        <summary class="cursor-pointer font-display text-lg font-semibold">
          {t.groups[g.group]} ({g.rows.length})
        </summary>
        <!-- one card per location: fits a phone without sideways scrolling -->
        <ul class="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {#each g.rows as row (row.id)}
            <li class="tile min-w-0 p-3" data-location={row.id}>
              <div class="flex items-center gap-2">
                <ItemDrawing id={row.id} name={row.name} size={40} decorative />
                <span class="font-display font-semibold">{row.name}</span>
              </div>
              <!-- 11rem: a dropdown shows its whole "level default (X)" text -->
              <div class="mt-2 grid grid-cols-[repeat(auto-fit,minmax(min(11rem,100%),1fr))] gap-2">
                {#each row.fields as f (f)}
                  {@render locationField(row, f)}
                {/each}
              </div>
            </li>
          {/each}
        </ul>
      </details>
    {/each}

    <div class="mt-6 flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="btn btn-primary"
        onclick={calculate}
        disabled={busy || errorList.length > 0}
        data-testid="calculate"
      >
        {busy ? t.calculating : t.calculate}
      </button>
      {#if busy && progress}
        <span class="muted flex items-center gap-2 text-sm" role="status">
          <span class="inline-flex animate-spin motion-reduce:animate-none"
            ><Icon name="loader-circle" size={16} /></span
          >
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
        <details class="mt-3" data-testid="notes">
          <summary class="cursor-pointer font-semibold">{t.warnings} ({plan.warnings.length})</summary>
          <ul class="item-list mt-2">
            {#each plan.warnings as w (w)}<li class="item">{translateWarning(w, t.notes, noteNames)}</li>{/each}
          </ul>
        </details>
      {/if}
      <PlanView schedule={plan.schedule} {lang} />
    </section>
  {/if}
{/if}
