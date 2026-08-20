import { cn } from "@/lib/utils";

/**
 * The product mark — an authority badge.
 *
 * Reads as "admin": a shield silhouette, which is the universal shorthand for privilege and
 * oversight, with a chevron struck through it for verification. That is what this console does —
 * it is the place decisions are reviewed and vouched for.
 *
 * Geometric by construction, per the design bible (chapter 4.6, "no perfect circles"): the shield
 * is six straight segments, never an arc, and the chevron is two. Both are drawn on the same 1.7
 * stroke weight and miter joins as the rest of the iconography.
 *
 * The tile is the inverted chip already used elsewhere (bg-n-12 / text-n-0), so the mark
 * introduces no new surface, radius or ink — and it inverts correctly in the light theme for
 * free, because both values are theme tokens.
 *
 * Swapping the identity later means editing this one file; the wordmark string lives separately
 * in lib/nexus/brand.ts.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-[26px] shrink-0 items-center justify-center rounded-r-3 bg-n-12 text-n-0",
        className,
      )}
    >
      <svg viewBox="0 0 16 16" className="size-[14px]" fill="none" aria-hidden="true">
        {/* Shield: flat shoulders, angled flanks, pointed base. Six segments, zero curves. */}
        <path
          d="M8 1.7 L13.4 4.1 L13.4 8.3 L8 14.3 L2.6 8.3 L2.6 4.1 Z"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinejoin="miter"
        />
        {/* Verification chevron. */}
        <path
          d="M5.5 7.9 L7.2 9.6 L10.6 6.2"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="square"
          strokeLinejoin="miter"
        />
      </svg>
    </span>
  );
}
