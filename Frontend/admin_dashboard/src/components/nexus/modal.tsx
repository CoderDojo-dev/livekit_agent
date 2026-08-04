import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { IconButton } from "@/components/nexus/primitives";
import { cn } from "@/lib/utils";

/**
 * Modal shell. No new tokens:
 *  - panel   = Card's class string (primitives.tsx)
 *  - scrim   = AppTopbar's scrim treatment (app-topbar.tsx)
 *  - header  = TableShell toolbar bar, h-[56px] (primitives.tsx)
 *  - footer  = TableShell footer bar, h-[52px] (primitives.tsx)
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

  if (!open) return null;

  // Portal to <body>: `rise` on the wrapping PageSection sets a CSS transform,
  // which would otherwise become the containing block for this fixed overlay
  // and shrink the scrim to the section's box (sidebar stays clickable).
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-surface-0/85 px-sp-8 py-sp-12 backdrop-blur-md"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "rise w-full max-w-[520px] overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1 outline-none",
          className,
        )}
      >
        <div className="flex min-h-[56px] items-start justify-between gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5">
          <div>
            <h2 className="t-title-3 text-ink-1">{title}</h2>
            {description ? (
              <p className="t-caption mt-sp-2 max-w-[48ch] text-ink-4">{description}</p>
            ) : null}
          </div>
          <IconButton label="Close" icon={X} onClick={onClose} />
        </div>

        <div className="px-sp-6 py-sp-6">{children}</div>

        {footer ? (
          <div className="flex h-[52px] items-center justify-end gap-sp-4 border-t border-stroke-subtle px-sp-6">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
