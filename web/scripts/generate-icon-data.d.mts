export function documentedIcons(markdown: string): string[];
export function readLucideIcons(): { icons: Record<string, { body: string }> };
export function buildIconData(lucide: { icons: Record<string, { body: string }> }, names: string[]): string;
