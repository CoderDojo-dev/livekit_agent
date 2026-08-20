import { formatInteger } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

/**
 * A row of filterable counters.
 *
 * Consolidates three hand-rolled implementations that had drifted apart: /tickets (grid-cols-5),
 * /notifications (grid-cols-3, the same idiom copy-pasted) and /knowledge (`HealthValue`, a
 * private near-duplicate). Each had its own grid, none had a hover state, and only two of them
 * were actually clickable — so the same visual promised different behaviour on different pages.
 *
 * Deliberately NOT StatCard: these numbers have no comparison period, and StatCard's shape
 * implies a delta that does not exist. That distinction is load-bearing in this product (see the
 * `F9: not StatCard — no delta exists` comments the original pages carried).
 *
 * Selecting the active item clears the filter, so the strip is a toggle rather than a radio group
 * with no escape.
 */

export type CountItem = {
  id: string;
  label: string;
  value: number;
};

export function CountStrip({
  items,
  active,
  onSelect,
  loading = false,
}: {
  items: CountItem[];
  /** The currently filtered id, or "" for no filter. */
  active: string;
  onSelect: (id: string) => void;
  loading?: boolean | undefined;
}) {
  return (
    <div
      role="group"
      aria-label="Filter by status"
      /* auto-fit rather than a fixed column count: three counters and five counters both fill
       * the card, and the strip reflows to two rows on a phone instead of crushing to 5 columns
       * of 40px. */
      className="grid gap-sp-4 [grid-template-columns:repeat(auto-fit,minmax(128px,1fr))]"
    >
      {items.map((item) => {
        const selected = active === item.id;

        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(selected ? "" : item.id)}
            className={cn(
              "group relative rounded-r-3 border px-sp-5 py-sp-5 text-left",
              "transition-[background-color,border-color,transform] duration-[120ms] active:translate-y-px",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              selected
                ? "border-stroke-strong bg-surface-3"
                : "border-transparent hover:border-stroke-default hover:bg-surface-3/50",
            )}
          >
            <span className="t-micro block truncate text-ink-5">{item.label}</span>

            {loading ? (
              <span className="shimmer mt-sp-3 block h-[20px] w-[56px] rounded-r-1" />
            ) : (
              <span
                className={cn(
                  "t-metric-m mt-sp-2 block transition-colors duration-[120ms]",
                  selected ? "text-ink-1" : "text-ink-3 group-hover:text-ink-2",
                )}
              >
                {formatInteger(item.value)}
              </span>
            )}

            {/* The 2px active rule, matching Tabs. Placed on the card's floor so the strip reads
             * as a row of tabs rather than a row of cards that happen to be clickable. */}
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-x-sp-5 bottom-0 block h-[2px] rounded-t-[1px] transition-opacity duration-[120ms]",
                selected ? "bg-n-12 opacity-100" : "opacity-0",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}
