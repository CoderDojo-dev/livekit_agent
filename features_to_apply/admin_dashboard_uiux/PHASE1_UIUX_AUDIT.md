# Phase 1 — Deep UI/UX Audit
## Nexus Admin Console (`Frontend/admin_dashboard`)

**Date:** 2026-08-20
**Scope:** presentation layer only. No backend, API, business-logic, auth, state-management or data-fetching changes.
**Method:** full read of `src/styles.css`, `src/components/nexus/*`, `src/components/audit/*`, `src/components/escalations/*`, all 21 route files, `src/lib/nexus/nav.ts`, `package.json`.

---

## 0. Two corrections before anything else

### 0.1 The target app

The brief says "Customer Portal". Every page it names — Policies, Knowledge Base, Calls & Transcripts,
Escalations, Notifications, Audit Ledger in Settings, the PLATFORM/KNOWLEDGE/OPERATIONS/INSIGHTS sidebar —
lives in **`Frontend/admin_dashboard`**. `Frontend/customer_portal` is a separate end-user app with a
different shell (`portal-rail`, `portal-tabbar`, `orb`) and none of those routes.

**This audit covers `Frontend/admin_dashboard`.** Say the word if you actually meant the other app.

The branding string is **"Nexus"**, not "Nexor" — `app-sidebar.tsx:44`, plus `<title>` in every route
`head()` and in `__root.tsx`.

### 0.2 The reference images vs. the design bible

`src/styles.css:5-8` states the product law:

> NEXUS ADMIN CONSOLE — MONOCHROME DESIGN BIBLE v1.0
> Achromatic by law: every hex satisfies RR === GG === BB.
> No colour. No perfect circles. No arbitrary values.

The three reference screenshots use colour semantically (red = down, green = up, purple = neutral) and
two of them are light-mode. Reproducing that literally would **replace** the identity, which the brief
forbids in the same breath as it asks for the references.

**Resolution rule applied throughout this audit:** take the references' *information structure* —
metric dominance, quiet secondary line, compact trend glyph, consistent card box, four-across analytical
row — and express trend/state in **form**, not hue. The system already has this vocabulary and it is
badly under-used:

| Reference does it with | Nexus already has |
|---|---|
| green/red % chip | `Delta` — arrow glyph + dotted underline for "bad" (`primitives.tsx:296`) |
| coloured status pill | `StatusChip` — six distinct *shapes* (disc/ring/half/triangle/square/bar), `primitives.tsx:112` |
| coloured bar heights | `PriorityMeter` — 3 tone-ramped bars (`primitives.tsx:203`) |
| coloured sparkline | `Sparkline` / `SeriesChart` — `n-12` stroke, `n-8` dashed comparison (`blocks.tsx:74`) |

No new colour token is proposed anywhere in this audit.

---

## 1. What already works (do not touch)

Being explicit about this, because several "problems" in the brief are already solved and would be
regressions if I "fixed" them.

1. **The token system is genuinely good.** 13 greys, 6 surfaces, 5 inks, 4 strokes, a 12-step spacing
   scale, 6 radii, 18 named type tokens, 5 elevations, 2 easing curves. Everything below reuses it;
   I propose **zero new tokens**.
2. **`prefers-reduced-motion` is already handled globally** (`styles.css:366`). Any animation I add
   inherits the guard for free.
3. **Loading and error states already exist and are structurally correct** — `TableSkeleton`,
   `CardSkeleton`, `ErrorState`, `TableErrorRow`, `InlineError` (`states.tsx`). `ErrorState` is a
   deliberate structural twin of `EmptyState`. This is better than most production dashboards.
4. **`/customers` already has correct offset pagination** with `keepPreviousData`, disabled
   Prev/Next, and an honest `Showing 1–25 of 812` footer (`customers.tsx:141-170`). **This is the
   house pattern.** The fix for every other heavy page is to generalise *this*, not invent something new.
5. **The truthfulness discipline is deliberate.** Comments like `F9: not StatCard — no delta exists`
   and `D18.5 — "Logged", not "Sent"` mean labels were argued over. I will not "improve" a label into
   a lie to make a card look fuller.
6. **`Modal` focus management is correct** — focus capture, restore, Escape, body scroll lock, portal
   with a documented reason (`modal.tsx:59-61`). Only its motion is missing.

