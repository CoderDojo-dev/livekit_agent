import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { DURATION, EASE_OUT, usePrefersReducedMotion } from "@/lib/nexus/motion-tokens";

/**
 * House motion components.
 *
 * Division of labour, deliberately:
 *  - CSS owns everything that only needs to play once on mount or on :hover. It is free, it
 *    never blocks hydration, and `@media (prefers-reduced-motion)` in styles.css already
 *    neutralises it globally.
 *  - framer-motion owns what CSS provably cannot: EXIT animations (an element already removed
 *    from the tree cannot be transitioned by CSS), presence-swapped content, and height:auto.
 *
 * Both halves share the same two easing curves and the same duration ladder, so a modal closing
 * and a table paging feel like the same product.
 *
 * REDUCED MOTION: framer-motion animates inline styles, which the CSS media query in styles.css
 * cannot reach. Every component here therefore calls `usePrefersReducedMotion()` and collapses to
 * an opacity-only (or instant) transition. Never remove those guards.
 *
 * This file exports components only — the curves, durations and hooks live in
 * lib/nexus/motion-tokens.ts so react-refresh can hot-reload these.
 */

/* ---------------------------------------------------------------------------------------------
 * Paginated content
 * ------------------------------------------------------------------------------------------- */

/**
 * Cross-fades one page of rows into the next.
 *
 * `mode="popLayout"` lets the outgoing page leave without the incoming page waiting for it, so
 * paging feels immediate rather than sequential. The direction of travel tilts the slide by a few
 * pixels — enough to read as "forward" or "back" without becoming a carousel.
 */
export function PageSwap({
  pageKey,
  direction = 0,
  children,
  className,
}: {
  /** Changes whenever the visible window changes. Usually the page index. */
  pageKey: string | number;
  /** +1 forward, -1 back, 0 no directional hint. */
  direction?: number | undefined;
  children: ReactNode;
  className?: string | undefined;
}) {
  const reduced = usePrefersReducedMotion();
  const offset = reduced ? 0 : direction * 6;

  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div
        key={pageKey}
        className={className}
        initial={{ opacity: 0, x: offset }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -offset }}
        transition={{ duration: reduced ? 0 : DURATION.base, ease: EASE_OUT }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/**
 * Table-body variant of <PageSwap>.
 *
 * HTML forbids a <div> between <table> and <tr>, so the animated element must itself be the
 * <tbody>. `motion.tbody` keeps the DOM valid while still giving us an exit animation.
 * `mode="wait"` rather than popLayout: two overlapping tbodies would briefly double the table's
 * height and shove the pager down the page.
 */
export function TableBodySwap({
  pageKey,
  children,
}: {
  pageKey: string | number;
  children: ReactNode;
}) {
  const reduced = usePrefersReducedMotion();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.tbody
        key={pageKey}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: reduced ? 0 : DURATION.fast, ease: EASE_OUT }}
      >
        {children}
      </motion.tbody>
    </AnimatePresence>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Disclosure
 * ------------------------------------------------------------------------------------------- */

/**
 * Height-animated reveal for accordions (policies, reference).
 *
 * `height: auto` is animatable by framer-motion because it measures the element first — this is
 * the one thing that makes an accordion feel built rather than assembled, and it is precisely
 * what plain CSS cannot do without a hard-coded max-height that then clips long content.
 */
export function Reveal({ open, children }: { open: boolean; children: ReactNode }) {
  const reduced = usePrefersReducedMotion();

  return (
    <AnimatePresence initial={false}>
      {open ? (
        <motion.div
          key="content"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{
            height: { duration: reduced ? 0 : DURATION.reveal, ease: EASE_OUT },
            opacity: { duration: reduced ? 0 : DURATION.fast, ease: EASE_OUT },
          }}
          style={{ overflow: "hidden" }}
        >
          {children}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Numeric badges
 * ------------------------------------------------------------------------------------------- */

/**
 * Swaps a count without the layout jolt of a plain text replacement. Used by the sidebar badges,
 * where a number changing under the cursor should be noticed but not startling.
 */
export function CountSwap({
  value,
  className,
}: {
  value: number | string;
  className?: string | undefined;
}) {
  const reduced = usePrefersReducedMotion();

  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.span
        key={String(value)}
        className={className}
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduced ? { opacity: 0 } : { opacity: 0, y: 4 }}
        transition={{ duration: reduced ? 0 : DURATION.fast, ease: EASE_OUT }}
      >
        {value}
      </motion.span>
    </AnimatePresence>
  );
}
