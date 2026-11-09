<script lang="ts">
  // Jump to a level page. `compact`: a bare select that navigates on change
  // (the level page's ‹ N › switch); otherwise a labelled form with a button.
  interface Props {
    levels: number[];
    /** the level pages' path prefix in the page's language, e.g. `<base>/hu/levels/` */
    base: string;
    current?: number;
    compact?: boolean;
    labels: { label: string; show: string };
  }
  let { levels, base, current, compact = false, labels }: Props = $props();
  let level = $state(current ?? levels[0]);

  function go() {
    window.location.href = `${base.replace(/\/$/, "")}/${level}/`;
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
    bind:value={level}
    onchange={compact ? go : undefined}
  >
    {#each levels as n (n)}
      <option value={n}>{n}</option>
    {/each}
  </select>
  {#if !compact}
    <button type="submit" class="btn btn-primary">{labels.show}</button>
  {/if}
</form>
