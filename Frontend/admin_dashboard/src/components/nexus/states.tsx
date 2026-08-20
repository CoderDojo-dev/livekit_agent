import { AlertTriangle, Lock, WifiOff, type LucideIcon } from "lucide-react";
import { Button, Card, Td } from "@/components/nexus/primitives";
import { errorMessage, isForbidden, isUnauthenticated } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

/* ---------- Loading ---------- */

/**
 * One shimmering cell. Uses surface-4 (the same fill as Avatar) — no new token.
 *
 * The sweep runs left-to-right (`.shimmer` in styles.css) instead of the old symmetric
 * `animate-pulse`: a directional wipe reads as "content is arriving", whereas a fade in and out
 * reads as "something is wrong here".
 */
export function Shimmer({ className }: { className?: string | undefined }) {
  return (
    <span aria-hidden="true" className={cn("shimmer block h-[10px] rounded-r-1", className)} />
  );
}

/**
 * Indeterminate 2px bar for regions that have no TableShell to host one (charts, panels, master
 * lists). Absolutely positioned by the caller so that appearing never shifts layout.
 */
export function TopProgress({ active, className }: { active: boolean; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "pointer-events-none block h-[2px] overflow-hidden transition-opacity duration-[120ms]",
        active ? "opacity-100" : "opacity-0",
        className,
      )}
    >
      {active ? <span className="progress-sweep block h-full w-full bg-n-11" /> : null}
    </span>
  );
}

/**
 * Skeleton for master lists (calls, escalations) — the row shape those pages actually render,
 * so the layout does not jump when data lands.
 */
export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" className="divide-y divide-stroke-subtle">
      <span className="sr-only">Loading</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="flex items-center gap-sp-5 px-sp-6 py-sp-5">
          <Shimmer className="size-[32px] shrink-0 rounded-r-3" />
          <div className="min-w-0 flex-1 space-y-sp-3">
            <Shimmer className="w-[55%]" />
            <Shimmer className="h-[8px] w-[35%]" />
          </div>
          <Shimmer className="h-[8px] w-[48px] shrink-0" />
        </div>
      ))}
    </div>
  );
}

/**
 * Row-level skeleton for <TableShell>. Column count must match the header so the
 * layout does not jump when real data lands.
 */
export function TableSkeleton({ columns, rows = 6 }: { columns: number; rows?: number }) {
  const widths = ["w-[60%]", "w-[35%]", "w-[45%]", "w-[30%]", "w-[50%]", "w-[40%]"];
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} aria-hidden="true">
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <Td key={columnIndex}>
              <Shimmer className={widths[columnIndex % widths.length]} />
            </Td>
          ))}
        </tr>
      ))}
      <tr className="sr-only">
        <td colSpan={columns} role="status">
          Loading
        </td>
      </tr>
    </>
  );
}

/** Block skeleton for card/chart regions. */
export function CardSkeleton({
  lines = 4,
  className,
}: {
  lines?: number;
  className?: string | undefined;
}) {
  return (
    <Card {...(className === undefined ? {} : { className })}>
      <div role="status" className="flex flex-col gap-sp-5">
        <span className="sr-only">Loading</span>
        <Shimmer className="h-[14px] w-[40%]" />
        {Array.from({ length: lines }).map((_, index) => (
          <Shimmer key={index} className={index % 2 === 0 ? "w-[85%]" : "w-[65%]"} />
        ))}
      </div>
    </Card>
  );
}

/* ---------- Error ---------- */

/**
 * Structural twin of EmptyState (primitives.tsx, chapter 24) with a retry affordance.
 * Identical spacing, radii, type ramp and icon frame — only the icon and the button differ.
 */
export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: (() => void) | undefined;
  title?: string;
}) {
  const forbidden = isForbidden(error);
  const expired = isUnauthenticated(error);

  const Icon: LucideIcon = forbidden ? Lock : expired ? Lock : WifiOff;
  const heading =
    title ?? (forbidden ? "Access denied" : expired ? "Session expired" : "Could not load");

  return (
    <div className="flex h-full flex-col items-center justify-center px-sp-8 py-sp-12 text-center">
      <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
        <Icon size={18} strokeWidth={1.5} />
      </span>
      <p className="t-title-3 text-ink-1">{heading}</p>
      <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">{errorMessage(error)}</p>
      {onRetry && !forbidden && !expired ? (
        <Button variant="secondary" size="sm" className="mt-sp-6" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
      {expired ? (
        <Button
          variant="primary"
          size="sm"
          className="mt-sp-6"
          onClick={() => window.location.assign("/login")}
        >
          Sign in
        </Button>
      ) : null}
    </div>
  );
}

/** Error state sized to sit inside a <TableShell> body. */
export function TableErrorRow({
  columns,
  error,
  onRetry,
}: {
  columns: number;
  error: unknown;
  onRetry?: (() => void) | undefined;
}) {
  return (
    <tr>
      <td colSpan={columns} className="border-b border-stroke-subtle">
        <ErrorState error={error} onRetry={onRetry} />
      </td>
    </tr>
  );
}

/** Inline banner for non-blocking failures (e.g. a background refetch failed). */
export function InlineError({ error }: { error: unknown }) {
  return (
    <span className="inline-flex items-center gap-sp-2 t-caption text-ink-3">
      <AlertTriangle size={12} strokeWidth={1.5} aria-hidden="true" />
      {errorMessage(error)}
    </span>
  );
}
