import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A provenance note — where this page's data comes from, and what it therefore does NOT include.
 *
 * These sentences are load-bearing in this product (see the `never let this read as "all GLPI
 * tickets"` comments), so they cannot be deleted. The question is only how to carry them.
 *
 * They were briefly boxed in a filled, bordered panel. That was wrong: a filled rectangle reads
 * as an ALERT — it implies something needs attention — and stacking one under every metric strip
 * added a second competing surface inside a card that is already a surface. Nothing here is
 * urgent; it is a footnote.
 *
 * So this is a margin note instead: a hairline rule in the margin, a small-caps eyebrow, and the
 * text at a short measure. No fill, no border box, no second background. The rule is the same
 * 2px stroke the active-nav indicator uses, which is the vocabulary the bible already has for
 * "this belongs to what is beside it".
 */
export function NoteBanner({
  children,
  className,
  label = "Source",
}: {
  children: ReactNode;
  className?: string | undefined;
  /** The eyebrow. "Source" fits provenance; override for anything else. */
  label?: string | undefined;
}) {
  return (
    <div className={cn("flex gap-sp-6 border-l-2 border-stroke-strong pl-sp-6", className)}>
      <div className="min-w-0">
        <p className="t-micro text-ink-5">{label}</p>
        {/* 78ch keeps the line short enough to actually finish reading. */}
        <p className="t-caption mt-sp-3 max-w-[78ch] text-ink-4">{children}</p>
      </div>
    </div>
  );
}
