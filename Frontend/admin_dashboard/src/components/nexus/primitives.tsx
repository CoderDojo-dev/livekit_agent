import { type ReactNode } from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { STATUS } from "@/lib/nexus/status";
import { cn } from "@/lib/utils";
import { formatDelta } from "@/lib/nexus/format";

/* ---------- Card (chapter 19) ---------- */

export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1",
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
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-sp-5">
      <div>
        <h2 className="t-title-3 text-ink-1">{title}</h2>
        {subtitle ? (
          <p className="t-caption mt-sp-2 max-w-[48ch] text-ink-4">
            {subtitle}
          </p>
        ) : null}
      </div>
      {action}
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
}: {
  children: ReactNode;
  strong?: boolean;
  mono?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-[20px] items-center rounded-r-1 px-sp-3",
        mono ? "t-mono-s" : "t-label",
        strong ? "bg-surface-5 text-ink-1" : "bg-surface-4 text-ink-2",
        className,
      )}
    >
      {children}
    </span>
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

export function StatusChip({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const def = STATUS[status];
  if (!def) return null;
  const inverted = def.container === "inverted";
  const tone = inverted ? "var(--n-0)" : (LEVEL_TONE[def.level] ?? "var(--n-8)");

  return (
    <span
      className={cn(
        "inline-flex h-[22px] items-center gap-sp-2 rounded-r-2 px-sp-4",
        def.container === "soft" && "bg-surface-4 text-ink-2",
        def.container === "outline" &&
          "border border-stroke-strong text-ink-2",
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

export function PriorityMeter({
  priority,
}: {
  priority: "high" | "medium" | "low";
}) {
  const tones =
    priority === "high"
      ? ["var(--n-12)", "var(--n-12)", "var(--n-12)"]
      : priority === "medium"
        ? ["var(--n-11)", "var(--n-11)", "var(--n-7)"]
        : ["var(--n-10)", "var(--n-7)", "var(--n-7)"];
  const label =
    priority === "high" ? "High" : priority === "medium" ? "Medium" : "Low";

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

export function PresenceDot({
  live = true,
  className,
}: {
  live?: boolean;
  className?: string;
}) {
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
        "inline-flex shrink-0 items-center justify-center gap-sp-4 whitespace-nowrap transition-colors duration-[120ms]",
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
        "inline-flex shrink-0 items-center justify-center rounded-r-3 text-ink-3 transition-colors duration-[120ms] hover:bg-surface-3 hover:text-ink-1",
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
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  title: string;
  description: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-sp-8 py-sp-12 text-center">
      <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
        <Icon size={18} strokeWidth={1.5} />
      </span>
      <p className="t-title-3 text-ink-1">{title}</p>
      <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">{description}</p>
    </div>
  );
}

/* ---------- Table shell (chapter 21) ---------- */

export function TableShell({
  toolbar,
  head,
  children,
  footer,
}: {
  toolbar?: ReactNode;
  head: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1">
      {toolbar ? (
        <div className="flex h-[56px] items-center gap-sp-5 border-b border-stroke-subtle px-sp-6">
          {toolbar}
        </div>
      ) : null}
      <table className="w-full border-collapse">
        <thead>{head}</thead>
        <tbody>{children}</tbody>
      </table>
      {footer ? (
        <div className="flex h-[52px] items-center justify-between border-t border-stroke-subtle px-sp-6">
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
}: {
  children?: ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}) {
  return (
    <td
      className={cn(
        "h-[52px] border-b border-stroke-subtle px-sp-6 t-ui text-ink-2",
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
}: {
  placeholder: string;
  className?: string;
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
}: {
  items: string[];
  active: string;
  onSelect?: (value: string) => void;
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
            {selected ? (
              <span className="absolute inset-x-0 -bottom-px block h-[2px] bg-n-12" />
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
}: {
  items: string[];
  active: string;
  onSelect?: (value: string) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex h-[28px] items-center gap-sp-1 rounded-r-2 border border-stroke-default bg-surface-2 p-[2px]",
        className,
      )}
    >
      {items.map((item) => {
        const selected = item === active;
        return (
          <button
            key={item}
            onClick={() => onSelect?.(item)}
            aria-pressed={selected}
            className={cn(
              "h-[22px] rounded-r-1 px-sp-5 t-label transition-colors duration-[120ms]",
              selected
                ? "bg-surface-5 text-ink-1"
                : "text-ink-4 hover:text-ink-2",
            )}
          >
            {item}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Checkbox (16px, radius 4) ---------- */

export function Checkbox({ label }: { label: string }) {
  return (
    <label className="relative inline-flex size-[16px] items-center justify-center">
      <span className="sr-only">{label}</span>
      <input
        type="checkbox"
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

export function Sparkline({
  values,
  className,
}: {
  values: number[];
  className?: string;
}) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const step = 100 / (values.length - 1);
  const points = values
    .map((v, i) => `${i * step},${28 - ((v - min) / (max - min || 1)) * 26}`)
    .join(" ");
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 100 28"
      preserveAspectRatio="none"
      className={cn("h-[28px] w-full", className)}
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--n-12)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
