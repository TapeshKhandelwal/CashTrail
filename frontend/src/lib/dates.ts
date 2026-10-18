/**
 * Business dates are IST calendar days ("2026-10-17"); timestamps are ISO-8601 with an offset.
 * Everything renders in Asia/Kolkata regardless of the device's timezone.
 */

export const TIME_ZONE = "Asia/Kolkata";
const LOCALE = "en-IN";

/** "YYYY-MM-DD" in IST. */
export type ISODate = string;

const isoDateFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function toISODate(date: Date): ISODate {
  return isoDateFormat.format(date);
}

/** Calendar pickers hand back local-midnight Dates; keep their calendar day as-is. */
export function fromPickerDate(date: Date): ISODate {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function toPickerDate(value: ISODate): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function todayIST(now: Date = new Date()): ISODate {
  return toISODate(now);
}

/** Business dates are calendar days, so they are anchored at UTC noon to never cross a day boundary. */
function fromISODate(value: ISODate): Date {
  return new Date(`${value}T12:00:00Z`);
}

export function addDays(value: ISODate, days: number): ISODate {
  const date = fromISODate(value);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(from: ISODate, to: ISODate): number {
  return Math.round((fromISODate(to).getTime() - fromISODate(from).getTime()) / 86_400_000);
}

export function startOfMonth(value: ISODate): ISODate {
  return `${value.slice(0, 8)}01`;
}

const isDateOnly = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);

function toDate(value: string | Date): { date: Date; zone: string } {
  if (value instanceof Date) return { date: value, zone: TIME_ZONE };
  return isDateOnly(value)
    ? { date: fromISODate(value), zone: "UTC" }
    : { date: new Date(value), zone: TIME_ZONE };
}

function format(value: string | Date, options: Intl.DateTimeFormatOptions): string {
  const { date, zone } = toDate(value);
  return new Intl.DateTimeFormat(LOCALE, { timeZone: zone, ...options }).format(date);
}

/** "17 Oct 2026" */
export const formatDate = (value: string | Date) =>
  format(value, { day: "numeric", month: "short", year: "numeric" });

/** "17 Oct" */
export const formatDayMonth = (value: string | Date) => format(value, { day: "numeric", month: "short" });

/** "2:05 pm" */
export const formatTime = (value: string | Date) =>
  format(value, { hour: "numeric", minute: "2-digit", hour12: true });

/** "17 Oct 2026, 2:05 pm" */
export const formatDateTime = (value: string | Date) =>
  format(value, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

/** "Friday, 17 October" (agent greeting caption). */
export const formatLongDay = (value: string | Date) =>
  format(value, { weekday: "long", day: "numeric", month: "long" });

const relative = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** "4 minutes ago", "yesterday", "in 2 days". */
export function formatRelative(value: string | Date, now: Date = new Date()): string {
  const seconds = Math.round((toDate(value).date.getTime() - now.getTime()) / 1000);
  for (const [unit, size] of RELATIVE_STEPS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.trunc(seconds / size), unit);
  }
  return "just now";
}

/** Hours since a timestamp, for "held since" style ageing badges. */
export function hoursSince(value: string, now: Date = new Date()): number {
  return Math.max(0, Math.floor((now.getTime() - new Date(value).getTime()) / 3_600_000));
}

export function greeting(now: Date = new Date()): string {
  const hour = Number(format(now, { hour: "numeric", hour12: false }));
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export interface DateRange {
  from: ISODate;
  to: ISODate;
}

export type DateRangePreset = "today" | "yesterday" | "last7" | "last30" | "thisMonth";

export const DATE_RANGE_PRESETS: { id: DateRangePreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "last7", label: "Last 7 days" },
  { id: "last30", label: "Last 30 days" },
  { id: "thisMonth", label: "This month" },
];

export function presetRange(preset: DateRangePreset, today: ISODate = todayIST()): DateRange {
  switch (preset) {
    case "today":
      return { from: today, to: today };
    case "yesterday": {
      const day = addDays(today, -1);
      return { from: day, to: day };
    }
    case "last7":
      return { from: addDays(today, -6), to: today };
    case "last30":
      return { from: addDays(today, -29), to: today };
    case "thisMonth":
      return { from: startOfMonth(today), to: today };
  }
}

export function formatRange({ from, to }: DateRange): string {
  return from === to ? formatDate(from) : `${formatDayMonth(from)} – ${formatDate(to)}`;
}
