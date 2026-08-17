# COOKBOOK 4 — UX / DATA LAYOUT REVAMP

**Backend touched:** none. **New dependencies:** none — `motion ^12.43.0` and `lucide-react` are already in `package.json` (verified), and `styles.css` already ships every token, the `.skeleton` shimmer, and the unused `caret` keyframe.
**Mandate:** enhance the identity, never replace it. No new colour, no hex, no font-size literal, no radius above `--r-5` (12 px), no shadow that is not `--elev-0…4`, no hue on the orb.

---

## 4.0 The five rules the current screens break

| Rule | Current failure | Fix |
|---|---|---|
| One vertical rhythm per page | screens mix `space-y-sp-8`, `gap-sp-6`, ad-hoc `mt-sp-3` | one `PageSection` wrapper; sections are `--sp-9` apart, content inside is `--sp-6` |
| A list never grows without bound | `copy.activity.loadMore` = endless append | `Pagination` with bottom page indicators; server already returns `total/limit/offset` (Cookbook 3) |
| A loading state keeps the page’s shape | no skeletons anywhere; `.skeleton` class unused | `Skeleton*` primitives sized to the real row |
| Feedback under 400 ms, always interruptible | `transition-colors duration-200` only; no press feedback, no elevation | `--d-2`/`--d-3` + `--ease-out`; `active:scale-[0.99]`; hover elevation on interactive cards |
| Empty is designed, not blank | `EmptyState` exists but only `/activity` uses it | every list has empty **and** error states |

---

## 4.1 New primitives — `src/components/portal/data.tsx`

A **new** file, not an edit to `primitives.tsx` (which stays as the chapter-authored design system, with the single `Meter` fix from Cookbook 1).

