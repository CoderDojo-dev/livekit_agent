/**
 * Product identity — the ONE place the console is named.
 *
 * Everything user-visible that says the product's name reads it from here: the sidebar wordmark,
 * the topbar fallback title, and every route's <title> / og:title. Renaming the product is a
 * one-line edit to `name` below.
 *
 * The mark itself lives in <BrandMark /> (components/nexus/brand-mark.tsx) so the glyph and the
 * string can be swapped independently.
 */
export const BRAND = {
  /** Full product name. Appears in the sidebar and in every document title. */
  name: "Admin Dashboard",
  /** Compact form for the sidebar wordmark and the topbar fallback, where width is scarce. */
  shortName: "Admin",
  /** Rendered as the muted mono chip beside the wordmark. */
  version: "v1.0",
} as const;

/** `pageTitle("Overview")` -> "Overview — Admin Dashboard". Used by every route's head(). */
export function pageTitle(page: string): string {
  return `${page} — ${BRAND.name}`;
}
