import { useIsFetching } from "@tanstack/react-query";
import { useRouterState } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { usePrefersReducedMotion } from "@/lib/nexus/motion-tokens";

/**
 * The global loading bar — ported from the customer portal's TopProgress so both frontends
 * signal work the same way.
 *
 * A 2px line pinned directly under the sticky topbar (h-[60px] here, vs the portal's h-16).
 * Indeterminate on purpose: neither a route transition nor a react-query fetch can report a
 * percentage, and a bar that invents one is a lie about progress.
 *
 * It watches TWO sources, because either can leave the user waiting:
 *  - the router, while a route's beforeLoad/loader resolves;
 *  - react-query, whenever any query in the app is in flight.
 *
 * z-index sits below the topbar (z-30) so it tucks under the header rather than crossing it.
 */
export function RouteProgress() {
  const reduced = usePrefersReducedMotion();

  const routerBusy = useRouterState({ select: (state) => state.status === "pending" });
  const queriesBusy = useIsFetching() > 0;
  const active = routerBusy || queriesBusy;

  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="route-progress"
          className="pointer-events-none fixed inset-x-0 top-[60px] z-20 h-[2px] overflow-hidden lg:left-[236px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          aria-hidden="true"
        >
          <motion.div
            className="h-[2px] w-1/3 bg-ink-3"
            initial={{ x: "-100%" }}
            /* Reduced motion still shows the bar — it just stops travelling, so the signal
             * survives without the movement. */
            animate={reduced ? { x: "0%" } : { x: ["-100%", "300%"] }}
            transition={
              reduced ? { duration: 0.12 } : { duration: 0.9, ease: "linear", repeat: Infinity }
            }
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
