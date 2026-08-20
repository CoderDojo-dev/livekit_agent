import { type ReactNode } from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { STATUS } from "@/lib/nexus/status";
import { cn } from "@/lib/utils";
import { formatDelta } from "@/lib/nexus/format";
import { useOverflowX } from "@/hooks/use-overflow-x";
import { motion } from "framer-motion";

/* ---------- Card (chapter 19) ---------- */

export function Card({
  children,
  className,
  padded = true,
  interactive = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  /**
   * Border-and-elevation hover response. ON by default so every card in the product answers the
   * pointer without each caller opting in — that consistency is the whole point.
   *
   * Deliberately no translate: a grid where a dozen cards lift under the pointer reads as noise,
   * not as response. Border + shadow says "this is a surface" without moving the page.
   *
   * Set false only for a card that is purely a layout box inside another card.
   */
  interactive?: boolean;
}) {
  return (
    <div
      className={cn(
        "group rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1",
        interactive &&
          "transition-[border-color,box-shadow] duration-[160ms] hover:border-stroke-strong hover:shadow-elev-2",
        padded && "p-sp-7",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon: Icon,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  /** Renders in the bordered frame EmptyState uses. Supply one only when it names the content. */
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number }> | undefined;
}) {
  return (
    <div className="flex items-start justify-between gap-sp-5">
      {/* The block is constrained, not just the subtitle: capping only the <p> left the title
       * spanning 1200px above a 430px caption, which read as a layout bug on wide cards. */}
      <div className="flex min-w-0 max-w-[62ch] items-start gap-sp-5">
        {Icon ? (
          <span className="mt-[1px] inline-flex size-[28px] shrink-0 items-center justify-center rounded-r-2 border border-stroke-default bg-surface-3 text-ink-4">
            <Icon size={14} strokeWidth={1.5} />
          </span>
        ) : null}
        <div className="min-w-0">
          <h2 className="t-title-3 text-ink-1">{title}</h2>
          {subtitle ? <p className="t-caption mt-sp-2 text-ink-4">{subtitle}</p> : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/* ---------- Avatar (square, never round — chapter 4.6) ---------- */

const AVATAR_SIZE = {
  xs: "size-[20px] rounded-r-2 text-[9px]",
  sm: "size-[24px] rounded-r-2 text-[10px]",
  md: "size-[32px] rounded-r-3 text-[11px]",
  lg: "size-[40px] rounded-r-3 text-[13px]",
  xl: "size-[56px] rounded-r-4 text-[16px]",
} as const;

export function Avatar({
  initials,
  size = "md",
  className,
  name,
}: {
  initials: string;
  size?: keyof typeof AVATAR_SIZE;
  className?: string;
  name?: string;
}) {
  return (
    <span
      aria-label={name}
      className={cn(
        "inline-flex shrink-0 items-center justify-center bg-surface-4 font-medium tracking-[0.02em] text-ink-2",
        AVATAR_SIZE[size],
        className,
      )}
    >
      <span aria-hidden="true">{initials}</span>
    </span>
  );
}

/* ---------- Token (chapter 18) ---------- */

export function Token({
  children,
  strong,
  mono = true,
  className,
  title,
}: {
  children: ReactNode;
  strong?: boolean | undefined;
  mono?: boolean | undefined;
  className?: string | undefined;
  /** Native tooltip. Used where a token stands in for longer text (e.g. an admin note). */
  title?: string | undefined;
}) {
  return (
    <span
      {...(title === undefined ? {} : { title })}
      className={cn(
        "inline-flex h-[20px] items-center gap-sp-2 rounded-r-1 px-sp-3",
        mono ? "t-mono-s" : "t-label",
        strong ? "bg-surface-5 text-ink-1" : "bg-surface-4 text-ink-2",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ---------- Navigation count badge ---------- */

/**
 * The compact counter beside a sidebar item.
 *
 * Two weights, because "42 tickets exist" and "7 callbacks are overdue" are not the same claim:
 *  - `attention` inverts (n-12 on n-0) for a queue that is waiting on a human;
 *  - the default is a quiet surface chip for a plain inventory count.
 *
 * Sizing matches `Token` (h-[20px], rounded-r-1, t-mono-s) so a badge and a token can sit in the
 * same row without a baseline fight.
 */
export function NavBadge({
  count,
  attention = false,
  className,
  children,
}: {
  count: number;
  attention?: boolean | undefined;
  className?: string | undefined;
  /** Optional animated renderer (see <CountSwap>). Falls back to the plain number. */
  children?: ReactNode | undefined;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-[18px] min-w-[18px] shrink-0 items-center justify-center overflow-hidden rounded-r-1 px-sp-2 t-mono-s tabular-nums",
        "transition-colors duration-[120ms]",
        attention ? "bg-n-12 text-n-0" : "bg-surface-4 text-ink-3",
        className,
      )}
    >
      {/* Four figures is the widest a 236px rail carries before the label has to truncate. */}
      {children ?? (count > 999 ? "999+" : count)}
    </span>
  );
}

/**
 * A bare presence dot for "there is something here" without a number — used where a count would
 * be noise but silence would be wrong.
 */
export function NavDot({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("block size-[5px] rounded-[1px] bg-n-11", className)} />
  );
}

/* ---------- Status glyphs and chips (chapters 1.6 / 1.7 / 18) ---------- */

function StatusGlyph({ shape, tone }: { shape: string; tone: string }) {
  const common = { width: 8, height: 8, viewBox: "0 0 8 8", "aria-hidden": true as const };
  switch (shape) {
    case "disc":
      return (
        <svg {...common}>
          <rect width="8" height="8" rx="4" fill={tone} />
        </svg>
      );
    case "ring":
      return (
        <svg {...common}>
          <rect
            x="0.75"
            y="0.75"
            width="6.5"
            height="6.5"
            rx="3.25"
            fill="none"
            stroke={tone}
            strokeWidth="1.5"
          />
        </svg>
      );
    case "half":
      return (
        <svg {...common}>
          <rect
            x="0.75"
            y="0.75"
            width="6.5"
            height="6.5"
            rx="3.25"
            fill="none"
            stroke={tone}
            strokeWidth="1.5"
          />
          <path d="M4 0.75 A3.25 3.25 0 0 1 4 7.25 Z" fill={tone} />
        </svg>
      );
    case "triangle":
      return (
        <svg {...common}>
          <path d="M4 0.6 L7.6 7.2 H0.4 Z" fill={tone} />
        </svg>
      );
    case "square":
      return (
        <svg {...common}>
          <rect width="8" height="8" rx="2" fill={tone} />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <rect y="3" width="8" height="2" rx="1" fill={tone} />
        </svg>
      );
  }
}

const LEVEL_TONE: Record<string, string> = {
  critical: "var(--n-12)",
  high: "var(--n-12)",
  medium: "var(--n-11)",
  low: "var(--n-10)",
  inert: "var(--n-8)",
};

export function StatusChip({ status, className }: { status: string; className?: string }) {
  const def = STATUS[status];
  if (!def) return null;
  const inverted = def.container === "inverted";
  const tone = inverted ? "var(--n-0)" : (LEVEL_TONE[def.level] ?? "var(--n-8)");

  return (
    <span
      className={cn(
        "inline-flex h-[22px] items-center gap-sp-2 rounded-r-2 px-sp-4",
        def.container === "soft" && "bg-surface-4 text-ink-2",
        def.container === "outline" && "border border-stroke-strong text-ink-2",
        def.container === "flat" && "text-ink-4",
        inverted && "bg-n-12 text-n-0",
        className,
      )}
    >
      <StatusGlyph shape={def.shape} tone={tone} />
      <span className="t-label whitespace-nowrap">{def.label}</span>
    </span>
  );
}

/* ---------- Priority meter (chapter 1.7) ---------- */

export function PriorityMeter({ priority }: { priority: "high" | "medium" | "low" }) {
  const tones =
    priority === "high"
      ? ["var(--n-12)", "var(--n-12)", "var(--n-12)"]
      : priority === "medium"
        ? ["var(--n-11)", "var(--n-11)", "var(--n-7)"]
        : ["var(--n-10)", "var(--n-7)", "var(--n-7)"];
  const label = priority === "high" ? "High" : priority === "medium" ? "Medium" : "Low";

  return (
    <span className="inline-flex items-center gap-sp-2">
      <span aria-hidden="true" className="flex items-end gap-[2px]">
        {tones.map((tone, i) => (
          <span
            key={i}
            className="block h-[10px] w-[3px] rounded-[1px]"
            style={{ background: tone }}
          />
        ))}
      </span>
      <span className="t-caption text-ink-3">{label}</span>
    </span>
  );
}

/* ---------- Presence dot (documented 6px exception) ---------- */

export function PresenceDot({ live = true, className }: { live?: boolean; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "block size-[6px] rounded-[3px]",
        live ? "bg-n-12 live-dot" : "bg-n-8",
        className,
      )}
    />
  );
}

/* ---------- Buttons ---------- */

export function Button({
  children,
  variant = "secondary",
  size = "md",
  icon: Icon,
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "outline";
  size?: "sm" | "md";
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number }>;
}) {
  return (
    <button
      type="button"
      className={cn(
        // transform + shadow join the transition so :active can depress the button. A 1px drop
        // on press is the cheapest possible "this control is real" signal.
        "inline-flex shrink-0 items-center justify-center gap-sp-4 whitespace-nowrap",
        "transition-[background-color,border-color,color,transform,box-shadow] duration-[120ms]",
        "active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
        size === "sm"
          ? "h-[28px] rounded-r-2 px-sp-5 t-label"
          : "h-[34px] rounded-r-3 px-sp-5 t-ui",
        variant === "primary" && "bg-n-12 text-n-0 hover:bg-n-11",
        variant === "secondary" &&
          "border border-stroke-default bg-surface-3 text-ink-2 hover:border-stroke-strong hover:bg-surface-4 hover:text-ink-1",
        variant === "outline" &&
          "border border-stroke-strong text-ink-2 hover:bg-surface-3 hover:text-ink-1",
        variant === "ghost" && "text-ink-3 hover:bg-surface-3 hover:text-ink-1",
        className,
      )}
      {...rest}
    >
      {Icon ? <Icon size={14} strokeWidth={1.5} /> : null}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  icon: Icon,
  size = "md",
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  size?: "sm" | "md";
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-r-3 text-ink-3 hover:bg-surface-3 hover:text-ink-1",
        "transition-[background-color,color,transform] duration-[120ms] active:translate-y-px",
        size === "sm" ? "size-[28px]" : "size-[34px]",
        className,
      )}
      {...rest}
    >
      <Icon size={16} strokeWidth={1.5} />
    </button>
  );
}

