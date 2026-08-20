import { useSyncExternalStore } from "react";

/**
 * Rows per page, derived from the viewport instead of hard-coded.
 *
 * The goal is a list that fills the screen and stops: no page-level scrollbar under the table,
 * no 10 000px wall of records, and no fixed "6" that wastes half a 1440p display while
 * overflowing a laptop. The pager at the bottom becomes the only way through the set, which is
 * exactly the behaviour we want people to reach for.
 *
 * SSR-safe: `getServerSnapshot` returns `fallback`, so the server renders a stable page size and
 * the client re-derives on hydration.
 */

type Options = {
  /** Height of one row, in px. `Td` is 52px; card rows run taller. */
  rowHeight: number;
  /** Vertical space consumed by everything that is not rows: topbar, headers, toolbar, footer. */
  chrome: number;
  min: number;
  max: number;
  /** Page size used during SSR and before the first measurement. */
  fallback: number;
};

function subscribe(onChange: () => void): () => void {
  window.addEventListener("resize", onChange, { passive: true });
  return () => window.removeEventListener("resize", onChange);
}

/**
 * Quantised so that a few pixels of resize do not churn the page size (and with it the query key
 * on server-paginated pages). Only crossing a whole-row boundary changes the answer.
 */
function measure({ rowHeight, chrome, min, max }: Options): number {
  const available = window.innerHeight - chrome;
  return Math.min(max, Math.max(min, Math.floor(available / rowHeight)));
}

export function useAdaptivePageSize(options: Options): number {
  return useSyncExternalStore(
    subscribe,
    () => measure(options),
    () => options.fallback,
  );
}

/** Row-height presets, so callers do not re-derive the table metrics from memory. */
export const ROW_HEIGHT = {
  /** `Td h-[52px]` — the standard single-line table row. */
  table: 52,
  /** Table rows whose cells stack (policies thresholds, decisions tokens). */
  stacked: 76,
  /** Master-list buttons on /calls and /escalations. */
  listItem: 72,
} as const;
