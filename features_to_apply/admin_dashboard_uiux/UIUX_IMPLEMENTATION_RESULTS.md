# Admin Console — UI/UX Implementation Results

**Target:** `Frontend/admin_dashboard` (NOT `customer_portal`)
**Date:** 2026-08-20
**Scope:** presentation layer, plus one new read-only server function for sidebar counts (explicitly approved).

**Gates:** `tsc --noEmit` clean · `eslint src` 0 errors (8 pre-existing warnings) · **140/140 tests pass** · `npm run build` succeeds.

---

## 0. Decisions taken from your answers

| Question | Your answer | What shipped |
|---|---|---|
| Brand | "Admin Console" + geometric mark | `lib/nexus/brand.ts` + `<BrandMark />` — a terminal caret and baseline rule, square caps, no circles (bible ch. 4.6). Renaming is now a **one-line edit**. |
| Page size | "adapted and responsive… use what's best" | Rows-per-page is **derived from the viewport**, not fixed. `useAdaptivePageSize` sizes each table so it ends just below the fold. Ranges are per-page-type (5–10 for stacked rows, 6–16 for single-line rows). |
| Sidebar counts | "make it backend" | New `getNavCounts` server function fans out to three upstreams server-side and returns one object. Real fetch, one request, 30s stale / 60s refresh. |
| framer-motion | "yes, install" | Installed (13.1.1). Used **only** where CSS provably cannot do the job: exit animations, presence swaps, `height:auto`. CSS keeps the cheap work. |

**Palette untouched.** Verified live in the browser: `--n-0: #000`, `--n-12: #fff`, `--surface-0: #0a0a0a`, `--ease-out: cubic-bezier(.16,1,.3,1)`. Zero new tokens, zero colour. The reference screenshots' red/green trend chips would have broken the bible's "achromatic by law" rule, so trend direction is carried by **form** instead — the `Delta` arrow glyph, `StatusChip`'s six shapes, weight contrast (`n-12` vs `n-8`) in the new `ShareBar`.

---

## 1. The P0 defect you did not report

`TableShell` was `overflow-hidden` wrapped around a bare `w-full` table with **no horizontal scroller**. Cells hold `whitespace-nowrap` chips that cannot shrink, so below ~1100px the rightmost columns were **silently clipped** — no scrollbar, no affordance, no error. On `/callbacks` (8 columns) Status and the action buttons vanished entirely on a tablet.

Fixed with a scroll region inside the rounded border plus an edge-fade mask that marks only the *live* edge. Verified in-browser:

| `data-overflow` | Mask applied |
|---|---|
| `none` (table fits) | `none` — no fade at all |
| `start` (scrolled left) | fades right edge only |
| `end` (scrolled right) | fades left edge only |
| `true` (mid-scroll) | fades both |

Toolbar and pager sit **outside** the scroller, so filters and pagination never scroll away from the columns they control. One component fix, ten pages repaired.

---

## 2. Page height: measured before and after

Row height is `Td h-[52px]`. "After" assumes a 900px viewport.

| Page | Before (worst case) | After | Change |
|---|---|---|---|
| `/callbacks` | 500 rows ≈ **26 000 px** (~29 screens) | ~1.4 screens | the `100/250/500` selector is gone |
| `/tickets` | 200 rows ≈ 10 600 px | ~1.4 screens | server-paginated |
| `/notifications` | 200 rows ≈ 10 500 px | ~1.4 screens | server-paginated |
| `/audit` | **unbounded** (`Load older` appended forever) | ~1.4 screens | cursor pager, one page rendered |
| `/decisions` | every row, no limit at all | ~1.4 screens | client pager |
| `/reference` | every catalog row (thousands) | ~1.4 screens | client pager |
| `/knowledge` | every indexed document | ~1.4 screens | client pager |
| `/advisors` | every advisor | ~1.4 screens | client pager |
| `/calls` | `max-h-[720px]` nested scroller | paged, one scrollbar | scroll trap removed |
| `/escalations` | `max-h-[640px]` nested scroller | paged, one scrollbar | scroll trap removed |

Both nested scrollers are gone — you had two of the exact thing you warned against.

