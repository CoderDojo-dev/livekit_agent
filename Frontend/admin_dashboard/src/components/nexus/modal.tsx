import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { IconButton } from "@/components/nexus/primitives";
import { AnimatePresence, motion } from "framer-motion";
import { useModalMotion, usePrefersReducedMotion } from "@/lib/nexus/motion-tokens";
import { cn } from "@/lib/utils";

/**
 * Modal shell. No new tokens:
 *  - panel   = Card's class string (primitives.tsx)
 *  - scrim   = AppTopbar's scrim treatment (app-topbar.tsx)
 *  - header  = TableShell toolbar bar, h-[56px] (primitives.tsx)
 *  - footer  = TableShell footer bar, h-[52px] (primitives.tsx)
 *
 * MOTION: the dialog used to fade in via the `.rise` CSS class and then vanish instantly, because
 * `if (!open) return null` tore the subtree out before any transition could run — CSS cannot
 * animate an element that no longer exists. AnimatePresence keeps it mounted for the length of
 * the exit, so closing now mirrors opening. Durations and easing come from useModalMotion(), which
 * collapses to opacity-only under `prefers-reduced-motion`.
 *
 * Focus handling, Escape, scroll lock and the portal rationale are unchanged.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  footer,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const { scrim, panel } = useModalMotion();
  const reduced = usePrefersReducedMotion();

  // AnimatePresence must stay mounted across the close, so the portal can no longer be created
  // lazily behind `if (!open)`. Gate on mount instead: `document` does not exist during SSR.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;

    restoreRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      restoreRef.current?.focus();
    };
  }, [open, onClose]);

  if (!mounted) return null;

  /* Reduced motion takes the ORIGINAL path: no AnimatePresence, so a close unmounts the dialog
   * on the same tick rather than keeping it alive for the length of an exit that will not play
   * anyway. Someone who has asked the OS for less motion should not also inherit its latency. */
  if (reduced && !open) return null;

  // Portal to <body>: `rise` on the wrapping PageSection sets a CSS transform,
  // which would otherwise become the containing block for this fixed overlay
  // and shrink the scrim to the section's box (sidebar stays clickable).
  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          key="scrim"
          {...scrim}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-surface-0/85 px-sp-8 py-sp-12 backdrop-blur-md"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.div
            key="panel"
            ref={panelRef}
            {...panel}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            className={cn(
              "w-full max-w-[520px] overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-4 outline-none",
              className,
            )}
          >
            <div className="flex min-h-[56px] items-start justify-between gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5">
              <div className="min-w-0">
                <h2 className="t-title-3 text-ink-1">{title}</h2>
                {description ? (
                  <p className="t-caption mt-sp-2 max-w-[48ch] text-ink-4">{description}</p>
                ) : null}
              </div>
              <IconButton label="Close" icon={X} onClick={onClose} />
            </div>

            <div className="px-sp-6 py-sp-6">{children}</div>

            {footer ? (
              <div className="flex min-h-[52px] flex-wrap items-center justify-end gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-4">
                {footer}
              </div>
            ) : null}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
