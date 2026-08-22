import * as React from "react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronLeft, ChevronRight, RotateCw, TriangleAlert, type LucideIcon } from "lucide-react";
import { Button, Card, EmptyState, IconFrame, SectionLabel } from "@/components/portal/primitives";
import { copy } from "@/lib/copy";
import { usePortalReducedMotion } from "@/hooks/use-portal-motion";
import { errorMessage } from "@/lib/api/errors";
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
/** Stage transition: the orb moving between centred and left. Slower than a
 *  panel because it carries the largest element on screen. */
export const T_STAGE = { duration: 0.48, ease: EASE_OUT } as const;

/* --------------------------------------------------------------------------
 * PageSection — the only vertical rhythm in the portal.
 * .portal-section is the hook the compact-density CSS rule uses.
 * -------------------------------------------------------------------------- */
export function PageSection({
  label,
  right,
  children,
  className,
  index = 0,
}: {
  label?: string | undefined;
  right?: ReactNode | undefined;
  children: ReactNode;
  className?: string | undefined;
  /**
   * Position in the page, used only to stagger the entrance. Capped at four
   * steps (240ms): past that the reader is waiting on the animation rather
   * than watching the page arrive, which is the opposite of the point.
   */
  index?: number | undefined;
}) {
  return (
    <section
      className={cn("portal-section", className)}
      style={{ "--rise-delay": `${Math.min(index, 4) * 60}ms` } as React.CSSProperties}
    >
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
  const reduce = usePortalReducedMotion();
  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="progress"
          className="pointer-events-none fixed inset-x-0 top-16 z-30 h-0.5 overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={T_MICRO}
          aria-hidden="true"
        >
          <motion.div
            className="h-0.5 w-1/3 bg-ink-3"
            initial={{ x: "-100%" }}
            animate={reduce ? { x: "0%" } : { x: ["-100%", "300%"] }}
            transition={reduce ? T_MICRO : { duration: 0.9, ease: "linear", repeat: Infinity }}
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
export function pageWindow(current: number, total: number): Array<number | "gap"> {
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
      <span className="t-caption text-ink-5">{copy.common.pageOf(current, pageCount, total)}</span>

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
  index,
  icon,
}: {
  label?: string;
  right?: ReactNode;
  state: { isPending: boolean; isFetching: boolean; isPlaceholderData?: boolean; error: unknown };
  items: T[] | undefined;
  skeletonRows?: number;
  empty: { title: string; body: string; action?: ReactNode; icon?: LucideIcon | undefined };
  onRetry?: () => void;
  children: (items: T[]) => ReactNode;
  /** Entrance stagger, forwarded to PageSection. */
  index?: number | undefined;
  /** Glyph for the empty state, when the caller has not put one in `empty`. */
  icon?: LucideIcon | undefined;
}) {
  const { isPending, error } = state;

  return (
    <PageSection label={label} right={right} index={index}>
      <Card>
        {isPending ? (
          <SkeletonList rows={skeletonRows} />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} />
        ) : !items || items.length === 0 ? (
          <EmptyState
            title={empty.title}
            body={empty.body}
            action={empty.action}
            icon={empty.icon ?? icon}
          />
        ) : (
          <motion.div
            // Dim only when the rows on screen are about to be replaced by a
            // different page. A background refresh of the same page must not
            // flash: nothing the customer asked for is changing.
            initial={{ opacity: 0 }}
            animate={{ opacity: state.isPlaceholderData ? 0.55 : 1 }}
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
export function ErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: (() => void) | undefined;
}) {
  // errorMessage() already covers 401 / 403 / 429 / transport (Cookbook 2).
  return (
    <div className="flex flex-col items-start gap-sp-5 py-sp-7">
      {/* The hatch is the portal's failure texture (38.4). It keeps its band,
          but the glyph and the sentence now sit on one line under it, so a
          failed section reads as a short notice rather than a stack. */}
      <div className="hatch-45 h-5 w-full rounded-r-1 opacity-40" aria-hidden="true" />
      <div className="flex items-start gap-sp-5">
        <IconFrame icon={TriangleAlert} tone="strong" />
        <div className="min-w-0">
          <div className="t-body-strong text-ink-1">{copy.common.couldNotLoad}</div>
          <p className="t-caption mt-sp-2 max-w-md text-ink-4">{errorMessage(error)}</p>
        </div>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RotateCw size={14} strokeWidth={1.5} />
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
  subtitle?: string | undefined;
  children: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;

    // Remember where focus came from so Escape returns the customer to the row
    // they opened, not to the top of the page.
    const opener = document.activeElement as HTMLElement | null;

    // Lock the page behind the sheet. Without this, a mobile bottom sheet
    // scrolls the list underneath it.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      // Minimal, dependency-free focus cycle across the sheet's own tabbables.
      const root = sheetRef.current;
      if (!root) return;
      const focusable = root.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0] as HTMLElement;
      const last = focusable[focusable.length - 1] as HTMLElement;
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    closeRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      opener?.focus?.();
    };
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
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="fixed inset-x-0 bottom-0 z-30 max-h-[88vh] overflow-y-auto rounded-t-r-4 border-t border-stroke-default bg-surface-1 p-sp-8 lg:inset-y-0 lg:start-auto lg:end-0 lg:max-h-none lg:w-[520px] lg:rounded-none lg:border-s lg:border-t-0"
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
        // `group` so the row's own children can answer the cursor - the icon
        // frames brighten, the chevron slides. `row-accent` grows the same 2px
        // leading stroke the rail uses for the active destination.
        "focus-ring group row-accent block w-full rounded-r-2 px-sp-5 py-sp-6 text-start transition-all duration-200",
        "hover:bg-surface-2 hover:shadow-elev-1 active:scale-[0.995]",
        className,
      )}
    >
      {children}
    </button>
  );
}