---

## 2. Priority legend

| | Meaning |
|---|---|
| **P0** | Breaks usability, readability or hierarchy. Ships first. |
| **P1** | Major visual/UX gap. The pages the brief names by name. |
| **P2** | Consistency and polish across the system. |
| **P3** | Micro-detail. The difference between "works" and "finished". |

Complexity: **S** ≈ under an hour · **M** ≈ half a day · **L** ≈ a day or more.

---

# P0 — Critical

## P0-1 · Tables are clipped on every viewport under ~1100px

**Component:** `TableShell` — `primitives.tsx:349`
**Used by:** `/tickets` (6 col), `/notifications` (5), `/knowledge` (7), `/policies` (6),
`/decisions` (6), `/callbacks` (8), `/advisors` (8), `/customers` (5), `/reference` (5), `/audit` (5).

**Current problem.** The shell is `overflow-hidden rounded-r-4 …` wrapping a bare
`<table className="w-full">`. There is **no horizontal scroll container**. Cells contain
`whitespace-nowrap` children (`StatusChip`, `Token`, `Segmented`). Below roughly 1100px those cells
cannot shrink, the table exceeds its box, and `overflow-hidden` **silently cuts the rightmost columns
off**. On `/callbacks` (8 columns) the Status and action columns disappear entirely on a tablet.

**Why it hurts.** Data loss with no affordance. The user cannot scroll to it, cannot know it is there,
and has no error to report. This is the single worst defect in the app.

**Fix.** Add an `overflow-x-auto` scroll region *inside* the rounded border, with a `min-w` on the
table so columns keep their intended widths, and edge-fade masks so the cut reads as "scrollable".
Toolbar and footer stay outside the scroller so filters and pagination never scroll away.

**Expected result.** Nothing changes at desktop width. Below it, the table scrolls horizontally with a
soft fade at the live edge; toolbar and pager stay pinned.

**Complexity:** S — one component, ~10 lines. Fixes 10 pages at once.

---

## P0-2 · Heavy pages render 50–500 rows at once and become 3–26k px tall

Measured initial and worst-case page heights (row height is `Td h-[52px]`, `primitives.tsx:406`):

| Page | Source | Initial rows | Ceiling | Worst-case height | Pattern |
|---|---|---|---|---|---|
| `/callbacks` | `callbacks.tsx:51,120` | **100** | **500** (Segmented `100/250/500`) | **~26 000 px** | none |
| `/tickets` | `tickets.tsx:66,169` | 50 | 200 (`+50` × 3) | ~10 600 px | Load more |
| `/notifications` | `notifications.tsx:60,154` | 50 | 200 | ~10 500 px | Load more |
| `/audit` | `audit-page.tsx:139,182` | 50 | **unbounded** (`useInfiniteQuery`) | unbounded | Load older |
| `/decisions` | `decisions.tsx:63` | whatever the server returns | — | rows are ~75px (stacked `Token`) | **none at all** |
| `/calls` | `calls.tsx:67,143` | 50 | 200 | contained by `max-h-[720px]` | nested scroller |
| `/escalations` | `escalations-page.tsx:130` | all | — | contained by `max-h-[640px]` | nested scroller |

`/callbacks` is the worst offender and the brief does not even name it: 500 rows × 52px ≈ 26 000 px,
about **29 screens** at a 900px viewport, with the limit selector sitting in the toolbar inviting it.

**Why it hurts.** Scroll position stops meaning anything — there is no sense of "where am I in the set".
`Load more` grows the DOM monotonically with no way back. And it is dishonest ergonomics: the footer
says `Showing 50 of 1,284` while the only affordance moves you 50 rows closer to 1,284, one click at a time.

**Fix.** Generalise the `/customers` pattern into a shared `Pager` presentation component and apply it
to all six list pages, with a **page size of 6** for the record-style tables the brief calls out
(tickets, notifications, audit, callbacks, decisions) — matching the brief's 5–6 guideline.
Numbered pages `1 2 3 … n` with ellipsis, Prev/Next, and an honest `Showing 13–18 of 1,284`.
Page state is local `useState` only — **no query-function or query-key changes** where the data is
already in memory. Where the server is already offset-paginated (`/customers`, `/tickets`,
`/notifications`, `/callbacks`) the existing `offset` argument is reused exactly as `/customers`
reuses it today.