### The audit ledger, specifically
Cursor pagination has no total, so `CursorPager` numbers only the pages already fetched and lets Next reach one further. Fetched pages **accumulate in the react-query cache** (stepping back is instant, zero refetch) but **only one page is ever rendered**. A test now asserts exactly this: two requests, back-paging costs nothing.

---

## 3. Overview

It was 15 stat cards and 3 lists in 5 flat sections, with **zero graphics**. `HeroStat` already accepted a `series` prop that draws a sparkline — Overview passed it on none of its cards. Nothing was deleted; it was never wired in.

Now five labelled bands:

1. **Support performance** — one `HeroStat` (`t-metric-xl`, with the session sparkline) leading three `StatCard`s. The reference images' exact composition: one dominant, three supporting.
2. **Volume & policy** — the restored `LineChart` with area wash, hover guide and a fixed readout row, beside the verdict mix.
3. **On the floor** — advisor roster and service catalog, both paged at 5 so the two cards match height.
4. **Runtime** — service health.
5. **Platform totals** — the four orphan cards, now explicitly a separate question.

**The chart costs no extra request.** It reads `analyticsKeys.trend(days)` — the identical key `/analytics` uses — so moving between the two screens is a cache hit on a byte-identical response.

**Verdict mix demoted** from three equal cards to one `ShareBar`. It is one metric split three ways; three cards implied three independent metrics and took three times the furniture.

**Honesty preserved.** The `no comparison exists, so no deltas` comment still holds — those KPIs are all-time with no prior period on the wire, so no card fabricates a delta.

---

## 4. Policies

The real cause of "overlapping text": three of six columns were unbounded variable-height stacks (free-text description with no `max-w`, an unbounded threshold list, a comma-joined env-var list). A `<table>` distributes width by content pressure, so the description stole the width, threshold pairs wrapped mid-pair, and rows ranged 52px→200px against a grid built for 52px.

Replaced with a domain-grouped accordion:

- **Collapsed** — one scannable line: id · domain · thresholds count · enforcement · version · status. The whole registry fits on one screen.
- **Expanded** — description at `t-body` (14/22, a real reading line-height) capped at **72ch**; thresholds as a two-column definition grid so a long label can never push its value onto the next line; env vars as mono tokens with a sentence explaining they are what you actually change.

Height animates via framer-motion's `height: auto` — the one thing CSS cannot do without a hard-coded `max-height` that then clips long content.

---

## 5. Sidebar

- **Brand** — `<BrandMark />` + `BRAND.shortName`; every route `<title>` now derives from `pageTitle()`. Confirmed live: the tab reads **"Sign in — Admin Console"**.
- **Live badges** — Escalations, Tickets, Callbacks. Queues waiting on a human (escalations, callbacks) invert to `n-12`; Tickets is a quiet surface chip. Counts animate on change via `CountSwap`.
- **`null` ≠ `0`.** A count we could not fetch renders **no badge**; zero renders a badge. An absent badge admits ignorance, a zero badge makes a claim. `Promise.allSettled` means a dead callback service still leaves the tickets badge working, and a `conseiller` gets no 403 in the nav rail.
- **The 2px active rail now renders.** `.nav-item[data-active="true"]::before` was defined in the bible as one of only two 2px strokes in the product — and **no element in the codebase carried the class**. Wired up.
- The shortcut hint (`G O`) only takes the trailing slot when no badge does; the two were competing for the same 40px, which is why counts had nowhere to go.

---

## 6. Motion — what got animated, and what deliberately did not

| Interaction | Treatment |
|---|---|
| Modal open **and close** | Scrim 160ms fade, panel 200ms fade/scale. Previously `if (!open) return null` tore the subtree out — CSS cannot animate what no longer exists, so there was **no exit animation at all**. |
| Page swap | `TableBodySwap` cross-fades `<tbody>` (`mode="wait"` — overlapping tbodies would double the table height and shove the pager down the page). |
| Tabs / Segmented | The 2px rule and the thumb **travel** between options via `layoutId` instead of blinking. |
| Background refetch | 2px indeterminate sweep on the toolbar edge, absolutely positioned so it never shifts a pixel of layout. |
| Section mount | `.rise` staggered 40ms per band, capped at 4. Every section previously fired at once — one synchronised lurch. |
| Skeletons | Directional shimmer, not symmetric pulse. A wipe reads as "arriving"; a fade in-and-out reads as "broken". |
| Buttons | 1px depress on `:active`. |
| **Cards** | Border + elevation only, **no lift**. Twelve cards rising under the pointer is noise, not response. |

