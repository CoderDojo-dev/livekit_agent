/**
 * Inline SVG so the mark inherits currentColor and needs no network request.
 * Achromatic on purpose: the whole portal is greyscale, and the orb is the only
 * light source in the design.
 */
export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 19V5l14 14V5"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
