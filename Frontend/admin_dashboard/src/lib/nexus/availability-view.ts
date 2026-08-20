import type { CoverageHour, Shift } from "@/lib/api/availability.server";

/* Monday-first, matching Python's datetime.weekday(). See finding F4. */
export const WEEKDAY_LABELS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

export const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export function hhmmToMinutes(value: string): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return Number.NaN;
  return Number(match[1]) * 60 + Number(match[2]);
}

export function minutesToHhmm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/* ---------- grid editing ---------- */

export type GridWindow = {
  uid: string;
  weekday: number;
  start: string;
  end: string;
  is_active: boolean;
};

let uidCounter = 0;
export function newUid(): string {
  uidCounter += 1;
  return `w${uidCounter}`;
}

export function shiftsToGrid(shifts: Shift[]): GridWindow[] {
  return shifts.map((s) => ({
    uid: newUid(),
    weekday: s.weekday,
    start: s.start,
    end: s.end,
    is_active: s.is_active,
  }));
}

export function gridToWindows(grid: GridWindow[]) {
  return grid.map(({ weekday, start, end, is_active }) => ({
    weekday,
    start,
    end,
    is_active,
  }));
}

/**
 * Mirrors replace_shifts() exactly, including the detail that the server checks
 * overlaps across ALL windows regardless of is_active. See finding F5.
 * Returns null when valid, otherwise a human message.
 */
export function validateGrid(grid: GridWindow[]): string | null {
  for (const w of grid) {
    const start = hhmmToMinutes(w.start);
    const end = hhmmToMinutes(w.end);
    const day = WEEKDAY_LABELS[w.weekday] ?? `weekday ${w.weekday}`;
    if (Number.isNaN(start) || Number.isNaN(end)) {
      return `${day}: times must be written as HH:MM.`;
    }
    if (start < 0 || start > 1440 || end < 0 || end > 1440) {
      return `${day}: times must fall between 00:00 and 24:00.`;
    }
    if (end <= start) {
      return `${day}: the end time must be after the start time.`;
    }
  }
  for (let day = 0; day < 7; day += 1) {
    const rows = grid
      .filter((w) => w.weekday === day)
      .sort((a, b) => hhmmToMinutes(a.start) - hhmmToMinutes(b.start));
    for (let i = 1; i < rows.length; i += 1) {
      const prev = rows[i - 1];
      const curr = rows[i];
      if (prev && curr && hhmmToMinutes(curr.start) < hhmmToMinutes(prev.end)) {
        return `${WEEKDAY_LABELS[day]}: two windows overlap. Disabling one does not help — the server rejects overlaps either way.`;
      }
    }
  }
  return null;
}

export function weeklyHours(grid: GridWindow[]): number {
  const minutes = grid
    .filter((w) => w.is_active)
    .reduce((sum, w) => sum + (hhmmToMinutes(w.end) - hhmmToMinutes(w.start)), 0);
  return Math.round((minutes / 60) * 10) / 10;
}

/* ---------- business-time conversion for writes. See finding F3. ---------- */

export function businessZoneOffset(instant: Date, timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      timeZoneName: "longOffset",
    }).formatToParts(instant);
    const name = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
    const match = /GMT([+-]\d{2}:\d{2})/.exec(name);
    return match?.[1] ?? "+00:00";
  } catch {
    return "+00:00";
  }
}

/**
 * "2026-08-05T09:00" (business wall clock) -> "2026-08-05T09:00:00+01:00".
 * Without this the backend reads the naive string as UTC and silently shifts
 * the absence by the zone offset.
 */
export function businessLocalToIso(localValue: string, timeZone: string): string {
  const normalised = localValue.length === 16 ? `${localValue}:00` : localValue;
  const probe = new Date(`${normalised}Z`);
  const offset = businessZoneOffset(Number.isNaN(probe.getTime()) ? new Date() : probe, timeZone);
  return `${normalised}${offset}`;
}

/** Renders an API ISO instant in business time without leaking browser time. */
export function formatBusinessInstant(iso: string, timeZone: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

/* ---------- coverage matrix ---------- */

export type CoverageMatrix = {
  hourLabels: string[];
  days: { date: string; label: string; cells: (CoverageHour | null)[] }[];
  peak: number;
};

/**
 * Pivots the flat hour list into day rows x hour columns.
 * The hour axis is derived from the payload, never hardcoded: DAY_START_HOUR
 * and DAY_END_HOUR are environment variables. See §3.1.
 */
export function coverageMatrix(hours: CoverageHour[]): CoverageMatrix {
  const hourLabels = [...new Set(hours.map((h) => h.local.slice(11, 16)))].sort();
  const byDate = new Map<string, Map<string, CoverageHour>>();
  for (const hour of hours) {
    const date = hour.local.slice(0, 10);
    const hh = hour.local.slice(11, 16);
    if (!byDate.has(date)) byDate.set(date, new Map());
    byDate.get(date)!.set(hh, hour);
  }
  const days = [...byDate.keys()].sort().map((date) => ({
    date,
    label: dayLabel(date),
    cells: hourLabels.map((hh) => byDate.get(date)!.get(hh) ?? null),
  }));
  const peak = hours.reduce((max, h) => Math.max(max, h.advisors), 0);
  return { hourLabels, days, peak };
}

/** "2026-08-03" -> "Mon 03 Aug". Parsed as parts, never through Date(string). */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  const utc = new Date(Date.UTC(y, m - 1, d));
  const weekday = (utc.getUTCDay() + 6) % 7; // shift Sunday-first to Monday-first
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${WEEKDAY_SHORT[weekday]} ${String(d).padStart(2, "0")} ${months[m - 1]}`;
}

/**
 * Achromatic intensity, taken straight from the existing scale in styles.css.
 * blocks.tsx already uses bg-n-12 / bg-n-8 / bg-n-7 for chart marks, so this
 * introduces no token and no colour.
 */
export function coverageTone(count: number, peak: number): string {
  /*
   * Outlined, not flooded.
   *
   * Solid fills made the grid read as a heat map of blocks — a wall of grey rectangles where the
   * eye could not separate one hour from the next, and where "thin cover" and "no cover" looked
   * more alike than they are. Every cell now carries a border and the FILL carries the load:
   * an empty hour is an outline only, a full hour is solid. That reads as a scale rather than as
   * a texture, and it keeps the whole grid lighter.
   *
   * Still achromatic: n-7/n-9/n-11 are the same three marks blocks.tsx uses for chart geometry.
   */
  if (count <= 0) return "border border-dashed border-stroke-strong bg-transparent";
  if (peak <= 1) return "border border-n-11 bg-n-11/85";

  const ratio = count / peak;
  if (ratio >= 0.75) return "border border-n-11 bg-n-11/85";
  if (ratio >= 0.4) return "border border-n-9 bg-n-9/45";
  return "border border-n-8 bg-n-8/15";
}