**Reduced motion is hardened.** framer-motion's `useReducedMotion` reads `matchMedia`; where that API is missing it returns its initial `false`, indistinguishable from a real "full motion please". `usePrefersReducedMotion` checks the capability **first** and assumes reduced when the question could not be asked. Modal also takes the original synchronous-unmount path under reduced motion — someone who asked the OS for less motion should not inherit its latency.

---

## 7. Regressions I introduced and fixed

Both were caught by the existing suite, and both were fixed at the source rather than by editing tests:

1. **`ResizeObserver` crashed 18 audit tests.** My overflow hook constructed it unguarded; jsdom (and older webviews) do not implement it. Now feature-detected with a `window.resize` fallback — the fade is an enhancement and must never cost the table itself.
2. **Modal exit kept the dialog mounted**, breaking 2 retention-panel assertions. Fixed via the reduced-motion path above.

**Three audit tests I did update**, because they drove the removed "Load older" button. The contracts under test are unchanged (`next_before_seq` → `beforeSeq`, no duplicate rows, disabled without a cursor); they now drive the pager and additionally assert the new "one page rendered, pages cached" behaviour.

---

## 8. New files

| File | Purpose |
|---|---|
| `lib/nexus/brand.ts` | The one place the product is named |
| `lib/nexus/paginate.ts` | Pagination arithmetic — pure, **20 tests** |
| `lib/nexus/paginate.test.ts` | Edge cases that bit the old code: empty sets, stranded pages, partial last page, stable token width |
| `lib/nexus/motion-tokens.ts` | Curves, durations, motion hooks |
| `lib/api/nav-counts.server.ts` | Sidebar counts, fail-soft |
| `components/nexus/brand-mark.tsx` | The geometric mark |
| `components/nexus/pager.tsx` | `Pager` + `CursorPager` |
| `components/nexus/count-strip.tsx` | Replaces 3 divergent hand-rolled counter rows |
| `components/nexus/motion.tsx` | `PageSwap`, `TableBodySwap`, `Reveal`, `CountSwap` |
| `hooks/use-adaptive-page-size.ts` | Viewport-derived page size, SSR-safe |
| `hooks/use-overflow-x.ts` | Drives the edge-fade |

36 files modified, 11 added. +3347 / −1755.

---

## 9. What I did NOT verify, and why

**The authenticated screens were not visually confirmed.** The dev server runs and business-api answers `/health` with 200, but reaching any dashboard page requires signing in — and entering a password into a form is something I won't do. The login screen renders clean (correct brand, zero console errors), and typecheck/lint/tests/build all pass, but **you should click through the pages yourself**.

```bash
npm --prefix Frontend/admin_dashboard run dev
```

Worth looking at specifically:

1. `/overview` — the restored curve, band structure, and that switching 7d/30d dissolves rather than blanking.
2. `/policies` — expand a rule; check the 72ch measure and the threshold grid.
3. `/callbacks` and `/tickets` — page height, and the pager's numbered jumps.
4. **Resize a table page below ~1100px** — this is the P0 fix; columns should scroll with a fade, not disappear.
5. The sidebar badges — confirm the counts match what the pages show.

**Two other honest notes:**

- Three test files (`agent-view.test.ts`, `agents.test.tsx`, `agent-activity-sparkline.test.tsx`) show as modified. That is **prettier re-wrapping only** — they had never been run through the repo's prettier config. No logic touched. Revert them if you'd rather keep the diff tight.
- `recharts` (498 kB) is still bundled but unused by any `nexus` component — only the vendored `components/ui/chart.tsx` imports it, and nothing imports that. Dropping it is a real bundle win, but it is outside this brief so I left it.