```tsx
import { type ReactNode, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button, Card, EmptyState, SectionLabel } from "@/components/portal/primitives";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/* --------------------------------------------------------------------------
 * Motion constants.
 * Mirrors apps/client-widget/src/lib/motion.ts in spirit, but the numbers are
 * the portal's own tokens: --d-2 = 120ms, --d-3 = 160ms, --d-4 = 220ms,
 * --ease-out = cubic-bezier(.22,1,.36,1).
 * -------------------------------------------------------------------------- */
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;
export const T_MICRO = { duration: 0.12, ease: EASE_OUT } as const;
export const T_BASE = { duration: 0.22, ease: EASE_OUT } as const;
export const T_PANEL = { duration: 0.28, ease: EASE_OUT } as const;

/* --------------------------------------------------------------------------
 * PageSection — the only vertical rhythm in the portal.
 * .portal-section is the hook the compact-density CSS rule uses.
 * -------------------------------------------------------------------------- */
export function PageSection({
  label,
  right,
  children,
  className,
}: {
  label?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("portal-section", className)}>
      {label ? <SectionLabel right={right}>{label}</SectionLabel> : null}
      <div className={cn(label && "mt-sp-6")}>{children}</div>
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Skeletons — .skeleton already animates (shimmer, 1400ms) in styles.css.
 * Sizes are chosen to match the real rows so nothing reflows on arrival.
 * -------------------------------------------------------------------------- */
export function SkeletonLine({ className }: { className?: string }) {
  return <div className={cn("skeleton h-3 rounded-r-1", className)} />;
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-sp-6 py-sp-6">
      <div className="skeleton h-9 w-9 shrink-0 rounded-r-2" />
      <div className="min-w-0 flex-1 space-y-sp-3">
        <SkeletonLine className="w-[42%]" />
        <SkeletonLine className="w-[24%] opacity-70" />
      </div>
      <SkeletonLine className="w-16 shrink-0" />
    </div>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div
      className="divide-y divide-stroke-subtle"
      role="status"
      aria-busy="true"
      aria-label={copy.common.loading}
    >
      {Array.from({ length: rows }, (_, index) => (
        <SkeletonRow key={index} />
      ))}
    </div>
  );
}

export function SkeletonMetric() {
  return (
    <div className="space-y-sp-4" role="status" aria-busy="true">
      <SkeletonLine className="w-20 opacity-70" />
      <div className="skeleton h-8 w-32 rounded-r-2" />
    </div>
  );
}

/* --------------------------------------------------------------------------
 * TopProgress — the "animated progress bar during data transitions".
 * A 2px line pinned under the sticky topbar (h-16). Indeterminate: it never
 * claims a percentage it cannot know. Uses --z-callbar's neighbourhood but
 * stays under it (z-30 < 40) so an active call bar always wins.
 * -------------------------------------------------------------------------- */
export function TopProgress({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="progress"
          className="pointer-events-none fixed inset-x-0 top-16 z-30 h-px overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={T_MICRO}
          aria-hidden="true"
        >
          <motion.div
            className="h-px w-1/3 bg-ink-3"
            initial={{ x: "-100%" }}
            animate={reduce ? { x: "0%" } : { x: ["-100%", "300%"] }}
            transition={
              reduce
                ? T_MICRO
                : { duration: 0.9, ease: "linear", repeat: Infinity }
            }
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/* --------------------------------------------------------------------------
 * Pagination — bottom page indicators, never endless scroll.
 * Windowed 1 … 4 5 6 … 12 so the control never wraps on mobile.
 * -------------------------------------------------------------------------- */
function pageWindow(current: number, total: number): Array<number | "gap"> {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = new Set<number>([1, total, current, current - 1, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const out: Array<number | "gap"> = [];
  let previous = 0;
  for (const page of sorted) {
    if (previous && page - previous > 1) out.push("gap");
    out.push(page);
    previous = page;
  }
  return out;
}

export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
  busy = false,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (next: number) => void;
  busy?: boolean;
}) {
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const current = Math.floor(offset / limit) + 1;
  if (pageCount <= 1) return null;

  const go = (page: number) => onOffsetChange((Math.min(Math.max(page, 1), pageCount) - 1) * limit);

  return (
    <nav
      aria-label={copy.common.pagination}
      className="mt-sp-7 flex items-center justify-between border-t border-stroke-subtle pt-sp-6"
    >
      <span className="t-caption text-ink-5">
        {copy.common.pageOf(current, pageCount, total)}
      </span>

      <div className="flex items-center gap-sp-2">
        <PageStep
          label={copy.common.previous}
          disabled={current <= 1 || busy}
          onClick={() => go(current - 1)}
        >
          <ChevronLeft size={15} strokeWidth={1.5} />
        </PageStep>

        {pageWindow(current, pageCount).map((entry, index) =>
          entry === "gap" ? (
            <span key={`gap-${index}`} className="t-caption px-sp-2 text-ink-5">
              …
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              aria-current={entry === current ? "page" : undefined}
              disabled={busy}
              onClick={() => go(entry)}
              className={cn(
                "focus-ring t-mono-s h-8 min-w-8 rounded-r-2 px-sp-3 transition-all duration-200 active:scale-[0.98]",
                entry === current
                  ? "border border-stroke-strong bg-surface-3 text-ink-1"
                  : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
              )}
            >
              {entry}
            </button>
          ),
        )}

        <PageStep
          label={copy.common.next}
          disabled={current >= pageCount || busy}
          onClick={() => go(current + 1)}
        >
          <ChevronRight size={15} strokeWidth={1.5} />
        </PageStep>
      </div>
    </nav>
  );
}

function PageStep({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="focus-ring flex h-8 w-8 items-center justify-center rounded-r-2 text-ink-4 transition-all duration-200 hover:bg-surface-2 hover:text-ink-1 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------------------------
 * DataSection — one component that owns the four states of every list, so no
 * screen can invent a fifth. Loading keeps the page's height; error never
 * replaces the whole page; empty is designed.
 * -------------------------------------------------------------------------- */
export function DataSection<T>({
  label,
  right,
  state,
  items,
  skeletonRows = 5,
  empty,
  onRetry,
  children,
}: {
  label?: string;
  right?: ReactNode;
  state: { isPending: boolean; isFetching: boolean; error: unknown };
  items: T[] | undefined;
  skeletonRows?: number;
  empty: { title: string; body: string; action?: ReactNode };
  onRetry?: () => void;
  children: (items: T[]) => ReactNode;
}) {
  const { isPending, isFetching, error } = state;

  return (
    <PageSection label={label} right={right}>
      <Card>
        {isPending ? (
          <SkeletonList rows={skeletonRows} />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} />
        ) : !items || items.length === 0 ? (
          <EmptyState title={empty.title} body={empty.body} action={empty.action} />
        ) : (
          <motion.div
            // Content fades in but does not move: no layout shift, no jump.
            initial={{ opacity: 0 }}
            animate={{ opacity: isFetching ? 0.55 : 1 }}
            transition={T_BASE}
          >
            {children(items)}
          </motion.div>
        )}
      </Card>
    </PageSection>
  );
}

/** Inline, section-scoped failure. Never a toast, never a whole-page takeover. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  // errorMessage() already covers 401 / 403 / 429 / transport (Cookbook 2).
  const { errorMessage } = require("@/lib/api/errors") as typeof import("@/lib/api/errors");
  return (
    <div className="flex flex-col items-start gap-sp-5 py-sp-8">
      <div className="hatch-45 h-6 w-full rounded-r-1 opacity-40" aria-hidden="true" />
      <div>
        <div className="t-body-strong text-ink-1">{copy.common.couldNotLoad}</div>
        <p className="t-caption mt-sp-2 max-w-md text-ink-4">{errorMessage(error)}</p>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {copy.common.tryAgain}
        </Button>
      ) : null}
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Panel — the detail surface for a conversation, request, or invoice.
 * Right-hand sheet on desktop, bottom sheet on mobile. Focus is trapped by
 * nothing clever: it is a plain dialog with Escape + backdrop close, which is
 * what the existing design language implies.
 * -------------------------------------------------------------------------- */
export function Panel({
  open,
  onClose,
  title,
  subtitle,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-30 bg-n-0/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={T_BASE}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="fixed inset-x-0 bottom-0 z-30 max-h-[88vh] overflow-y-auto rounded-t-r-4 border-t border-stroke-default bg-surface-1 p-sp-8 lg:inset-y-0 lg:left-auto lg:right-0 lg:max-h-none lg:w-[520px] lg:rounded-none lg:border-l lg:border-t-0"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            transition={T_PANEL}
          >
            <div className="flex items-start justify-between gap-sp-6">
              <div className="min-w-0">
                <h2 className="t-title-3 truncate text-ink-1">{title}</h2>
                {subtitle ? <p className="t-caption mt-sp-2 text-ink-4">{subtitle}</p> : null}
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={onClose}
                aria-label={copy.common.close}
                className="focus-ring t-ui flex h-8 items-center rounded-r-2 px-sp-4 text-ink-4 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
              >
                {copy.common.close}
              </button>
            </div>
            <div className="mt-sp-8">{children}</div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

/** Row that opens a Panel. Hover elevation + press feedback, keyboard-first. */
export function InteractiveRow({
  onClick,
  children,
  className,
}: {
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "focus-ring block w-full rounded-r-2 px-sp-4 py-sp-6 text-left transition-all duration-200",
        "hover:bg-surface-2 hover:shadow-elev-1 active:scale-[0.995]",
        className,
      )}
    >
      {children}
    </button>
  );
}

/** Tabs with an animated underline. Wraps the existing Tabs contract. */
export function AnimatedTabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-sp-2 border-b border-stroke-subtle">
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={cn(
              "focus-ring t-ui relative h-10 rounded-t-r-2 px-sp-5 transition-colors duration-200",
              active ? "text-ink-1" : "text-ink-4 hover:text-ink-2",
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span className="t-mono-s ml-sp-3 text-ink-5">{tab.count}</span>
            ) : null}
            {active ? (
              <motion.span
                layoutId="tab-underline"
                className="absolute inset-x-sp-4 -bottom-px h-px bg-ink-1"
                transition={T_BASE}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/** Panel body that cross-fades when the active tab changes. */
export function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={T_BASE}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/** Metric tile — the anti-cramming device: one number, one label, real space. */
export function MetricTile({
  label,
  value,
  hint,
  size = "m",
}: {
  label: string;
  value: string;
  hint?: string;
  size?: "m" | "l" | "xl";
}) {
  const type = size === "xl" ? "t-metric-xl" : size === "l" ? "t-metric-l" : "t-metric-m";
  return (
    <div className="min-w-0">
      <div className="t-micro-2 text-ink-5">{label}</div>
      <div className={cn(type, "mt-sp-3 truncate text-ink-1")}>{value}</div>
      {hint ? <div className="t-caption mt-sp-2 truncate text-ink-4">{hint}</div> : null}
    </div>
  );
}
```

