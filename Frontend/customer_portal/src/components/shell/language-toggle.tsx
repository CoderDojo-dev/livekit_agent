import { useEffect, useRef, useState } from "react";
import { Languages } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { IconButton } from "@/components/portal/primitives";
import { updatePreferences, usePreferences } from "@/lib/preferences";
import { LOCALES, LOCALE_LABEL, LOCALE_SHORT, useTranslation } from "@/lib/i18n";
import { usePortalReducedMotion } from "@/hooks/use-portal-motion";
import { cn } from "@/lib/utils";

/**
 * components/shell/language-toggle.tsx — the interface language, one click from anywhere.
 *
 * The sibling of <ThemeToggle>, and the portal's port of the admin console's control, so a person
 * who uses both products finds the same thing in the same corner.
 *
 * A MENU, NOT A CYCLING BUTTON. With three languages a cycle turns reaching the one you want into
 * a guessing game, and it never shows which one is current. Each option is written in its OWN
 * language, which is the single label a speaker of that language can always recognise even when
 * the rest of the interface is in a script they cannot read — the whole point of the control.
 *
 * Preferences stays the canonical place to set this; both read and write the same store, so the
 * two can never disagree and the pre-paint script still applies lang/dir on reload.
 *
 * NOT THE ASSISTANT'S LANGUAGE. This changes the screen. What the assistant SPEAKS is
 * crm.customers.preferred_language, set under Preferences → Language, and it deliberately is not
 * touched here: a customer who reads French but wants to be spoken to in Arabic is an ordinary
 * case in Tunisia, not an edge one.
 */
export function LanguageToggle() {
  const { locale } = usePreferences();
  const { t } = useTranslation();
  const reduce = usePortalReducedMotion();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  /* Dismiss on outside click and on Escape — the two ways anyone expects a menu to close. */
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
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

  return (
    <div ref={wrapperRef} className="relative">
      <IconButton
        label={`${t("shell.language")} — ${LOCALE_LABEL[locale]}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <Languages size={16} strokeWidth={1.5} />
      </IconButton>

      <AnimatePresence>
        {open ? (
          /* end-0 rather than right-0: under dir="rtl" the menu has to hang from the other edge,
             and the logical property does that without a direction check anywhere in the tree. */
          <motion.div
            role="menu"
            aria-label={t("shell.language")}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.985 }}
            transition={reduce ? { duration: 0 } : { duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="absolute end-0 top-11 z-50 min-w-[176px] overflow-hidden rounded-r-3 border border-stroke-default bg-surface-2 py-sp-2 shadow-elev-4"
          >
            {LOCALES.map((option) => {
              const selected = option === locale;
              return (
                <button
                  key={option}
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  // Each row declares its own language and direction, so the browser shapes the
                  // Arabic label correctly even while the page around it is still in English.
                  lang={option}
                  dir={option === "ar" ? "rtl" : "ltr"}
                  onClick={() => {
                    updatePreferences({ locale: option });
                    setOpen(false);
                  }}
                  className={cn(
                    "t-ui flex w-full items-center gap-sp-5 px-sp-5 py-sp-3 text-start transition-colors duration-200",
                    selected
                      ? "bg-surface-3 text-ink-1"
                      : "text-ink-3 hover:bg-surface-3 hover:text-ink-1",
                  )}
                >
                  <span className="t-mono-s w-[22px] shrink-0 text-ink-5">
                    {LOCALE_SHORT[option]}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{LOCALE_LABEL[option]}</span>
                  {/* A bar, not a tick: the portal has no check glyph, and this is the same 2px
                      mark the rail uses for the active destination. */}
                  {selected ? (
                    <span aria-hidden="true" className="block h-3 w-0.5 rounded-r-1 bg-n-12" />
                  ) : null}
                </button>
              );
            })}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
