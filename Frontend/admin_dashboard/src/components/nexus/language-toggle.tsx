import { useEffect, useRef, useState } from "react";
import { Languages } from "lucide-react";
import { IconButton } from "@/components/nexus/primitives";
import { updatePreferences, usePreferences } from "@/lib/nexus/preferences";
import { LOCALES, LOCALE_LABEL, LOCALE_SHORT, useTranslation } from "@/lib/nexus/i18n";
import { cn } from "@/lib/utils";

/**
 * Interface language, one click from anywhere — the sibling of <ThemeToggle>.
 *
 * A small menu rather than a cycling button: with three languages a cycle makes reaching the one
 * you want a guessing game, and the current choice is invisible. Each option is written in its
 * OWN language, which is the one label a speaker of that language can always recognise.
 *
 * Settings stays the canonical control; this reads and writes the same preferences store, so the
 * two can never disagree and the pre-paint script still applies `lang`/`dir` on reload.
 */
export function LanguageToggle() {
  const { locale } = usePreferences();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  /* Dismiss on outside click and on Escape — the two ways anyone expects a menu to close. */
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative">
      <IconButton
        label={`${t("shell.language")} — ${LOCALE_LABEL[locale]}`}
        icon={Languages}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      />

      {open ? (
        /* end-0 rather than right-0: in RTL the menu has to hang from the other edge, and the
         * logical property does that without a direction check. */
        <div
          role="menu"
          aria-label={t("shell.language")}
          className="absolute end-0 top-[calc(100%+6px)] z-40 min-w-[168px] overflow-hidden rounded-r-3 border border-stroke-default bg-surface-4 py-sp-2 shadow-elev-3"
        >
          {LOCALES.map((option) => {
            const selected = option === locale;
            return (
              <button
                key={option}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                lang={option}
                dir={option === "ar" ? "rtl" : "ltr"}
                onClick={() => {
                  updatePreferences({ locale: option });
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-sp-4 px-sp-5 py-sp-3 text-start t-ui transition-colors duration-[120ms]",
                  selected
                    ? "bg-surface-5 text-ink-1"
                    : "text-ink-3 hover:bg-surface-5 hover:text-ink-1",
                )}
              >
                <span className="t-mono-s w-[20px] shrink-0 text-ink-4">
                  {LOCALE_SHORT[option]}
                </span>
                <span className="min-w-0 flex-1 truncate">{LOCALE_LABEL[option]}</span>
                {/* A bar, not a tick: the product has no check glyph and this matches the 2px
                 * active-nav indicator. */}
                {selected ? (
                  <span aria-hidden="true" className="block h-[12px] w-[2px] bg-n-12" />
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
