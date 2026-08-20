import { cn } from "@/lib/utils";

/**
 * The product mark.
 *
 * Geometric by construction, per the design bible (chapter 4.6, "no perfect circles"):
 * a terminal caret and a baseline rule, both drawn with square caps on the same 1.8 stroke
 * as the glyph it replaces. Swapping the identity later means editing this one file — the
 * wordmark string lives separately in lib/nexus/brand.ts.
 *
 * The tile is the inverted chip already used elsewhere (bg-n-12 / text-n-0), so the mark
 * introduces no new surface, radius or ink.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "group/mark inline-flex size-[26px] shrink-0 items-center justify-center rounded-r-3 bg-n-12 text-n-0",
        className,
      )}
    >
      <svg viewBox="0 0 16 16" className="size-[13px]" fill="none" aria-hidden="true">
        {/* caret */}
        <path
          d="M3 4.2 L7.2 8 L3 11.8"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
        {/* baseline rule */}
        <path d="M8.8 11.8 H13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square" />
      </svg>
    </span>
  );
}