**Expected result.** Every heavy page settles at roughly **one and a half screens**, regardless of
dataset size. The page footer becomes the navigation instrument.

**Complexity:** M — one new presentational component plus six small route edits.

---

## P0-3 · Nested scroll traps on `/calls` and `/escalations`

**Components:** `calls.tsx:143` (`max-h-[720px] overflow-y-auto`), `escalations-page.tsx:130` (`max-h-[640px]`)

**Current problem.** A tall inner scroller sits inside the normal page scroll. There is no fade, no
shadow and no count boundary telling the user the inner region scrolls. A mouse wheel over the list
scrolls the list; two pixels to the right it scrolls the page. On trackpads this reads as broken.

**Why it hurts.** Scroll hijacking is the classic "this dashboard feels cheap" tell — and it is exactly
why the brief says *"Do not solve everything by adding a giant scroll container."* Two already exist.

**Fix.** Replace both with the P0-2 `Pager` at 6 rows per page. The master column then has a fixed,
predictable height and the page has exactly one scrollbar.

**Expected result.** One scroll axis per page. The master/detail split stops fighting the mouse.

**Complexity:** S once P0-2 exists.

---

## P0-4 · `/policies` puts prose and multi-value definitions inside a 6-column table

**Component:** `policies.tsx:106-172`

**Current problem.** The `Policy` cell stacks `rule_id` (mono) **plus a free-text `description`** with
no `max-w`. The `Thresholds` cell stacks an *unbounded* list of `label + Token` pairs vertically
(`definitionEntries`). The `Enforcement` cell stacks a `Token` plus a comma-joined list of env-var
names. Three of six columns are variable-height stacks. Since a `<table>` distributes width by content
pressure, the long description column steals width, the threshold Tokens wrap mid-pair, and rows land
anywhere from 52px to 200px tall. What the brief calls "overlapping text" is precisely this: cells of
wildly different heights sharing a baseline grid built for 52px rows, inside a container that also
clips (P0-1).

**Why it hurts.** Policies is a *reading* surface — governance records a human must comprehend — and it
is rendered in the densest possible container. There is no way to scan the rule set before reading it.

**Fix.** Replace the table with an **accordion of policy cards grouped by domain**. Collapsed row =
`rule_id` · domain · `Version` token · `StatusChip` · enforced/catalog token — one line, fully scannable.
Expanded = description at `t-body` (22px line-height, `max-w-[72ch]`), thresholds as a definition
grid, governed-by env vars as mono tokens. Uses `@radix-ui/react-collapsible`, already a dependency and
already vendored at `components/ui/collapsible.tsx`.

**Expected result.** The whole policy set fits on one screen collapsed. Reading one policy is a
comfortable measure at a comfortable line-height. Same treatment available for `/reference` if its
prose columns grow.

**Complexity:** M.

---

## P0-5 · `/overview` has no visualisation at all

**Component:** `overview.tsx`

**Current problem.** The page is **15 stat cards and 3 lists stacked in 5 flat `PageSection`s**, and
not one of them draws anything:

- rows 1–2: 4 KPI cards, **zero deltas** (`overview.tsx:58` — all-time data, honest) and **zero series**
- row 3: 3 verdict cards, identical treatment, so the eye cannot rank them against row 1
- row 4: two list cards plus the service-health panel
- row 5: 4 more stat cards with the same `StatCard` treatment as rows 1–3

`HeroStat` accepts an optional `series` prop that renders a `Sparkline` (`blocks.tsx:26`). **Overview
passes it on none of its cards.** `/analytics` is the only page in the app that passes it. So the
sparkline primitive exists, is tested, and is unused on the one page that most needs it — this is
exactly the "you deleted the beautiful curves" complaint, except the primitive was never deleted, just
never wired in.

**Why it hurts.** Twelve near-identical cards is not a hierarchy; it is a list with borders. There is
no answer to "what should I look at first". And this page opens the product.

