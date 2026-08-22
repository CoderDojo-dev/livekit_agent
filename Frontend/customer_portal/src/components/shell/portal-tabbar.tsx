import { Link, useRouterState } from "@tanstack/react-router";
import {
  AudioLines,
  History,
  Inbox,
  Layers2,
  ReceiptText,
  Info,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { useNavCounts } from "@/hooks/use-nav-counts";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  "audio-lines": AudioLines,
  history: History,
  inbox: Inbox,
  "layers-2": Layers2,
  "receipt-text": ReceiptText,
};

/** 11.9 — en dessous de lg, le rail devient une barre basse de cinq entrees.
 *  Une seule source de verite : NAV. Renommer ou retirer une destination ne
 *  peut plus laisser un lien mort ici. */
const MOBILE_HREFS = ["/assistant", "/activity", "/requests", "/services", "/billing"] as const;

const ITEMS = MOBILE_HREFS.map((href) => {
  const item = NAV.flatMap((group) => group.items).find((i) => i.href === href);
  return item ?? null;
}).filter((item): item is NonNullable<typeof item> => item !== null);

export function PortalTabbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const counts = useNavCounts();
  return (
    <nav
      aria-label="Portal"
      className="fixed inset-x-0 bottom-0 z-20 flex h-14 border-t border-stroke-subtle bg-surface-1/90 backdrop-blur-md lg:hidden"
    >
      {ITEMS.map((item) => {
        const Icon = ICONS[item.icon] ?? Info;
        const active = pathname.startsWith(item.href);
        const count = counts[item.href] ?? null;
        return (
          <Link
            key={item.href}
            to={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "focus-ring relative flex flex-1 flex-col items-center justify-center gap-sp-2 transition-colors duration-200 active:scale-[0.97]",
              active ? "text-ink-1" : "text-ink-5",
            )}
          >
            {/* The bar's only mark of position was the ink level of the label,
                which at t-micro-2 is a 10px difference in grey. A 2px rule on
                the leading edge of the cell is the same device the rail and the
                settings nav use, at the size a 56px bar can carry. */}
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-x-sp-7 top-0 h-0.5 rounded-b-r-1 bg-n-12 transition-opacity duration-200",
                active ? "opacity-100" : "opacity-0",
              )}
            />
            {/* A 14px bar has no room for a pill, so the count becomes a
                superscript on the icon - the same fact, at the size the bar
                can carry. */}
            <span className="relative">
              <Icon size={17} strokeWidth={1.5} />
              {count !== null && count > 0 ? (
                <span
                  aria-hidden="true"
                  className="t-micro-2 absolute -right-sp-5 -top-sp-2 tabular-nums text-ink-4"
                >
                  {count}
                </span>
              ) : null}
            </span>
            <span className="t-micro-2">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
