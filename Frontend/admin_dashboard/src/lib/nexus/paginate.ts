/**
 * Pagination arithmetic. Pure functions, no JSX, no network — same contract as every other
 * `lib/nexus/*-view.ts` module, so it is unit-testable in isolation.
 *
 * Two consumers, deliberately kept apart:
 *  - CLIENT paging: the whole result set is already in memory (policies, decisions, escalations,
 *    advisors, reference). `slicePage` cuts the visible window.
 *  - SERVER paging: the backend is already offset-based (customers, tickets, notifications,
 *    callbacks, calls). Only `offsetFor` and the page-token list are used; the rows arrive
 *    pre-cut and MUST NOT be sliced again.
 */

/** Total number of pages for a set. Always >= 1 so the pager never renders "page 1 of 0". */
export function pageCount(total: number, pageSize: number): number {
  if (pageSize <= 0) return 1;
  return Math.max(1, Math.ceil(total / pageSize));
}

/** Clamps a page index into range. Guards against a filter shrinking the set under a high page. */
export function clampPage(page: number, total: number, pageSize: number): number {
  return Math.min(Math.max(0, page), pageCount(total, pageSize) - 1);
}

/** Zero-based page index -> row offset, for server-paginated endpoints. */
export function offsetFor(page: number, pageSize: number): number {
  return Math.max(0, page) * pageSize;
}

/** The visible window of an in-memory set. */
export function slicePage<T>(rows: readonly T[], page: number, pageSize: number): T[] {
  const safe = clampPage(page, rows.length, pageSize);
  return rows.slice(safe * pageSize, safe * pageSize + pageSize);
}

export type PageRange = { from: number; to: number };

/**
 * 1-based inclusive human range for the footer readout: "Showing 13–18 of 1,284".
 * An empty set collapses to { from: 0, to: 0 } so the caller can render "No rows" instead.
 */
export function rangeFor(page: number, pageSize: number, total: number): PageRange {
  if (total === 0) return { from: 0, to: 0 };
  const safe = clampPage(page, total, pageSize);
  const from = safe * pageSize + 1;
  return { from, to: Math.min(total, from + pageSize - 1) };
}

/** A rendered pager slot: either a page to jump to, or a gap standing in for skipped pages. */
export type PageToken = { kind: "page"; page: number } | { kind: "gap"; key: string };

/**
 * Page tokens with elision, e.g. `1 … 4 5 [6] 7 8 … 42`.
 *
 * `siblings` is how many pages flank the current one. First and last are always present, so the
 * token count is stable at `siblings * 2 + 5` once the set is long enough — which matters: a
 * pager whose width changes as you page through it makes the footer jump under the cursor.
 */
export function pageTokens(current: number, total: number, siblings = 1): PageToken[] {
  const last = total - 1;
  if (total <= 0) return [];

  const windowSize = siblings * 2 + 5;
  if (total <= windowSize) {
    return Array.from({ length: total }, (_, page) => ({ kind: "page", page }) as const);
  }

  const start = Math.max(1, Math.min(current - siblings, last - (siblings * 2 + 2)));
  const end = Math.min(last - 1, Math.max(current + siblings, siblings * 2 + 2));

  const tokens: PageToken[] = [{ kind: "page", page: 0 }];
  if (start > 1) tokens.push({ kind: "gap", key: "head" });
  for (let page = start; page <= end; page++) tokens.push({ kind: "page", page });
  if (end < last - 1) tokens.push({ kind: "gap", key: "tail" });
  tokens.push({ kind: "page", page: last });

  return tokens;
}