/* ---------- Delta ---------- */

export function Delta({
  value,
  good,
}: {
  value: number;
  /** null = neutral polarity */
  good?: boolean | null;
}) {
  const up = value > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-sp-1 t-label",
        good === false
          ? "text-ink-1 underline decoration-dotted decoration-from-font underline-offset-4"
          : good === true
            ? "text-ink-2"
            : "text-ink-3",
      )}
    >
      <Icon size={12} strokeWidth={1.5} aria-hidden="true" />
      {formatDelta(value)}
    </span>
  );
}

/* ---------- Empty state (chapter 24) ---------- */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  compact = false,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  title: string;
  description: string;
  /** Several empty states are actionable ("Register an advisor…") but had nothing to click. */
  action?: ReactNode | undefined;
  /** Trims the vertical padding for empty states sitting inside a short panel. */
  compact?: boolean | undefined;
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col items-center justify-center px-sp-8 text-center",
        compact ? "py-sp-9" : "py-sp-12",
      )}
    >
      <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
        <Icon size={18} strokeWidth={1.5} />
      </span>
      <p className="t-title-3 text-ink-1">{title}</p>
      <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">{description}</p>
      {action ? <div className="mt-sp-6">{action}</div> : null}
    </div>
  );
}

/* ---------- Table shell (chapter 21) ---------- */