> Replace the `require("@/lib/api/errors")` line with a normal top-of-file `import { errorMessage } from "@/lib/api/errors";` — it is written inline above only to keep the snippet self-contained. A CommonJS `require` in a Vite/TS file will fail lint.

**Copy additions:**

```ts
  common: {
    back: "Back",
    tryAgain: "Try again",
    close: "Close",
    loading: "Loading",
    couldNotLoad: "We could not load this",
    pagination: "Pages",
    previous: "Previous page",
    next: "Next page",
    pageOf: (page: number, pages: number, total: number) =>
      `Page ${page} of ${pages} · ${total} item${total === 1 ? "" : "s"}`,
  },
```

---

## 4.2 Grid rules — the actual anti-overlap fix

The shell gives `max-w-6xl px-sp-8 py-sp-9` (verified in `portal-shell.tsx`). Inside it, exactly four layouts are permitted:

| Layout | Tailwind | Used by |
|---|---|---|
| **Stack** | `space-y-sp-9` | every page root |
| **Metric band** | `grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3` | Billing hero, Services plan, Activity hero |
| **Split** | `grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]` | `/security`, `/profile`, `/preferences` (already the pattern in `security.tsx` — keep it) |
| **List** | `divide-y divide-stroke-subtle` rows at `py-sp-6` | every collection |