**Fix.**
1. **Restore visualisation.** Feed `HeroStat.series` from the daily trend the app *already fetches*
   for `/analytics` (`analyticsKeys.trend`) — same query key, so it is a **shared cache hit, not a new
   request**. Add one full-width `LineChart` "Volume trend" card, the same component `/analytics`
   uses, so Overview finally has a curve.
2. **Rank the rows.** Row 1 becomes one `HeroStat` at `t-metric-xl` plus 3 `StatCard` at `t-metric-l` —
   the reference images' exact composition (one dominant, three supporting).
3. **Demote the verdict mix** from three full cards to one segmented bar inside a single card. It is a
   3-way share of 100 items; three cards is three times the furniture it deserves.
4. **Group into two labelled bands** — "Support performance" and "Platform totals" — with `t-micro`
   section eyebrows, so the 4 orphan cards in row 5 stop reading as an afterthought.
5. **Add icons** (P1-2).

**Expected result.** An analytical page with a clear first read, a curve, and half the card count for
the same information.

**Complexity:** L — the largest single patch.

---

# P1 — High

## P1-1 · Branding is hard-coded inline and not swappable

**Component:** `app-sidebar.tsx:33-46`, plus `app-topbar.tsx:94`, `__root.tsx` head, 18 route `head()` blocks.

**Current problem.** The mark is a raw inline `<svg>` and the wordmark is a bare `"Nexus"` string inside
the sidebar's JSX. The name is *also* duplicated as a literal in ~20 `<title>` / `og:title` strings.
Renaming the product today means a 20-file find-and-replace.

**Why it hurts.** The brief asks for a placeholder identity that is "easy to replace later". Right now
it is the opposite.

**Fix.** One `src/lib/nexus/brand.ts` exporting `{ name, shortName, version }`, plus a `<BrandMark />`
component holding the SVG. Sidebar and topbar consume it. Route titles become
`` `Overview — ${BRAND.name}` ``. Swapping the product name becomes a **one-line edit**.
Neutral placeholder proposed: **"Console"**, with a geometric mark drawn from the existing
`M3 13V3l10 10V3` idiom — no rounded shapes, per the bible's "no perfect circles" rule.

**Expected result.** Identical pixels today; a one-line rename tomorrow.

**Complexity:** S.

---

## P1-2 · Stat cards have no icons; card headers have no icons

**Components:** `HeroStat` / `StatCard` (`blocks.tsx:5,29`), `CardHeader` (`primitives.tsx:31`)

**Current problem.** None of them accepts an icon. Across all 21 routes, `lucide-react` is imported
**once per file and only for the `EmptyState` icon** — verified by grep. So icons appear in the sidebar
and in empty states, and **nowhere else**. On Overview that means 15 cards distinguished only by an
11px uppercase label.

**Why it hurts.** Metric recognition at a glance is precisely what an icon buys on a KPI card, and it is
the most visible thing the reference images do that this app does not.

**Fix.** Add an optional `icon` prop to `HeroStat`, `StatCard` and `CardHeader`, rendered in the
bordered frame `EmptyState` already uses (`primitives.tsx:334`) at `size-[28px] rounded-r-2`,
`size={14} strokeWidth={1.5}`, `text-ink-4`. One icon family (lucide), one weight, one size.
**Only where the icon names the metric** — not on generic containers.

**Expected result.** KPI rows become scannable by shape. No new visual language: the frame, radius,
stroke and ink already exist.

**Complexity:** S (component) plus S (per-page icon assignment).

---

## P1-3 · Every `PageSection` animates identically, at the same instant

**Component:** `PageSection` (`app-topbar.tsx:114`), `.rise` (`styles.css:352`)

**Current problem.** `.rise` is `nexus-rise 240ms both` — a fine 8px fade-up. But it is applied to
*every* section with *zero* delay, so a 5-section page performs one synchronised 240ms lurch. It also
re-runs on every mount, including a filter change that remounts a section.

**Why it hurts.** Simultaneous motion reads as a glitch; staggered motion reads as composition. This is
free polish that is 90% built.

**Fix.** An optional `index` prop setting `animation-delay: index * 40ms` (capped around 4). One CSS
custom property, no new keyframes. `prefers-reduced-motion` already neutralises it.

**Expected result.** Pages assemble top-down over ~360ms instead of blinking into place.

**Complexity:** S.

