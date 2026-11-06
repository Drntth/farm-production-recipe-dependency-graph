<script lang="ts">
  // Jump to a level page; the level list below it works without JavaScript.
  interface Props {
    levels: number[];
    base: string;
    current?: number;
  }
  let { levels, base, current }: Props = $props();
  let level = $state(current ?? levels[0]);

  function go(event: SubmitEvent) {
    event.preventDefault();
    window.location.href = `${base.replace(/\/$/, "")}/levels/${level}/`;
  }
</script>

<form class="picker" onsubmit={go}>
  <label for="level-select">Level</label>
  <select id="level-select" bind:value={level}>
    {#each levels as n (n)}
      <option value={n}>{n}</option>
    {/each}
  </select>
  <button type="submit">Show</button>
</form>

<style>
  .picker {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  select,
  button {
    font: inherit;
    padding: 4px 10px;
  }
</style>