Hard constraints that remove the current crowding:

1. **Every flex row that contains text carries `min-w-0` on the text child** — this single omission causes most of the current overlap, because a long `subject` or `user_agent` refuses to shrink. Pair with `truncate`.
2. **Never more than 4 columns** in a table on `lg`, never more than 2 on `sm`. Extra fields move into the `Panel`, not into a narrower column.
3. **Numbers right-aligned and `t-mono-s`/`t-mono`**, labels left-aligned. `tabular-nums` is inherent to the mono utilities already defined.
4. **Icons are `shrink-0`**, always inside a `h-9 w-9` `rounded-r-2` tile (the pattern `security.tsx` already uses).
5. **A card never nests a card.** Nested `Card` was one of the crowding sources; use `Divider` + `SectionLabel` inside a single `Card`.
6. **Sticky things get z-indices from the token block only** — topbar `z-20` (existing), `TopProgress` `z-30`, `Panel` `z-30`, call bar `--z-callbar: 40`, grain `9999`. Nothing else may declare a z-index.

---

## 4.3 Per-tab composition (final layout spec)

### `/activity`
1. **Hero** — last conversation: `MetricTile` band × 3 (`When` · `Duration` · `Turns`) + disposition `StatusChip` + “Open conversation” button.
2. `AnimatedTabs`: All / Conversations / Requests / Callbacks (counts from `total`).
3. `DataSection` list, **10 rows per page**, `Pagination` at the bottom.
4. Row → `Panel` with the masked transcript (Cookbook 5 renders turns with the same bubble component as the live view).
5. `copy.activity.loadMore` is **deleted** with the endless-scroll behaviour.

### `/requests`
1. Hero only when something needs attention (`status ∈ {open, in_progress, pending}` exists), otherwise skip — no empty hero shell.
2. Tabs Active / Resolved / All, mapped to the **five** DB statuses.
3. `DataSection`, 10 per page, `Pagination`.
4. Row → read-only `Panel`: reference, category, priority, created/updated, status timeline built from the two timestamps only. No reply box (Cookbook 1).

### `/services`
1. **YOUR PLAN** — metric band from `customer_360.subscriptions`: plan name (`t-metric-l`), MSISDN (`t-mono`), status chip.
2. **BALANCES** (prepaid only) — `Meter` per data balance with `overNote`, `quantity()` for the value, `expires_on` as hint.
3. Nothing else. Add-ons and “available to add” are gone.

### `/billing`
1. Hero: `MetricTile size="xl"` **AMOUNT DUE** = `money(total_outstanding, currency_code)`; hint = next `due_date`.
2. Postpaid: invoice list — 4 columns max (`invoice_number` · period · `total_amount` · status), `outstanding_amount` in the `Panel`.
3. Prepaid: balance cards + recharge history.
4. `Pagination` when invoices exceed 10.
5. No payment method, no PDF, no “retry payment”.

### `/security`
Keep the existing left-nav split layout. Sessions list uses `deviceLabel`, `relative`, and a single `StatusChip` for the current device. One destructive-adjacent action (“Sign out of every device”), placed in the `SectionLabel right` slot, `variant="secondary"` — **not** `danger`, which is reserved for irreversible actions that no longer exist here.

### `/help`, `/about`
Static. `/help` = topic grid (`sm:grid-cols-2`) + one contact card whose primary action is “Start a conversation” → `/assistant`.

### Topbar
Brand block (rail already has it) · `PAGE_HEAD` title · notification tray · `AccountMenu`. The dead search button is gone; if a search returns later it must be a real route, not an icon.

---

## 4.4 Branding in the rail

Today: a hand-drawn `N` tile plus `copy.brand.name` and `copy.brand.version`. Keep the geometry (`h-8 w-8`, `rounded-r-2`, `border-stroke-strong`, `bg-surface-4`, `shadow-elev-1`) and make it a real mark:

**Add** `src/components/shell/brand-mark.tsx`:

