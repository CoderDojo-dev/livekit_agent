import { Link, useRouterState } from "@tanstack/react-router";
import { AudioLines, History, Inbox, Layers2, ReceiptText } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/assistant", label: "Assistant", Icon: AudioLines },
  { href: "/activity", label: "Activity", Icon: History },
  { href: "/requests", label: "Requests", Icon: Inbox },
  { href: "/services", label: "Services", Icon: Layers2 },
  { href: "/billing", label: "Billing", Icon: ReceiptText },
];

/** 11.9 — en dessous de lg, le rail devient une barre basse de cinq entrees. */
export function PortalTabbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      aria-label="Portal"
      className="fixed inset-x-0 bottom-0 z-20 flex h-14 border-t border-stroke-subtle bg-surface-1 lg:hidden"
    >
      {ITEMS.map(({ href, label, Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            to={href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-sp-2 transition-colors duration-200",
              active ? "text-ink-1" : "text-ink-5",
            )}
          >
            <Icon size={17} strokeWidth={1.5} />
            <span className="t-micro-2">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