export function TableShell({
  toolbar,
  head,
  children,
  footer,
  minWidth = 720,
  busy = false,
  bodyAsChild = false,
}: {
  toolbar?: ReactNode;
  head: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /**
   * Width below which the table scrolls instead of crushing its columns. Raise it for wide
   * tables (8 columns want ~980); lower it for narrow ones.
   */
  minWidth?: number | undefined;
  /** Shows the indeterminate sweep under the toolbar during a background refetch. */
  busy?: boolean | undefined;
  /**
   * When true, `children` is expected to supply its own <tbody> (so it can be animated by
   * <TableBodySwap>). Otherwise the shell wraps children in a plain <tbody>.
   */
  bodyAsChild?: boolean | undefined;
}) {
  const { ref, edges } = useOverflowX<HTMLDivElement>();

  return (
    <div className="rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1">
      {/* Toolbar and footer live OUTSIDE the scroll region: filters and pagination must never
       * scroll away horizontally with the columns they control. */}
      {toolbar ? (
        <div className="relative flex min-h-[56px] flex-wrap items-center gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-4">
          {toolbar}
          {/* Absolutely positioned so appearing mid-fetch never shifts a single pixel of layout. */}
          <span
            aria-hidden="true"
            className={cn(
              "pointer-events-none absolute inset-x-0 bottom-[-1px] block h-[2px] overflow-hidden transition-opacity duration-[120ms]",
              busy ? "opacity-100" : "opacity-0",
            )}
          >
            {busy ? <span className="progress-sweep block h-full w-full bg-n-11" /> : null}
          </span>
        </div>
      ) : null}

      {/* THE fix for clipped columns: previously this was `overflow-hidden` around a w-full
       * table, so below ~1100px the rightmost columns were silently cut off with no scrollbar
       * and no affordance. Now the table scrolls, and the mask marks the live edge. */}
      <div
        ref={ref}
        data-overflow={edges}
        className="edge-fade-x overflow-x-auto overscroll-x-contain"
      >
        <table className="w-full border-collapse" style={{ minWidth }}>
          <thead>{head}</thead>
          {bodyAsChild ? children : <tbody>{children}</tbody>}
        </table>
      </div>

      {footer ? (
        <div className="flex min-h-[52px] flex-wrap items-center justify-between gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-4">
          {footer}
        </div>
      ) : null}
    </div>
  );
}

