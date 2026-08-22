import { useRouterState } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  History,
  Inbox,
  Info,
  Layers2,
  LifeBuoy,
  Lock,
  ReceiptText,
  Shield,
  SlidersHorizontal,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { NAV, PAGE_HEAD } from "@/lib/nav";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchNotifications } from "@/lib/api/notifications.server";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { AccountMenu } from "@/components/shell/account-menu";
import { NotificationTray } from "@/components/shell/notification-tray";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { IconFrame, StatusChip } from "@/components/portal/primitives";

/**
 * components/shell/portal-topbar.tsx — chapitre 12.
 * Titre de page a gauche, assurance et compte a droite.
 */

/**
 * The same ten glyphs the rail uses, keyed by the same `icon` strings from
 * lib/nav.ts — so the mark beside the page title is provably the mark next to
 * the highlighted rail row, and adding a destination cannot leave the two
 * disagreeing.
 */
const ICONS: Record<string, LucideIcon> = {
  "audio-lines": AudioLines,
  history: History,
  inbox: Inbox,
  "layers-2": Layers2,
  "receipt-text": ReceiptText,
  "life-buoy": LifeBuoy,
  "user-round": UserRound,
  "sliders-horizontal": SlidersHorizontal,
  shield: Shield,
  info: Info,
};

const NAV_ITEMS = NAV.flatMap((group) => group.items);

export function PortalTopbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const base = "/" + pathname.split("/").filter(Boolean)[0];
  const head = PAGE_HEAD[base] ?? { title: "Assistant", subtitle: null };
  const item = NAV_ITEMS.find((entry) => entry.href === base);
  const Icon = item ? (ICONS[item.icon] ?? Info) : Info;

  const session = usePortalSession();
  const profile = useQuery({
    queryKey: qk.profileDetail(session?.customerId ?? "unknown"),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });
  const notifications = useQuery({
    queryKey: qk.notifications(session?.customerId ?? "unknown", 20, 0),
    queryFn: () => fetchNotifications({ data: { limit: 20, offset: 0 } }),
    staleTime: 30_000,
  });
  const me = profile.data;
  const items = notifications.data?.items ?? [];

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-sp-5 border-b border-stroke-subtle bg-surface-0/85 px-sp-8 backdrop-blur-md">
      {/* The bar carried a title and a subtitle and nothing else on the left,
          which on a 1440px screen is two lines of text floating in a great
          deal of nothing. The destination's own glyph anchors them, and it is
          hidden below sm where the width is genuinely scarce. */}
      <IconFrame icon={Icon} tone="strong" className="hidden sm:inline-flex" />

      <div className="min-w-0 flex-1">
        <h1 className="t-title-2 truncate text-ink-1">{head.title}</h1>
        {head.subtitle ? <p className="t-caption truncate text-ink-4">{head.subtitle}</p> : null}
      </div>

      <div className="hidden items-center gap-sp-4 md:flex">
        <StatusChip tone="muted">
          <Lock size={10} strokeWidth={1.5} />
          {copy.shell.secure}
        </StatusChip>
      </div>

      <ThemeToggle />

      <NotificationTray items={items} />

      <AccountMenu name={me?.full_name ?? "Account"} email={me?.email ?? ""} />
    </header>
  );
}
