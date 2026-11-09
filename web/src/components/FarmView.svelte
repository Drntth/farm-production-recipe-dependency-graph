<script lang="ts">
  // The farm view: the level's layout drawn as an isometric SVG on the base map,
  // with pan and zoom (wheel, drag, pinch, + / − / reset buttons, keyboard), and
  // the block cards below it. Hovering or focusing a block on the map or its card
  // highlights both; selecting one (click, tap, Enter on the card) dims the
  // others, zooms to it and opens its details (× or Esc closes them).
  // Rendered on the server too, so without JavaScript the map and the cards
  // still show (only the controls are hidden). Tile (x, y) maps to the screen like
  // the game and `src/layout/render_svg.py`: x runs ↘, y runs ↙; a tile is 2 × 1 units.
  import { untrack } from "svelte";
  import type { Block, FlowLink, LayoutBlock, MapView } from "../data";

  interface Labels {
    map: string;
    hint: string;
    zoomIn: string;
    zoomOut: string;
    reset: string;
    reserved: string;
    blocks: string;
    blockFields: string;
    notPlacedTag: string;
    details: string;
    close: string;
    busy: string;
    perHour: string;
    reservedCopies: string;
    fieldsReserved: string;
    flowsIn: string;
    flowsOut: string;
    notPlacedDetail: string;
  }
  interface Props {
    map: MapView;
    /** blocks as placed (frames, items), in layout order: the colour order */
    layout: LayoutBlock[];
    /** blocks with their buildings, fields and production */
    blocks: Block[];
    flows: FlowLink[];
    /** number format locale, e.g. "en-GB" */
    locale: string;
    labels: Labels;
  }
  let { map, layout, blocks, flows, locale, labels }: Props = $props();

  // the block colours of render_svg.py (Okabe-Ito based), by block order
  const PALETTE = [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#D55E00",
    "#56B4E9",
    "#8C6D1F",
    "#6A3D9A",
    "#B22222",
    "#2E8B57",
    "#4B5563",
    "#C71585",
    "#1F4E79",
    "#9A6324",
    "#469990",
    "#911EB4",
    "#808000",
    "#E6194B",
  ];
  const PAD = 2; // tiles around the initial view
  const MIN_W = 8; // narrowest view in units (about four tiles)
  const ZOOM_STEP = 1.4;

  const fill = (text: string, values: Record<string, string | number>) =>
    text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
  // game item names stay English, like label() in data.ts (which reads files, so not importable here)
  const label = (id: string) => {
    const text = id.replaceAll("_", " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  };
  const num = (n: number, digits = 2) => n.toLocaleString(locale, { maximumFractionDigits: digits });

  type Rect = [number, number, number, number];
  type View = { x: number; y: number; w: number; h: number };

  const pt = (x: number, y: number) => `${x - y},${(x + y) / 2}`;
  const diamond = ([x, y, w, h]: Rect) => `${pt(x, y)} ${pt(x + w, y)} ${pt(x + w, y + h)} ${pt(x, y + h)}`;
  const rectOf = (r: { x: number; y: number; width: number; height: number }): Rect => [r.x, r.y, r.width, r.height];

  /** Screen box (units) of a tile rect. */
  function bounds([x, y, w, h]: Rect): View {
    return { x: x - (y + h), y: (x + y) / 2, w: w + h, h: (w + h) / 2 };
  }

  const full = $derived(bounds([0, 0, map.width, map.height]));
  const home = $derived.by(() => {
    const [x, y, w, h] = map.usable_bounds ?? [0, 0, map.width, map.height];
    return bounds([x - PAD, y - PAD, w + 2 * PAD, h + 2 * PAD]);
  });
  const maxW = $derived(full.w * 1.2);

  let box: HTMLDivElement | undefined = $state();
  let ready = $state(false);
  let aspect = $state(0); // container height / width once mounted
  let boxWidth = $state(0); // container width in pixels once mounted
  let view: View = $state({ x: 0, y: 0, w: 1, h: 1 });

  /** *v* reshaped to the container's aspect around its centre (meet: nothing is cut off). */
  function fit(v: View): View {
    if (!aspect) return v;
    const w = Math.max(v.w, v.h / aspect);
    const h = w * aspect;
    return { x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h };
  }

  function reset() {
    view = fit(home);
  }

  /** Zoom by *factor* (>1 = in) around the point (fx, fy) given as a share of the view. */
  function zoom(factor: number, fx = 0.5, fy = 0.5) {
    const w = Math.min(maxW, Math.max(MIN_W, view.w / factor));
    const h = (w * view.h) / view.w;
    view = { x: view.x + (view.w - w) * fx, y: view.y + (view.h - h) * fy, w, h };
  }

  /** Move the view by a screen distance in pixels. */
  function pan(dx: number, dy: number) {
    if (!box) return;
    const s = view.w / box.clientWidth;
    view = { ...view, x: view.x - dx * s, y: view.y - dy * s };
  }

  // highlight (hover / focus) and selection, shared by the map and the cards
  let hot: string | null = $state(null);
  let selected: string | null = $state(null);

  function zoomTo(id: string) {
    const f = layout.find((b) => b.id === id)?.frame;
    if (f) view = fit(bounds([f.x - PAD, f.y - PAD, f.width + 2 * PAD, f.height + 2 * PAD]));
  }
  function select(id: string) {
    if (selected === id) return close();
    selected = id;
    zoomTo(id);
  }
  function close() {
    const id = selected;
    selected = null;
    // back to the card that opened the details, so keyboard users keep their place
    if (id) document.querySelector<HTMLElement>(`[data-card="${id}"] button`)?.focus({ preventScroll: true });
  }
  function escape(e: KeyboardEvent) {
    if (e.key === "Escape" && selected) {
      e.preventDefault();
      close();
    }
  }

  $effect(() => {
    if (!box) return;
    const el = box;
    // untracked: the effect only sets up the listeners once per mount
    const measure = () =>
      untrack(() => {
        aspect = el.clientHeight / el.clientWidth;
        boxWidth = el.clientWidth;
        view = fit(ready ? view : home);
        ready = true;
      });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    // wheel needs a non-passive listener to keep the page from scrolling
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoom(Math.exp(-e.deltaY * 0.0015), (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => {
      ro.disconnect();
      el.removeEventListener("wheel", wheel);
    };
  });

  // pointers: one drags, two pinch (distance → zoom, midpoint → pan)
  const pointers = new Map<number, { x: number; y: number }>();
  // a press that did not move (more than a few pixels) selects the block under it
  let press: { id: string | null; x: number; y: number; moved: boolean } | null = null;
  function spread() {
    const [a, b] = [...pointers.values()];
    return { d: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
  }
  function down(e: PointerEvent) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    try {
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    } catch {
      // a pointer the browser does not know (synthetic events): no capture
    }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const target = (e.target as Element).closest?.("[data-block]");
    press =
      pointers.size === 1
        ? { id: target?.getAttribute("data-block") ?? null, x: e.clientX, y: e.clientY, moved: false }
        : null;
  }
  function move(e: PointerEvent) {
    const last = pointers.get(e.pointerId);
    if (!last || !box) return;
    if (press && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 4) press.moved = true;
    if (pointers.size === 1) {
      pan(e.clientX - last.x, e.clientY - last.y);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      return;
    }
    const before = spread();
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const after = spread();
    const r = box.getBoundingClientRect();
    if (before.d > 0) zoom(after.d / before.d, (after.mx - r.left) / r.width, (after.my - r.top) / r.height);
    pan(after.mx - before.mx, after.my - before.my);
  }
  function up(e: PointerEvent) {
    const was = pointers.delete(e.pointerId);
    if (was && e.type === "pointerup" && pointers.size === 0 && press?.id && !press.moved) select(press.id);
    if (pointers.size === 0) press = null;
  }

  function key(e: KeyboardEvent) {
    const step = 0.1 * (box?.clientWidth ?? 0);
    const keys: Record<string, () => void> = {
      ArrowLeft: () => pan(step, 0),
      ArrowRight: () => pan(-step, 0),
      ArrowUp: () => pan(0, step),
      ArrowDown: () => pan(0, -step),
      "+": () => zoom(ZOOM_STEP),
      "=": () => zoom(ZOOM_STEP),
      "-": () => zoom(1 / ZOOM_STEP),
      "0": reset,
    };
    const run = keys[e.key];
    if (run && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      run();
    }
  }

  const shown = $derived(ready ? view : home);
  // block names keep about 12 px on screen at any zoom (before mount: a fixed size)
  const labelSize = $derived(ready && boxWidth ? (12 * shown.w) / boxWidth : 1.2);
  const viewBox = $derived([shown.x, shown.y, shown.w, shown.h].map((n) => +n.toFixed(3)).join(" "));
  const colour = $derived(new Map(layout.map((b, i) => [b.id, PALETTE[i % PALETTE.length]])));
  const placed = $derived(layout.filter((b) => b.frame !== null));
  const names = $derived({
    field: "Field",
    ...Object.fromEntries(blocks.flatMap((b) => b.locations).map((l) => [l.id, l.name])),
  } as Record<string, string>);
  const blockName = $derived(new Map(blocks.map((b) => [b.id, b.name])));
  const detail = $derived(blocks.find((b) => b.id === selected) ?? null);
  const flowsIn = $derived(flows.filter((f) => f.target === selected));
  const flowsOut = $derived(flows.filter((f) => f.source === selected));
  const dim = (id: string) => selected !== null && selected !== id;
  const labelAt = (f: NonNullable<LayoutBlock["frame"]>) => {
    const cx = f.x + f.width / 2;
    const cy = f.y + f.height / 2;
    return { x: cx - cy, y: (cx + cy) / 2 };
  };
</script>

<svelte:window onkeydown={escape} />

<div class="farm-view">
  <div class="relative">
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
      bind:this={box}
      class="farm-box overflow-hidden rounded-xl border border-line"
      role="group"
      tabindex="0"
      aria-label={labels.map}
      aria-describedby="farm-view-hint"
      onpointerdown={down}
      onpointermove={move}
      onpointerup={up}
      onpointercancel={up}
      onkeydown={key}
    >
      <svg
        {viewBox}
        class="block h-full w-full"
        role="img"
        aria-label={labels.map}
        data-testid="farm-view"
        font-family="inherit"
      >
        <polygon class="fv-outside" points={diamond([0, 0, map.width, map.height])} />
        {#each map.usable as r, i (i)}
          <polygon class="fv-usable" points={diamond(r)} />
        {/each}
        {#each map.farm_outline as [x1, y1, x2, y2], i (i)}
          <line class="fv-outline" x1={x1 - y1} y1={(x1 + y1) / 2} x2={x2 - y2} y2={(x2 + y2) / 2} />
        {/each}
        {#each map.fixed as f (f.id)}
          <polygon class="fv-fixed" points={diamond(rectOf(f))}><title>{f.name}</title></polygon>
        {/each}
        {#each placed as b (b.id)}
          <g
            class="fv-block"
            class:fv-hot={hot === b.id || selected === b.id}
            class:fv-dim={dim(b.id)}
            data-block={b.id}
            style:--block={colour.get(b.id)}
            onpointerenter={() => (hot = b.id)}
            onpointerleave={() => (hot = null)}
            role="presentation"
          >
            <title>{b.name}</title>
            <polygon class="fv-frame" points={diamond(rectOf(b.frame!))} />
            {#each b.items as item, i (i)}
              <polygon
                class="fv-item"
                class:fv-field={item.location_id === "field"}
                class:fv-reserved={item.reserved}
                points={diamond(rectOf(item))}
              >
                <title
                  >{names[item.location_id] ?? item.location_id}{item.reserved ? ` (${labels.reserved})` : ""}</title
                >
              </polygon>
            {/each}
          </g>
        {/each}
        {#each placed as b (b.id)}
          {@const at = labelAt(b.frame!)}
          <text
            class="fv-label"
            class:fv-dim={dim(b.id)}
            font-size={labelSize.toFixed(3)}
            stroke-width={(labelSize / 4).toFixed(3)}
            x={at.x}
            y={at.y}
            text-anchor="middle"
            dominant-baseline="middle">{b.name}</text
          >
        {/each}
      </svg>
    </div>
    {#if ready}
      <div class="absolute top-2 right-2 flex flex-col gap-1" data-testid="farm-controls">
        <button
          type="button"
          class="icon-btn bg-surface"
          aria-label={labels.zoomIn}
          title={labels.zoomIn}
          onclick={() => zoom(ZOOM_STEP)}>+</button
        >
        <button
          type="button"
          class="icon-btn bg-surface"
          aria-label={labels.zoomOut}
          title={labels.zoomOut}
          onclick={() => zoom(1 / ZOOM_STEP)}>−</button
        >
        <button
          type="button"
          class="icon-btn bg-surface text-xs"
          aria-label={labels.reset}
          title={labels.reset}
          onclick={reset}>⌂</button
        >
      </div>
    {/if}
  </div>
  <p id="farm-view-hint" class="muted mt-2 text-sm">{labels.hint}</p>

  {#if detail}
    <section
      class="tile fv-details mt-4"
      style:--block={colour.get(detail.id) ?? "var(--muted)"}
      aria-labelledby="fv-details-title"
      data-testid="block-details"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="muted text-xs">{labels.details}</p>
          <h3 id="fv-details-title" class="text-xl">{detail.name}</h3>
        </div>
        <button type="button" class="icon-btn" aria-label={labels.close} title={labels.close} onclick={close}>×</button>
      </div>
      {#if !detail.placed}
        <p class="warning mt-3">{labels.notPlacedDetail}</p>
      {/if}
      <ul class="mt-3 grid gap-2 sm:grid-cols-2">
        {#each detail.locations as l (l.id)}
          <li>
            <p class="font-semibold">
              {l.name} <b>×{l.copies}</b>
              {#if l.reserved > 0}<span class="muted text-sm font-normal">
                  · {fill(labels.reservedCopies, { n: l.reserved })}</span
                >{/if}
            </p>
            {#if l.busy !== undefined}
              <p class="muted text-sm">{fill(labels.busy, { n: Math.round(l.busy * 100) })}</p>
            {/if}
            {#if l.per_hour && Object.keys(l.per_hour).length > 0}
              <p class="text-sm">
                {labels.perHour}
                {Object.entries(l.per_hour)
                  .map(([id, n]) => `${label(id)} ${num(n)}`)
                  .join(", ")}
              </p>
            {/if}
          </li>
        {/each}
      </ul>
      {#if detail.fields && detail.fields.count > 0}
        <p class="mt-3 text-sm">
          {fill(labels.blockFields, { n: detail.fields.count })}{#if detail.fields.reserved > 0}{" "}({fill(
              labels.fieldsReserved,
              { n: detail.fields.reserved },
            )}){/if}{#if detail.fields.crops.length > 0}: {detail.fields.crops.map(label).join(", ")}{/if}
        </p>
      {/if}
      {#each [[labels.flowsIn, flowsIn, "source"], [labels.flowsOut, flowsOut, "target"]] as const as [title, list, side] (side)}
        {#if list.length > 0}
          <p class="mt-2 text-sm">
            {title}
            {list.map((f) => `${blockName.get(f[side]) ?? label(f[side])} ${num(f.per_hour)}`).join(", ")}
          </p>
        {/if}
      {/each}
    </section>
  {/if}

  <ul class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label={labels.blocks} data-testid="blocks">
    {#each blocks as b (b.id)}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
      <li
        class="tile fv-card"
        class:fv-hot={hot === b.id}
        class:fv-selected={selected === b.id}
        class:fv-dim={dim(b.id)}
        style:--block={colour.get(b.id) ?? "var(--muted)"}
        data-card={b.id}
        onpointerenter={() => (hot = b.id)}
        onpointerleave={() => (hot = null)}
        onclick={(e) => {
          if (ready && !(e.target as Element).closest("button")) select(b.id);
        }}
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-lg">
            <button
              type="button"
              class="fv-card-btn"
              aria-pressed={selected === b.id}
              disabled={!ready}
              onclick={() => select(b.id)}
              onfocus={() => (hot = b.id)}
              onblur={() => (hot = null)}
            >
              <span class="fv-swatch" aria-hidden="true"></span>{b.name}
            </button>
          </h3>
          {#if !b.placed}<span class="badge badge-warn">{labels.notPlacedTag}</span>{/if}
        </div>
        <ul class="item-list mt-2">
          {#each b.locations as l (l.id)}
            <li class="item">{l.name} <b>×{l.copies}</b></li>
          {/each}
        </ul>
        {#if b.fields && b.fields.count > 0}
          <p class="muted mt-2 text-sm">
            {fill(labels.blockFields, { n: b.fields.count })}{#if b.fields.crops.length > 0}: {b.fields.crops
                .map(label)
                .join(", ")}{/if}
          </p>
        {/if}
      </li>
    {/each}
  </ul>
</div>

<style>
  .farm-box {
    aspect-ratio: 4 / 3;
    max-height: 75vh;
    width: 100%;
    touch-action: none;
    cursor: grab;
    background: var(--surface);
  }
  .farm-box:active {
    cursor: grabbing;
  }
  .farm-box:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  @media (min-width: 640px) {
    .farm-box {
      aspect-ratio: 16 / 10;
    }
  }
  svg :global(polygon),
  svg :global(line) {
    vector-effect: non-scaling-stroke;
  }
  .fv-outside {
    fill: var(--line);
    opacity: 0.35;
  }
  .fv-usable {
    fill: color-mix(in srgb, var(--grass) 55%, var(--surface));
  }
  .fv-outline {
    stroke: var(--muted);
    stroke-width: 1px;
  }
  .fv-fixed {
    fill: var(--muted);
    opacity: 0.45;
    stroke: var(--muted);
    stroke-width: 1px;
  }
  .fv-frame {
    fill: var(--block);
    fill-opacity: 0.08;
    stroke: var(--block);
    stroke-width: 1.5px;
    stroke-dasharray: 4 3;
  }
  .fv-item {
    fill: var(--block);
    fill-opacity: 0.85;
    stroke: var(--surface);
    stroke-width: 1px;
  }
  .fv-item.fv-field {
    fill-opacity: 0.45;
  }
  .fv-item.fv-reserved {
    fill-opacity: 0.15;
    stroke: var(--block);
    stroke-dasharray: 2 2;
  }
  .fv-block {
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .fv-hot .fv-frame {
    fill-opacity: 0.25;
    stroke-width: 3px;
    stroke-dasharray: none;
  }
  .fv-dim {
    opacity: 0.25;
  }
  .fv-details {
    border-left: 4px solid var(--block);
  }
  .fv-card {
    transition:
      opacity 0.2s,
      box-shadow 0.2s;
    cursor: pointer;
  }
  .fv-card.fv-hot,
  .fv-card.fv-selected {
    box-shadow: 0 0 0 2px var(--block);
  }
  .fv-card-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    text-align: left;
    font: inherit;
    cursor: pointer;
  }
  .fv-card-btn:disabled {
    cursor: default;
    color: inherit;
  }
  .fv-card-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 4px;
  }
  .fv-swatch {
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 3px;
    background: var(--block);
    flex-shrink: 0;
  }
  @media (prefers-reduced-motion: reduce) {
    .fv-block,
    .fv-card {
      transition: none;
    }
  }
  .fv-label {
    font-weight: 700;
    fill: var(--fg);
    stroke: var(--surface);
    paint-order: stroke;
    pointer-events: none;
  }
</style>