export function Th({
  children,
  className,
  align = "left",
}: {
  children?: ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}) {
  return (
    <th
      scope="col"
      className={cn(
        "h-[38px] border-b border-stroke-subtle px-sp-6 t-micro font-medium text-ink-5",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  className,
  align = "left",
  stacked = false,
}: {
  children?: ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
  /**
   * For cells that stack several values. `h-[52px]` is a *minimum* in practice, so a stacking
   * cell used to drag its whole row to 200px while its neighbours stayed vertically centred —
   * which is what made rows look misaligned. Stacked cells align to the top and breathe with
   * padding instead of pretending to be one line tall.
   */
  stacked?: boolean | undefined;
}) {
  return (
    <td
      className={cn(
        "border-b border-stroke-subtle px-sp-6 t-ui text-ink-2",
        stacked ? "py-sp-5 align-top" : "h-[var(--row-h)]",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </td>
  );
}

/* ---------- Search input (a real field, chapter 17) ---------- */

export function SearchInput({
  placeholder,
  className,
  value,
  onChange,
}: {
  placeholder: string;
  className?: string;
  value?: string;
  onChange?: (value: string) => void;
}) {
  return (
    <label className={cn("relative block", className)}>
      <span className="sr-only">{placeholder}</span>
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="pointer-events-none absolute left-[10px] top-1/2 size-[14px] -translate-y-1/2 text-ink-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.6-3.6" />
      </svg>
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 pl-[30px] pr-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
      />
    </label>
  );
}

/* ---------- Tabs / segmented control (chapter 20) ---------- */

export function Tabs({
  items,
  active,
  onSelect,
  /** Distinguishes concurrently-mounted Tabs so their indicators do not animate into each other. */
  groupId = "tabs",
}: {
  items: string[];
  active: string;
  onSelect?: ((value: string) => void) | undefined;
  groupId?: string | undefined;
}) {
  return (
    <div role="tablist" className="flex h-[36px] items-center gap-sp-6">
      {items.map((item) => {
        const selected = item === active;
        return (
          <button
            key={item}
            role="tab"
            aria-selected={selected}
            onClick={() => onSelect?.(item)}
            className={cn(
              "relative h-[36px] t-ui transition-colors duration-[120ms]",
              selected ? "text-ink-1" : "text-ink-4 hover:text-ink-2",
            )}
          >
            {item}
            {/* layoutId makes the 2px rule TRAVEL between tabs instead of blinking from one to
             * the next. It is the single clearest signal that the two views are siblings. */}
            {selected ? (
              <motion.span
                layoutId={`${groupId}-tab-indicator`}
                className="absolute inset-x-0 -bottom-px block h-[2px] bg-n-12"
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function Segmented({
  items,
  active,
  onSelect,
  className,
  /** Distinguishes concurrently-mounted Segmenteds (a page may host three at once). */
  groupId,
}: {
  items: string[];
  active: string;
  onSelect?: ((value: string) => void) | undefined;
  className?: string | undefined;
  groupId?: string | undefined;
}) {
  // Falls back to the item set, so two Segmenteds with different options never share a thumb.
  const id = groupId ?? items.join("|");

  return (
    <div
      className={cn(
        "inline-flex h-[28px] shrink-0 items-center gap-sp-1 rounded-r-2 border border-stroke-default bg-surface-2 p-[2px]",
        className,
      )}
    >
      {items.map((item) => {
        const selected = item === active;
        return (
          <button
            key={item}
            type="button"
            onClick={() => onSelect?.(item)}
            aria-pressed={selected}
            className={cn(
              "relative h-[22px] whitespace-nowrap rounded-r-1 px-sp-5 t-label transition-colors duration-[120ms]",
              selected ? "text-ink-1" : "text-ink-4 hover:text-ink-2",
            )}
          >
            {/* The thumb slides between options rather than cutting. Same layoutId trick as Tabs;
             * z-ordering keeps the label above the moving fill. */}
            {selected ? (
              <motion.span
                layoutId={`${id}-segmented-thumb`}
                className="absolute inset-0 block rounded-r-1 bg-surface-5"
                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              />
            ) : null}
            <span className="relative z-10">{item}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Checkbox (16px, radius 4) ---------- */

export function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked?: boolean;
  onChange?: (checked: boolean) => void;
}) {
  return (
    <label className="relative inline-flex size-[16px] items-center justify-center">
      <span className="sr-only">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange?.(e.target.checked)}
        className="peer size-[16px] appearance-none rounded-r-1 border border-stroke-strong bg-surface-3 transition-colors duration-[120ms] checked:border-n-12 checked:bg-n-12 hover:border-stroke-ink"
      />
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="pointer-events-none absolute size-[12px] text-n-0 opacity-0 peer-checked:opacity-100"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="m3 8.4 3.2 3.2L13 5" />
      </svg>
    </label>
  );
}

/* ---------- Sparkline ---------- */

/**
 * Compact trend line for a stat card.
 *
 * Hardened against the two inputs that used to produce invalid geometry:
 *  - `values.length < 2` made `step` divide by zero and emitted `points="0,Infinity"`;
 *  - a non-finite value (a null coerced upstream) poisoned the whole polyline.
 * Both now degrade to a flat baseline, which is the honest reading of "not enough data".
 *
 * `muted` renders the line in n-8, matching LineChart's comparison series — used when the card
 * itself is secondary and the sparkline should not compete with the metric above it.
 */
export function Sparkline({
  values,
  className,
  area = true,
  muted = false,
}: {
  values: number[];
  className?: string;
  /** Fills under the curve at 6% — the same wash SeriesChart uses. */
  area?: boolean | undefined;
  muted?: boolean | undefined;
}) {
  const usable = values.filter((value) => Number.isFinite(value));
  const stroke = muted ? "var(--n-8)" : "var(--n-12)";

  // A single reading is not a trend. Draw the baseline rather than nothing, so the card keeps
  // its height and the grid does not reflow when a second point arrives.
  if (usable.length < 2) {
    return (
      <svg
        aria-hidden="true"
        viewBox="0 0 100 28"
        preserveAspectRatio="none"
        className={cn("h-[28px] w-full", className)}
      >
        <line
          x1="0"
          x2="100"
          y1="26"
          y2="26"
          stroke="var(--n-7)"
          strokeWidth="1.5"
          strokeDasharray="3 4"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  const max = Math.max(...usable);
  const min = Math.min(...usable);
  const span = max - min || 1;
  const step = 100 / (usable.length - 1);
  const y = (value: number) => 26 - ((value - min) / span) * 24;

  const points = usable.map((value, index) => `${index * step},${y(value)}`).join(" ");
  const lastY = y(usable[usable.length - 1]!);

  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 100 28"
      preserveAspectRatio="none"
      className={cn("h-[28px] w-full overflow-visible", className)}
    >
      {area ? (
        <polygon points={`0,28 ${points} 100,28`} fill={stroke} fillOpacity={muted ? 0.04 : 0.07} />
      ) : null}
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* Endpoint tick. A rect or circle would be distorted by preserveAspectRatio="none";
       * a non-scaling stroke stays square whatever the card's width. */}
      <line
        x1="99.5"
        x2="100"
        y1={lastY}
        y2={lastY}
        stroke={stroke}
        strokeWidth="4"
        strokeLinecap="square"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/* ---------- Text field (chapter 17 — same field metrics as SearchInput) ---------- */

export function TextField({
  label,
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className={cn("block", className)}>
      <span className="t-micro mb-sp-2 block font-medium text-ink-5">{label}</span>
      <input
        className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
        {...rest}
      />
    </label>
  );
}
