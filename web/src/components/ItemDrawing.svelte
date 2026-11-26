<script lang="ts">
  // Game item drawing (own SVG) at a given size, on light and dark themes alike.
  // `name` is the English game item name: the accessible name, unless `decorative`
  // (use it when the name is printed next to the drawing).
  import { drawingFor } from "./item-drawings";

  interface Props {
    /** data id, e.g. `chicken_coop`; an unknown id shows the placeholder */
    id: string;
    name: string;
    /** width and height in px */
    size?: number;
    decorative?: boolean;
  }
  let { id, name, size = 48, decorative = false }: Props = $props();

  const drawing = $derived(drawingFor(id));
</script>

<span
  class="item-drawing"
  style:width="{size}px"
  style:height="{size}px"
  style:--tile-pad="{Math.round(size * 0.08)}px"
  role={decorative ? undefined : "img"}
  aria-label={decorative ? undefined : name}
  aria-hidden={decorative ? "true" : undefined}>{@html drawing.svg}</span
>

<style>
  .item-drawing {
    display: inline-block;
    flex-shrink: 0;
    box-sizing: border-box;
    line-height: 0;
  }
  /* the drawings' dark outline would vanish on the dark theme: they sit on a light tile there */
  :global(.dark) .item-drawing {
    /* a % padding would follow the parent's width, not the drawing's size */
    padding: var(--tile-pad);
    border-radius: 22%;
    background: #f6efdc;
  }
  .item-drawing :global(svg) {
    display: block;
    width: 100%;
    height: 100%;
  }
</style>
