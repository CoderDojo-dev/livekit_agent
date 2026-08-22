/**
 * components/shell/brand-mark.tsx — the mark in the rail's header.
 *
 * A PERSON, not a monogram. The previous mark was an angular "N" left over from
 * the pre-rebrand release: it said nothing about what this product is, and it
 * said it in a letter the product is no longer named after. This is a self-care
 * portal — the whole surface is one customer's own account — so the mark is the
 * customer.
 *
 * Drawn rather than imported from lucide for two reasons: it must inherit
 * `currentColor` so the rail's ink level carries it in both themes, and the
 * proportions here are the portal's own. The head is deliberately small and the
 * shoulders wide and shallow, which keeps both shapes legible at the 18px the
 * rail renders it at — a lucide `User` at this size closes its shoulder arc into
 * a smudge.
 *
 * Achromatic by construction, like everything else: no fill of its own, one
 * stroke weight, no gradient.
 */
export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      {/* The head. */}
      <circle cx="12" cy="8.25" r="3.5" stroke="currentColor" strokeWidth={1.6} />
      {/* The shoulders: an arc, not a closed capsule, so the mark reads as a
          drawing of a person rather than as a filled avatar chip. */}
      <path
        d="M4.75 19.25c0-3.45 3.25-5.75 7.25-5.75s7.25 2.3 7.25 5.75"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
    </svg>
  );
}