```tsx
/**
 * Inline SVG so the mark inherits currentColor and needs no network request.
 * Achromatic on purpose: the whole portal is greyscale, and the orb is the only
 * light source in the design.
 */
export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 19V5l14 14V5"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

In `portal-rail.tsx`, swap `<span className="t-mono-l text-ink-1">N</span>` for `<BrandMark />` and keep the collapsed state showing only the tile. `copy.brand.version` (“Version 1.0.0”) stays but must be kept true — if it is not maintained, delete it rather than let it rot.

---

## 4.5 Route-level progress

In `_portal.tsx`’s layout component:

```tsx
import { useRouterState } from "@tanstack/react-router";
import { useIsFetching } from "@tanstack/react-query";
import { TopProgress } from "@/components/portal/data";

function PortalLayout() {
  const navigating = useRouterState({ select: (s) => s.status === "pending" });
  const fetching = useIsFetching() > 0;
  return (
    <PortalShell>
      <TopProgress active={navigating || fetching} />
      <Outlet />
    </PortalShell>
  );
}
```

Page transitions: wrap `<Outlet />` in a `TabPanel`-style cross-fade keyed on `location.pathname`, 220 ms, opacity + 6 px rise only. **No horizontal slide** — the rail is fixed and a slide would visually detach the content from it.

---

## 4.6 State machine every screen obeys

| State | Rendering | Never |
|---|---|---|
| first load | `SkeletonList` / `SkeletonMetric` sized to the real content | a spinner in the middle of an empty page |
| refetch / page change | previous data at `opacity 0.55` + `TopProgress` (`keepPreviousData`) | blanking the list |
| empty | `EmptyState` with a real next action | “No data” |
| filtered empty | `copy.empty.filtered` with “Clear filters” | the generic empty state |
| error | `ErrorState` inside the section + retry | a toast, or a whole-page error |
| 401 | redirect to `/logout?reason=expired` (Cookbook 2) | an inline error the user cannot act on |
| success (mutation) | `sonner` toast | an inline banner that shifts the layout |

---

## 4.7 Accessibility and motion budget

* Every animation: **opacity + ≤ 8 px transform + ≤ 1.5 % scale**, 120–280 ms. Nothing animates `width`, `height`, `top`, or `left`.
* `useReducedMotion()` from `motion/react` gates `TopProgress`; the global `prefers-reduced-motion` block in `styles.css` and the manual `[data-reduce-motion="true"]` mirror (Cookbook 1) handle the CSS side.
* `aria-busy` on skeleton containers, `aria-current="page"` on the active page button, `role="tablist"/"tab"` + `aria-selected` on tabs, `role="dialog"` + `aria-modal` + Escape on `Panel`, `aria-live="polite"` on the transcript stack (Cookbook 5).
* Touch targets ≥ 32 px (`h-8`) and ≥ 36 px (`h-9`) for primary rows — the existing rail/tabbar heights already satisfy this.
* Focus is visible everywhere via the existing `focus-ring` utility; never add `outline-none` without it.

---

## 4.8 Acceptance

| # | Check |
|---|---|
| 1 | 320 px wide: no horizontal scrollbar on any of the ten tabs; the tabbar does not cover the last row (`pb-20` already in the shell) |
| 2 | 1440 px: no line of body text wider than ~72 characters; no card taller than the viewport without an internal scroll |
| 3 | Every list of >10 items shows bottom page indicators; no “Load more” survives (`git grep -n "loadMore"` → empty) |
| 4 | Changing page keeps the previous rows visible, dimmed, with `TopProgress` running; the layout does not jump |
| 5 | Throttle to Slow 3G: skeletons appear within 100 ms and are the same height as the rows that replace them |
| 6 | With OS reduced-motion on: no looping animation anywhere, including `TopProgress` |
| 7 | Keyboard only: tab to a row, Enter opens the `Panel`, Escape closes it, focus returns to the row |
| 8 | `git grep -nE "#[0-9a-fA-F]{3,8}" -- Frontend/customer_portal/src` → only `orb-renderer.ts`/`orb-config.ts` if at all |
| 9 | `git grep -nE "rounded-(sm\|md\|lg\|xl\|2xl\|3xl\|full)" -- Frontend/customer_portal/src` → only `rounded-full` on genuinely circular things (avatar, orb frame) |
| 10 | `git grep -nE "text-(xs\|sm\|base\|lg\|xl\|[0-9]xl)" -- Frontend/customer_portal/src` → empty (type comes only from the 18 `t-*` utilities) |
| 11 | `git grep -n "z-\[" -- Frontend/customer_portal/src` → empty; z-indices come from the token scale |
| 12 | Lighthouse a11y ≥ 95 on `/activity`, `/billing`, `/security` |

### Rollback

`data.tsx` and `brand-mark.tsx` are new files; the page edits are layout-only. Reverting the commit restores the previous screens without touching data or backend.
