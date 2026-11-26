<script lang="ts">
  // Lucide icon for Svelte islands (the .astro pages use astro-icon instead).
  // Decorative by default; pass `label` only when the icon stands alone.
  import { LUCIDE_ICONS, type IconName } from "./icon-data";

  interface Props {
    name: IconName;
    /** width and height in px */
    size?: number;
    /** accessible name, only when the icon carries meaning without visible text */
    label?: string;
  }
  let { name, size = 24, label }: Props = $props();

  // the body is trusted: it comes from the generated icon-data.ts
  const markup = $derived(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false" aria-hidden="true">${LUCIDE_ICONS[name].body}</svg>`,
  );
</script>

<span
  class="inline-flex shrink-0 align-[-0.125em] leading-none"
  role={label ? "img" : undefined}
  aria-label={label}
  aria-hidden={label ? undefined : "true"}>{@html markup}</span
>