---

## P1-4 · `Modal` opens and closes with no transition

**Component:** `modal.tsx:59-101`

**Current problem.** The panel carries `.rise` so it fades **in**. On close, `if (!open) return null` —
the whole portal is torn down synchronously. **There is no exit animation at all**, for the panel or the
backdrop, and the backdrop has no entrance animation either. Used by `/settings` (revoke confirmation),
`/customers` (detail), `/decisions` (detail), `/advisors`, and `/callbacks` ×3.

**Why it hurts.** The brief singles this out: *"Close — equally smooth exit animation."* An instant
disappearance loses the spatial thread back to the row you came from.

**Fix.** Local `closing` state driven by `animationend`; the scrim gets its own 160ms fade, the panel a
200ms scale/fade on the existing `--ease-out`. Every existing focus / Escape / scroll-lock behaviour is
preserved byte-for-byte.

**Expected result.** Modals arrive and leave. Nothing about focus or keyboard changes.

**Complexity:** S.

---

## P1-5 · No visual feedback during a background refetch or a page change

**Components:** all list routes; `Segmented` / `Tabs` / `SearchInput` handlers

**Current problem.** Three distinct react-query states collapse into two treatments:

| State | Today |
|---|---|
| `isPending` (first load) | full skeleton — correct |
| `isFetching` after a filter change | **nothing** — stale rows sit there looking current |
| `keepPreviousData` page change | **nothing** — and only `/customers` and `/analytics` even use it |

`/customers` disables Prev/Next during `isPending` but shows no progress. `/analytics` swaps chart data
with no transition at all.

**Why it hurts.** Clicking "Escalated" and seeing the same rows for 400ms reads as a dead control.

**Fix.** A 2px `TopProgress` bar keyed off `isFetching`, hosted on `TableShell`'s toolbar bottom edge
(so it never shifts layout), animating an indeterminate sweep at ~1.1s. Plus `opacity-60` and
`pointer-events-none` on the tbody while a page swap is in flight. This is the brief's
*"smooth loading progress bar animations when fetching or displaying the next data cell."*

**Expected result.** Every filter and page change acknowledges the click within one frame.

**Complexity:** S (component) plus S (wiring).

---

## P1-6 · The documented active-nav indicator is dead CSS

**Component:** `styles.css:325` — `.nav-item[data-active="true"]::before` vs `app-sidebar.tsx:71-82`

**Current problem.** The stylesheet defines a 2px white left rail as one of only two 2px strokes in the
entire product. **No element in the codebase carries `class="nav-item"`** — verified by grep. The
sidebar signals active state with `bg-surface-3` alone, which at `#1a1a1a` against `#101010` is a very
quiet 4-value step.

**Why it hurts.** The reference sidebar's whole point is an unmistakable active state. Here it is
nearly invisible — and the fix is already written, merely unwired.

