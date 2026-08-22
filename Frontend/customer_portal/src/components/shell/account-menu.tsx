import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, LogOut, Shield, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * The topbar identity button was inert (no onClick), so the portal had no way
 * out. This is the only sign-out affordance; it routes to /logout, which is the
 * only place that calls the logout server function.
 */
export function AccountMenu({ name, email }: { name: string; email: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const initials =
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "—";

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("shell.account")}
        onClick={() => setOpen((value) => !value)}
        className="focus-ring flex h-9 items-center gap-sp-4 rounded-r-2 px-sp-3 text-ink-3 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
      >
        <span className="t-mono-s flex h-7 w-7 items-center justify-center rounded-r-2 border border-stroke-default bg-surface-3 text-ink-2">
          {initials}
        </span>
        <span className="t-ui hidden max-w-[160px] truncate md:block">{name}</span>
        <ChevronDown
          size={14}
          strokeWidth={1.5}
          className={cn("transition-transform duration-200", open && "rotate-180")}
        />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -4, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.985 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="absolute end-0 top-11 z-30 w-64 overflow-hidden rounded-r-3 border border-stroke-default bg-surface-2 shadow-elev-3"
          >
            <div className="border-b border-stroke-subtle px-sp-6 py-sp-5">
              <div className="t-body-strong truncate text-ink-1">{name}</div>
              <div className="t-caption truncate text-ink-4">{email}</div>
            </div>
            <div className="p-sp-2">
              <MenuLink
                to="/profile"
                icon={UserRound}
                label={t("shell.menu.profile")}
                onDone={() => setOpen(false)}
              />
              <MenuLink
                to="/security"
                icon={Shield}
                label={t("shell.menu.security")}
                onDone={() => setOpen(false)}
              />
            </div>
            <div className="border-t border-stroke-subtle p-sp-2">
              <MenuLink
                to="/logout"
                search={{ reason: "manual" as const }}
                icon={LogOut}
                label={t("shell.signOut")}
                onDone={() => setOpen(false)}
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function MenuLink({
  to,
  search,
  icon: Icon,
  label,
  onDone,
}: {
  to: string;
  search?: Record<string, string>;
  icon: typeof UserRound;
  label: string;
  onDone: () => void;
}) {
  return (
    <Link
      to={to}
      {...(search === undefined ? {} : { search })}
      role="menuitem"
      onClick={onDone}
      className="focus-ring t-ui flex h-9 items-center gap-sp-5 rounded-r-2 px-sp-4 text-ink-3 transition-colors duration-200 hover:bg-surface-3 hover:text-ink-1"
    >
      <Icon size={15} strokeWidth={1.5} />
      {label}
    </Link>
  );
}
