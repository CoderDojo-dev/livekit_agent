import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Sparkline, Delta } from "@/components/nexus/primitives";
import { cn } from "@/lib/utils";

type MetricIcon = React.ComponentType<{ size?: number; strokeWidth?: number }>;

/**
 * The notched metric card.
 *
 * Shape follows the reference: the card's top-right corner is left clear and an action control
 * floats in the gap, ringed by the page colour so it reads as a notch cut out of the card rather
 * than a button parked on top of it. The ring is `bg-surface-0` — the page behind — so the
 * illusion holds in both themes without a mask or a clip-path.
 *
 * Two deliberate departures from the reference, both to stay inside the design bible:
 *  - the icon frame and the action are squircles (rounded-r-2 / rounded-r-3), never true circles
 *    (chapter 4.6, "no perfect circles");
 *  - nothing is coloured. Emphasis is weight and ink level, as everywhere else.
 *
 * The footer takes up to two supporting figures. That is the pattern that makes the reference
 * cards work: one dominant number, then the two facts that qualify it, separated by a rule — so
 * the card answers "how many" and "of what kind" without a second card.
 */
export function MetricCard({
  label,
  value,
  icon: Icon,
  footer,
  series,
  delta,
  good,
  context,
  to,
  onAction,
  actionLabel,
  className,
}: {
  label: string;
  value: string;
  icon?: MetricIcon | undefined;
  /** Up to two supporting figures, rendered under a divider. */
  footer?: readonly { label: string; value: string; title?: string }[] | undefined;
  series?: number[] | undefined;
  delta?: number | undefined;
  good?: boolean | null | undefined;
  context?: string | undefined;
  /** Router destination for the corner action. Omit both `to` and `onAction` to hide it. */
  to?: string | undefined;
  onAction?: (() => void) | undefined;
  actionLabel?: string | undefined;
  className?: string | undefined;
}) {
  const label_ = actionLabel ?? `Open ${label}`;

  const action =
    to === undefined && onAction === undefined ? null : (
      /* The ring: page-coloured padding around the control carves the corner out of the card. */
      <div className="absolute right-0 top-0 rounded-r-4 bg-surface-0 p-[4px]">
        {to !== undefined ? (
          <Link to={to as "/overview"} aria-label={label_} title={label_} className={ACTION_CLASS}>
            <ArrowUpRight size={14} strokeWidth={1.6} aria-hidden="true" />
          </Link>
        ) : (
          <button
            type="button"
            aria-label={label_}
            title={label_}
            onClick={onAction}
            className={ACTION_CLASS}
          >
            <ArrowUpRight size={14} strokeWidth={1.6} aria-hidden="true" />
          </button>
        )}
      </div>
    );

  return (
    // pt/pr reserve the notch so the action never overlaps the card's own content.
    <div className={cn("group relative pr-[14px] pt-[14px]", className)}>
      <div
        className={cn(
          "flex h-full flex-col rounded-r-4 border border-stroke-default bg-surface-2 p-sp-5 shadow-elev-1",
          "transition-[border-color,box-shadow] duration-[160ms] group-hover:border-stroke-strong group-hover:shadow-elev-2",
        )}
      >
        {/* ---- Header: icon + label, with the delta trailing if there is one ---- */}
        <div className="flex items-center gap-sp-4">
          {Icon ? (
            <span className="inline-flex size-[26px] shrink-0 items-center justify-center rounded-r-2 border border-stroke-strong text-ink-3 transition-colors duration-[160ms] group-hover:border-stroke-ink group-hover:text-ink-1">
              <Icon size={13} strokeWidth={1.5} />
            </span>
          ) : null}
          <p className="t-label min-w-0 flex-1 truncate text-ink-3">{label}</p>
          {delta === undefined ? null : <Delta value={delta} good={good ?? null} />}
        </div>

        {/* ---- The number ----
             t-metric-l (26px). It began at t-display (40px), which dominated a card it was meant
             to sit inside and forced the box square. Measured: 40px gave a 204px card, 26px gives
             152px. Dropping further to 20px saved only 6px more and left the figure no longer
             reading as the card's headline, so the height came out of the PADDING instead. */}
        <p className="t-metric-l mt-sp-4 text-ink-1">{value}</p>
        {context ? (
          // Two lines maximum: a long context line was the other half of the height problem.
          <p className="t-caption mt-sp-2 line-clamp-2 text-ink-4">{context}</p>
        ) : null}

        {series ? <Sparkline values={series} className="mt-sp-4" /> : null}

        {/* ---- Supporting figures, under a rule.
             Label and value share ONE line each rather than stacking, which halves the footer.
             mt-auto pins the block to the card floor so a row of cards aligns its footers even
             when the contexts differ in length. ---- */}
        {footer && footer.length > 0 ? (
          <div className="mt-auto space-y-sp-1 border-t border-stroke-subtle pt-sp-4">
            {footer.slice(0, 2).map((item) => (
              <div key={item.label} className="flex items-baseline justify-between gap-sp-4">
                <span className="t-caption min-w-0 truncate text-ink-5">{item.label}</span>
                {/* max-w so a long value (an env var name) truncates instead of wrapping the
                    row onto a second line and pushing the card taller than its neighbours. */}
                <span
                  className="t-label max-w-[62%] shrink-0 truncate text-ink-1"
                  title={item.title ?? item.value}
                >
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {action}
    </div>
  );
}

const ACTION_CLASS = cn(
  "inline-flex size-[28px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4",
  "transition-[background-color,border-color,color,transform] duration-[160ms]",
  "hover:border-stroke-ink hover:bg-surface-3 hover:text-ink-1 active:translate-y-px",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface-0",
);

/** Grid wrapper matching the reference's four-across rhythm, collapsing sensibly. */
export function MetricRow({ children }: { children: ReactNode }) {
  return <div className="grid gap-sp-5 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}
