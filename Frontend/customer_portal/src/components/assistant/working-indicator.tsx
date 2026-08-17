import { AnimatePresence, motion } from "motion/react";
import { T_BASE } from "@/components/portal/data";
import { copy } from "@/lib/copy";

/**
 * Shown while agent.state === "thinking".
 *
 * The wording is intentionally generic ("Checking this for you…") because at
 * this moment the portal genuinely does not know which tool is running: tool
 * events only arrive once execution has finished. Naming a specific check here
 * would be a guess.
 *
 * Three dots on the existing shimmer rhythm; no spinner, which does not exist
 * anywhere in this design system.
 */
export function WorkingIndicator({ active }: { active: boolean }) {
  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="working"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={T_BASE}
          className="flex items-center gap-sp-4 rounded-r-4 border border-stroke-subtle bg-surface-2 px-sp-6 py-sp-5"
          role="status"
        >
          <span className="flex items-center gap-sp-2" aria-hidden="true">
            {[0, 1, 2].map((index) => (
              <motion.span
                key={index}
                className="h-1 w-1 rounded-full bg-ink-3"
                animate={{ opacity: [0.25, 1, 0.25] }}
                transition={{
                  duration: 1.1,
                  ease: "easeInOut",
                  repeat: Infinity,
                  delay: index * 0.16,
                }}
              />
            ))}
          </span>
          <span className="t-ui text-ink-3">{copy.assistant.tools.working}</span>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