**Fix.** Wire the class and `data-active` onto the nav `Link`, add `relative`, keep the existing
`bg-surface-3`. Add a 160ms colour transition on hover (currently `transition-colors` with no duration,
so it inherits Tailwind's default rather than the house 120ms).

**Expected result.** The bible's own indicator finally renders.

**Complexity:** S.

---

## P1-7 · The sidebar has no counts; 17 items across 4 sections with no density relief

**Component:** `app-sidebar.tsx`, `nav.ts:36`

**Current problem.** The reference sidebar carries compact counters (`Conversations 4`, `Tickets 42`,
`Callbacks 7`) — the brief lists them as a pattern to keep coherent. Nexus has **no badges anywhere**.
Meanwhile the shortcut hint (`G O`, `G T`) occupies the right slot on hover, so the affordance the
reference spends on counts is spent here on a keyboard hint — and there is **no keyboard handler bound
to those shortcuts anywhere in the app**, so the hints are purely decorative.

**Why it hurts.** "How many escalations are open right now" is the first question an operator asks, and
they must visit three pages to answer it.

**Fix — with a caveat.** A `Badge` slot on the nav item is trivial. **Feeding it is not a presentation
change** — it needs open-escalation / pending-callback counts in the sidebar's render path, which is
data fetching and therefore **out of scope under the constraints you set**. I will:

- build the presentational `NavBadge` and its slot;
- render it only where a count is *already* in the react-query cache for that session
  (`callbackKeys.stats()` and `escalationKeys.list("open")` are both fetched by their own pages),
  read through a cache-only selector with **no new request**;
- leave it absent otherwise, rather than invent a number.

If you want live counts on first paint, that is a deliberate data change and I will raise it as a
separate decision rather than smuggle it into a UI patch.

**Complexity:** M, partially blocked by scope. Flagged, not assumed.

---

# P2 — Medium

## P2-1 · `Delta` is defined but appears on exactly one page
`Delta` — `primitives.tsx:296`. Only `/analytics` passes `delta` (4 cards). Overview's comment
`no comparison exists, so no deltas` is **correct and must stay** — that data is all-time. But
`/agents`, `/knowledge` and `/customers` render `StatCard`s where a windowed comparison *is* on the wire
and simply is not shown. Audit each; render where honest, leave alone where not. **S**

## P2-2 · Three different "counts row" implementations exist
`/tickets:96` (`grid-cols-5` of button-wrapped `t-metric-m`), `/notifications:92` (`grid-cols-3`, the
same idiom copy-pasted), `/knowledge:127` (`HealthValue`, a private near-duplicate). Three hand-rolled
variants of one pattern, with drifting grid columns and no shared hover or active state. Extract one
`CountStrip` — a real segmented filter with `aria-pressed`, hover, and a 2px active underline matching
`Tabs`. **M**

## P2-3 · `Segmented` used as a page-size selector on `/callbacks`
`callbacks.tsx:117-121` renders `100 / 250 / 500` in a `Segmented`, which everywhere else in the app
means "filter scope". Semantic collision, and it is what invites the 26 000px page in P0-2. Removed by
the `Pager` patch. **S**

## P2-4 · Hover states on rows that are not clickable
`/customers:180` and `/decisions:196` give rows `role="button"`, `tabIndex={0}` and a focus ring;
`/calls` and `/escalations` use real `<button>`s. But `/tickets`, `/notifications` and `/knowledge` rows
carry `hover:bg-surface-3` on a **non-interactive** row — promising a click that does nothing. Either
make them open a detail, or drop the hover. **S**

## P2-5 · `CardHeader` subtitle is capped at `max-w-[48ch]` but the card is not
`primitives.tsx:43`. On a full-width card at 1440px the title spans ~1200px while the subtitle stops at
~430px, leaving a large asymmetric void — visible on `/policies`, `/knowledge` and `/audit`. Constrain
the header block, not just the subtitle. **S**

## P2-6 · `/decisions` renders an unbounded list with no pagination whatsoever
`decisions.tsx:63` calls `listDecisions` and maps every row, with the footer reading
`Showing the most recent N decisions` — where N is whatever arrived. Rows are ~75px tall (stacked
`Token` in two cells). Covered by P0-2's `Pager`; called out separately because it is the only heavy
page with **no** limiting affordance at all. **S** once `Pager` exists.

## P2-7 · Grain overlay sits at `z-index: 9999`, above the modal layer (`z-50`)
`styles.css:187`. It is `pointer-events: none`, so nothing breaks, but the `mix-blend-mode: overlay`
grain lands on top of dialog content and very slightly muddies text in modals. Drop it to `z-40`, or
exclude it over `[role="dialog"]`. **S**

## P2-8 · Table row height is fixed at 52px regardless of content
`Td h-[52px]` (`primitives.tsx:406`) is a *minimum* in practice — cells that stack (policies
thresholds, decisions tokens, notifications failure reason) blow past it, so the consistent row rhythm
the fixed height is meant to guarantee does not hold on 4 of 10 tables. Introduce an explicit `density`
prop on `TableShell` (`comfortable` / `compact`) and use `align-top` plus `py` instead of a fixed height
on stacking tables. **M**

---

# P3 — Fine Polish

- **P3-1** `Button` / `IconButton` transition only `colors`. Add `transform` and `shadow` on the same
  120ms — a 1px lift on `:active` costs nothing and is the highest-value micro-interaction available. **S**
- **P3-2** Sidebar nav `transition-colors` has no duration, so it uses Tailwind's 150ms default while
  the rest of the app is on the house 120ms. Two-character fix, system-wide consistency. **S**
- **P3-3** `Sparkline` (`primitives.tsx:597`) divides by `values.length - 1` — a single-point series
  yields `Infinity` and an invalid `points` attribute. `LineChart` and `SeriesChart` both guard this;
  `Sparkline` does not. It starts mattering the moment Overview feeds it (P0-5). **S**
- **P3-4** `Avatar` has 5 sizes; only `sm`, `md` and `xl` are used. `PresenceDot` appears only on the
  sidebar and Overview. Nothing to fix — noted so nobody "cleans up" a used API. **—**
- **P3-5** `SeriesChart` lifts hover to the caller and stays stateless (a good decision,
  `blocks.tsx:145`). `LineChart` has **no** hover readout, so `/analytics`' primary chart is less
  interactive than its secondary one. Port the hit-cell + readout idiom across. **M**
- **P3-6** `EmptyState` and `ErrorState` are structural twins, but `EmptyState` has no action slot.
  Several empty states are actionable ("Register an advisor…") yet offer no button. Add an optional
  `action`. **S**
- **P3-7** The focus ring is `outline: 2px solid var(--n-12)` with `border-radius: inherit` — correct —
  but `:focus { outline: none }` on line 199 kills it for programmatic focus on the modal panel (which
  sets `tabIndex={-1}` and calls `.focus()`). Low impact, easy to make right. **S**
- **P3-8** The scrollbar is styled for WebKit only. Add `scrollbar-color` / `scrollbar-width` so Firefox
  matches. **S**
- **P3-9** No `aria-live` region for route transitions, so screen readers get no announcement when the
  page changes. **S**

---

# 3. Proposed Phase 2 patch grouping

Ordered so each patch lands on a green build and none depends on a later one.

| # | Patch | Contains | Priority | Complexity |
|---|---|---|---|---|
| **1** | **Table containment & responsive rescue** | P0-1, P2-5, P2-8 | P0 | S–M |
| **2** | **Pagination & data distribution** | P0-2, P0-3, P2-3, P2-6 — new `Pager`, applied to 6 pages | P0 | M |
| **3** | **Loading, progress & transition feedback** | P1-5, P1-3, P1-4 | P0/P1 | S–M |
| **4** | **Policies & heavy-text architecture** | P0-4 (accordion), spill-over to `/reference` | P0 | M |
| **5** | **Overview & analytics composition** | P0-5 — restore curves, rank rows, band the page | P0 | L |
| **6** | **Iconography** | P1-2 — icon slots plus per-page assignment | P1 | S |
| **7** | **Navigation & branding** | P1-1, P1-6, P1-7 (scoped) | P1 | S–M |
| **8** | **Consistency sweep** | P2-1, P2-2, P2-4, P2-7 | P2 | M |
| **9** | **Micro-interactions & final polish** | all P3 | P3 | S |

---

# 4. Explicit non-goals

I will **not**:

1. Add colour. The bible forbids it and the brief forbids replacing the identity.
2. Install `framer-motion`. It is **not** in `package.json` — adding it is a dependency and bundle
   change, not a view change. Everything in this audit is achievable in CSS on the two easing curves
   already defined (`--ease-out`, `--ease-in-out`), and CSS inherits the existing
   `prefers-reduced-motion` guard for free. Say the word if you want the dependency anyway.
3. Introduce new design tokens. Zero are needed.
4. Change query functions, query keys, server functions, or anything under `src/lib/api/`.
5. Reproduce the reference screenshots' numbers. Real data only, per the brief.
6. "Fill" a card with a metric that is not honestly available — the `no delta exists` comments stay.
7. Touch `Frontend/customer_portal`.

---

# 5. Open questions

1. **Placeholder brand name** — I will use **"Console"** unless you name one.
2. **Page size** — the brief says 5–6. I propose **6** for record tables, **8** for `/customers` and
   `/advisors` (denser single-line rows, no stacking). Confirm or override.
3. **Sidebar counts (P1-7)** — cache-only badges as described, or real fetches (a data change I would
   need explicit sign-off for)?
4. **`framer-motion`** — CSS-only as proposed, or install it?

None of these block Phase 2. Absent an answer I will assume the defaults above and flag each one inline
in the cookbook.
