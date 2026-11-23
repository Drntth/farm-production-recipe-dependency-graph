<script lang="ts">
  // Jump to a level page. `compact`: a bare select that navigates on change
  // (the level page's ‹ N › switch); otherwise a labelled form with a button.
  interface Props {
    levels: number[];
    /** the level pages' path prefix in the page's language, e.g. `<base>/hu/levels/` */
    base: string;
    current?: number;
    /** path after the level, e.g. `plan/`: the switch stays on the open tab */
    suffix?: string;
    compact?: boolean;
    labels: { label: string; show: string };
  }
  let { levels, base, current, suffix = "", compact = false, labels }: Props = $props();
  const initial = current ?? levels[0];
  let select: HTMLSelectElement;

  // read the select itself, not a bound state: a level picked before the
  // island loaded (slow phone) is in the DOM, and hydration must not reset it
  function go() {
    window.location.href = `${base.replace(/\/$/, "")}/${select.value}/${suffix}`;
  }
  function submit(event: SubmitEvent) {
    event.preventDefault();
    go();
  }
</script>

<form class="flex flex-wrap items-center gap-2" onsubmit={submit}>
  <label for="level-select" class={compact ? "sr-only" : "font-semibold"}>{labels.label}</label>
  <select
    id="level-select"
    class={compact ? "field font-display text-lg font-semibold" : "field"}
    bind:this={select}
    onchange={compact ? go : undefined}
  >
    {#each levels as n (n)}
      <option value={n} selected={n === initial}>{n}</option>
    {/each}
  </select>
  {#if !compact}
    <button type="submit" class="btn btn-primary">{labels.show}</button>
  {/if}
</form>
