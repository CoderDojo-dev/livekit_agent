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
  return (
    <nav
      aria-label="Portal"
      className="fixed inset-x-0 bottom-0 z-20 flex h-14 border-t border-stroke-subtle bg-surface-1 lg:hidden"
    >
      {ITEMS.map((item) => {
        const Icon = ICONS[item.icon] ?? Info;
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            to={item.href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-sp-2 transition-colors duration-200",
              active ? "text-ink-1" : "text-ink-5",
            )}
          >
            <Icon size={17} strokeWidth={1.5} />
            <span className="t-micro-2">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
