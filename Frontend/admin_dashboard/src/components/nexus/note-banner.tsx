import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A provenance note — where this page's data comes from, and what it therefore does NOT include.
 *
 * These paragraphs are load-bearing in this product (see the `never let this read as "all GLPI
 * tickets"` comments), so they cannot be deleted. But rendered as a bare run of caption text
 * spanning the full width of a card, they read as small print nobody finishes.
 *
 * Framing them gives the eye somewhere to start and somewhere to stop: an icon anchors the block,
 * an inset surface separates it from the metrics above, and the measure is capped so the lines
 * stay short enough to actually read.
 */
export function NoteBanner({
  children,
  className,
  icon: Icon = Info,
}: {
  children: ReactNode;
  className?: string | undefined;
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number }> | undefined;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-sp-5 rounded-r-3 border border-stroke-subtle bg-surface-1 px-sp-6 py-sp-5",
        className,
      )}
    >
      <span className="mt-[1px] shrink-0 text-ink-5" aria-hidden="true">
        <Icon size={14} strokeWidth={1.5} />
      </span>
      <p className="t-caption max-w-[92ch] text-ink-4">{children}</p>
    </div>
  );
}