/**
 * The chevron that ends an InteractiveRow.
 *
 * Holds its width at rest and only fades and slides, so nothing on the row
 * moves when the cursor arrives - the same rule the rail's shortcut hint
 * follows. Opt-in: a row whose last cell is already a status chip does not
 * need a second "there is more this way".
 */
export function RowChevron() {
  return (
    <ChevronRight
      size={15}
      strokeWidth={1.5}
      aria-hidden="true"
      className="shrink-0 text-ink-5 opacity-0 transition-all duration-200 group-hover:translate-x-sp-1 group-hover:text-ink-3 group-hover:opacity-100"
    />
  );
}

/** Tabs with an animated underline. Accepts a groupId so multiple tab groups
 * on one page each animate their own underline, preventing the underline from
 * flying across the screen between unrelated groups. */
export function AnimatedTabs<T extends string>({
  tabs,
  value,
  onChange,
  /** Distinct per tab group on a page: a shared layoutId makes the underline
   *  fly between unrelated groups. Defaults to a stable per-mount id. */
  groupId,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (next: T) => void;
  groupId?: string;
}) {
  const autoId = useId();
  const underlineId = `tab-underline-${groupId ?? autoId}`;
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
              <span className="t-mono-s ms-sp-3 text-ink-5">{tab.count}</span>
            ) : null}
            {active ? (
              <motion.span
                layoutId={underlineId}
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

/** Panel body that cross-fades when the active tab changes. className lets a
 *  scene route (the assistant, which owns its height) stretch this wrapper:
 *  without a definite height here, h-full inside the route content resolves
 *  to auto and the scene's internal scroll regions can never engage. */
export function TabPanel({
  id,
  children,
  className,
}: {
  id: string;
  children: ReactNode;
  className?: string | undefined;
}) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={id}
        className={cn(className)}
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

/**
 * Disclosure — one question, one answer, height-animated.
 *
 * `height: auto` is animatable here because Framer measures the element first.
 * A hard-coded max-height is the usual substitute and it clips the moment an
 * answer runs to three lines, which is most of them.
 *
 * The whole header is the control (a button, not a div with a click handler),
 * so it is reachable by keyboard and announces its state through
 * aria-expanded. The chevron only rotates; it never changes glyph, because a
 * glyph swap under the cursor reads as two different buttons.
 */
export function Disclosure({
  question,
  children,
  defaultOpen = false,
}: {
  question: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const reduce = usePortalReducedMotion();
  const id = useId();

  return (
    <div className="border-b border-stroke-subtle last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={id}
        className="focus-ring group flex w-full items-center gap-sp-5 rounded-r-2 py-sp-6 text-start transition-colors duration-200"
      >
        <ChevronRight
          size={15}
          strokeWidth={1.5}
          aria-hidden="true"
          className={cn(
            "shrink-0 text-ink-5 transition-transform duration-200 group-hover:text-ink-3",
            open && "rotate-90",
          )}
        />
        <span
          className={cn(
            "t-body-strong min-w-0 flex-1 transition-colors duration-200",
            open ? "text-ink-1" : "text-ink-2 group-hover:text-ink-1",
          )}
        >
          {question}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={id}
            key="answer"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={
              reduce
                ? { duration: 0 }
                : {
                    height: { duration: 0.24, ease: EASE_OUT },
                    opacity: { duration: 0.12, ease: EASE_OUT },
                  }
            }
            style={{ overflow: "hidden" }}
          >
            {/* The indent lines the answer up with the question, not with the
                chevron: the answer belongs to the words, not to the marker. */}
            <div className="pb-sp-6 ps-sp-8">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

/** Metric tile — the anti-cramming device: one number, one label, real space. */
export function MetricTile({
  label,
  value,
  hint,
  size = "m",
  share,
  icon,
  /** Shows a shimmer at the value's own type size instead of a placeholder
   *  glyph, so "still loading" is never read as "zero" or "nothing". */
  pending = false,
}: {
  label: string;
  value: string;
  hint?: string | undefined;
  size?: "m" | "l" | "xl";
  /**
   * Sits beside the label, never beside the number. A tile is read
   * label-then-figure; an icon next to the figure competes with it for the
   * one thing the tile exists to say.
   */
  icon?: LucideIcon | undefined;
  /**
   * A hairline proportion bar under the value. Only pass this when the metric
   * genuinely IS a part of a whole that the same payload already carries -
   * active lines out of all lines, paid out of billed. It is not a trend and
   * there is no history behind it: a tile with no real denominator gets no
   * bar rather than a decorative one.
   */
  share?: { of: number; value: number } | undefined;
  pending?: boolean;
}) {
  const type = size === "xl" ? "t-metric-xl" : size === "l" ? "t-metric-l" : "t-metric-m";
  const barHeight = size === "xl" ? "h-10" : size === "l" ? "h-8" : "h-6";
  const ratio = share && share.of > 0 ? Math.min(Math.max(share.value / share.of, 0), 1) : null;
  return (
    <div className="group/tile min-w-0">
      <div className="flex items-center gap-sp-4">
        {icon ? <IconFrame icon={icon} size="sm" /> : null}
        <div className="t-micro-2 min-w-0 truncate text-ink-5">{label}</div>
      </div>
      {pending ? (
        <div
          className={cn("skeleton mt-sp-3 w-32 rounded-r-2", barHeight)}
          role="status"
          aria-busy="true"
          aria-label={copy.common.loading}
        />
      ) : (
        <div className={cn(type, "mt-sp-3 truncate text-ink-1")}>{value}</div>
      )}
      {ratio !== null && !pending ? (
        <div
          className="mt-sp-4 h-px w-full bg-stroke-subtle"
          role="img"
          aria-label={copy.common.shareOf(share!.value, share!.of)}
        >
          <div
            className="h-full bg-ink-3 transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      ) : null}
      {hint && !pending ? (
        <div className="t-caption mt-sp-2 truncate text-ink-4">{hint}</div>
      ) : null}
    </div>
  );
}
