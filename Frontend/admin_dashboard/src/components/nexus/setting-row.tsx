import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * One labelled setting: description on the left, control on the right.
 *
 * A settings page is a list of decisions, and the thing that makes one readable is that every row
 * has the same shape — you learn the pattern once and then only read the words that change. Rows
 * stack on narrow screens rather than crushing the control against the text.
 */
export function SettingRow({
  title,
  description,
  control,
  className,
}: {
  title: string;
  description: string;
  control: ReactNode;
  className?: string | undefined;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-sp-4 border-t border-stroke-subtle py-sp-6 first:border-t-0 first:pt-0 last:pb-0",
        "sm:flex-row sm:items-center sm:justify-between sm:gap-sp-8",
        className,
      )}
    >
      <div className="min-w-0">
        <p className="t-body-strong text-ink-1">{title}</p>
        <p className="t-caption mt-sp-2 max-w-[62ch] text-ink-4">{description}</p>
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  );
}

/**
 * A two-state control for a boolean setting.
 *
 * Built from Segmented's metrics rather than a switch: the product has no toggle primitive, and
 * naming both states ("On" / "Off") is less ambiguous than a slider whose meaning depends on
 * which end is lit — particularly in a monochrome interface with no accent colour to lean on.
 */
export function SettingToggle({
  value,
  onChange,
  labels = ["On", "Off"],
  name,
}: {
  value: boolean;
  onChange: (next: boolean) => void;
  labels?: [string, string];
  /** Distinguishes this control from its neighbours for assistive tech. */
  name: string;
}) {
  return (
    <div
      role="group"
      aria-label={name}
      className="inline-flex h-[28px] items-center gap-sp-1 rounded-r-2 border border-stroke-default bg-surface-2 p-[2px]"
    >
      {([true, false] as const).map((state, index) => {
        const selected = value === state;
        return (
          <button
            key={String(state)}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(state)}
            className={cn(
              "h-[22px] min-w-[46px] rounded-r-1 px-sp-5 t-label transition-colors duration-[120ms]",
              selected ? "bg-surface-5 text-ink-1" : "text-ink-4 hover:text-ink-2",
            )}
          >
            {labels[index]}
          </button>
        );
      })}
    </div>
  );
}
