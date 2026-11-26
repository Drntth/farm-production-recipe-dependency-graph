// Data safety of the farm profiles (docs/ui-design.md, "Data safety"): the browser may
// delete stored data, only an exported file survives. These rules decide when the page
// reminds the player to export, and how the last export is shown.

export const DAY_MS = 24 * 3600_000;
/** Safari deletes script-written storage after 7 days without a visit: a rule, not a setting. */
export const REMIND_AFTER_MS = 7 * DAY_MS;

/** A stored profile's times (epoch milliseconds): last write and last export. */
export interface BackupTimes {
  updated: number;
  exported?: number;
}

/** The reminder shows when the profile was never exported, or changed since an export older than 7 days. */
export function needsReminder(times: BackupTimes, now: number): boolean {
  if (times.exported === undefined) return true;
  return times.updated > times.exported && now - times.exported > REMIND_AFTER_MS;
}

/** "3 days ago" in the page language; "now" within the last minute. */
export function lastExportAgo(exported: number, now: number, lang: string): string {
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const minutes = Math.floor((now - exported) / 60_000);
  if (minutes < 1) return rtf.format(0, "second");
  if (minutes < 60) return rtf.format(-minutes, "minute");
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return rtf.format(-hours, "hour");
  return rtf.format(-Math.floor(hours / 24), "day");
}
