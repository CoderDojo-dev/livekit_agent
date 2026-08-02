import * as React from "react";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------------------
 * components/portal/primitives.tsx — le catalogue. Rien hors catalogue.
 * Rayon plafonne a 12px, aucun cercle parfait, aucune couleur.
 * ------------------------------------------------------------------------- */

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "quiet" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "focus-ring inline-flex items-center justify-center gap-sp-4 whitespace-nowrap rounded-r-2 border transition-colors duration-200 disabled:pointer-events-none disabled:opacity-40",
        size === "sm" && "t-label h-7 px-sp-5",
        size === "md" && "t-ui h-9 px-sp-6",
        size === "lg" && "t-ui h-11 px-sp-8",
        variant === "primary" &&
          "border-transparent bg-n-12 text-ink-inverse hover:bg-n-11 active:bg-n-10",
        variant === "secondary" &&
          "border-stroke-default bg-surface-3 text-ink-1 shadow-elev-1 hover:border-stroke-strong hover:bg-surface-4",
        variant === "ghost" &&
          "border-transparent text-ink-3 hover:bg-surface-3 hover:text-ink-1",
        variant === "quiet" &&
          "border-stroke-subtle bg-transparent text-ink-3 hover:border-stroke-default hover:text-ink-1",
        variant === "danger" &&
          "border-stroke-strong border-dashed bg-transparent text-ink-2 hover:bg-surface-3 hover:text-ink-1",
        className,
      )}
      {...props}
    />
  );
}

export function IconButton({
  className,
  label,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cn(
        "focus-ring inline-flex h-8 w-8 items-center justify-center rounded-r-2 border border-transparent text-ink-3 transition-colors duration-200 hover:border-stroke-default hover:bg-surface-3 hover:text-ink-1",
        className,
      )}
      {...props}
    />
  );
}

export function Card({
  className,
  inset = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-r-5 border border-stroke-default bg-surface-1 shadow-elev-1",
        inset && "p-sp-8",
        className,
      )}
      {...props}
    />
  );
}

export function SectionLabel({
  children,
  className,
  right,
}: {
  children: React.ReactNode;
  className?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-sp-6", className)}>
      <h2 className="t-micro text-ink-4">{children}</h2>
      {right}
    </div>
  );
}

/** 22.4 — le statut se lit par la forme, jamais par la teinte. */
export type ChipTone = "solid" | "outline" | "dashed" | "dotted" | "muted";

export function StatusChip({
  children,
  tone = "outline",
  className,
}: {
  children: React.ReactNode;
  tone?: ChipTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "t-micro-2 inline-flex h-6 items-center gap-sp-3 rounded-r-1 border px-sp-4",
        tone === "solid" && "border-transparent bg-n-12 text-ink-inverse",
        tone === "outline" && "border-stroke-ink bg-transparent text-ink-2",
        tone === "dashed" && "border-dashed border-stroke-strong bg-transparent text-ink-2",
        tone === "dotted" && "border-dotted border-stroke-strong bg-transparent text-ink-3",
        tone === "muted" && "border-stroke-subtle bg-surface-3 text-ink-4",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-stroke-subtle", className)} />;
}

export function FieldRow({
  label,
  value,
  hint,
  action,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  action?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-sp-6 py-sp-6">
      <div className="min-w-0">
        <div className="t-label text-ink-4">{label}</div>
        <div className={cn("mt-sp-2 text-ink-1", mono ? "t-mono-l" : "t-body-strong")}>
          {value}
        </div>
        {hint ? <div className="t-caption mt-sp-2 text-ink-5">{hint}</div> : null}
      </div>
      {action ? <div className="shrink-0 pt-sp-3">{action}</div> : null}
    </div>
  );
}

export function SwitchRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-sp-8 py-sp-6">
      <div className="min-w-0">
        <div className="t-body-strong text-ink-1">{label}</div>
        <div className="t-caption mt-sp-2 max-w-xl text-ink-4">{description}</div>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "focus-ring relative mt-sp-2 h-6 w-11 shrink-0 rounded-r-1 border transition-colors duration-200",
          checked ? "border-transparent bg-n-12" : "border-stroke-strong bg-surface-3",
        )}
      >
        <span
          className={cn(
            "absolute top-sp-1 h-4 w-4 rounded-r-1 transition-all duration-200",
            checked ? "left-6 bg-n-0" : "left-sp-1 bg-n-8",
          )}
        />
      </button>
    </div>
  );
}

/** 38.4 — au-dela de la limite, la barre se hachure. */
export function Meter({
  label,
  used,
  limit,
  unit,
}: {
  label: string;
  used: number;
  limit: number;
  unit: string;
}) {
  const over = used > limit;
  const pct = Math.min(100, Math.round((used / limit) * 100));
  return (
    <div className="py-sp-5">
      <div className="flex items-baseline justify-between gap-sp-5">
        <span className="t-ui text-ink-2">{label}</span>
        <span className="t-mono text-ink-3">
          {used} / {limit} {unit === "%" ? "" : unit}
        </span>
      </div>
      <div className="mt-sp-4 h-2 w-full overflow-hidden rounded-r-1 border border-stroke-subtle bg-surface-3">
        <div
          className={cn("h-full bg-n-11", over && "hatch-45 bg-n-12")}
          style={{ width: `${pct}%` }}
        />
      </div>
      {over ? (
        <div className="t-caption mt-sp-3 text-ink-3">
          Over your monthly allowance. Extra blocks are billed at £6.00 each.
        </div>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-r-5 border border-dashed border-stroke-default px-sp-8 py-sp-12 text-center">
      <div className="h-10 w-10 rounded-r-3 border border-stroke-strong bg-surface-2 shadow-elev-1" />
      <h3 className="t-title-3 mt-sp-7 text-ink-1">{title}</h3>
      <p className="t-body mt-sp-3 max-w-sm text-ink-4">{body}</p>
      {action ? <div className="mt-sp-7">{action}</div> : null}
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: readonly { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex items-center gap-sp-1 rounded-r-2 border border-stroke-subtle bg-surface-2 p-sp-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          aria-pressed={value === t.id}
          className={cn(
            "focus-ring t-label h-7 rounded-r-1 px-sp-5 transition-colors duration-200",
            value === t.id
              ? "bg-surface-4 text-ink-1 shadow-elev-1"
              : "text-ink-4 hover:text-ink-2",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function SearchField({
  placeholder,
  value,
  onChange,
  className,
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <input
      type="search"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "focus-ring t-ui-regular h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5",
        className,
      )}
    />
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-r-2 border border-stroke-default">
      {options.map((o, i) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={cn(
            "t-label h-8 px-sp-6 transition-colors duration-200",
            i > 0 && "border-l border-stroke-default",
            value === o
              ? "bg-n-12 text-ink-inverse"
              : "bg-surface-2 text-ink-3 hover:bg-surface-3 hover:text-ink-1",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}
