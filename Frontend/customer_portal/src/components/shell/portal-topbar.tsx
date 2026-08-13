import { useState } from "react";
import { useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search, Lock, ChevronDown } from "lucide-react";
import { PAGE_HEAD } from "@/lib/nav";
import { copy } from "@/lib/copy";
import { notifications } from "@/lib/fixtures/customer";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { IconButton, StatusChip } from "@/components/portal/primitives";
import { cn } from "@/lib/utils";

/**
 * components/shell/portal-topbar.tsx — chapitre 12.
 * Titre de page a gauche, assurance et compte a droite.
 */
export function PortalTopbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const base = "/" + pathname.split("/").filter(Boolean)[0];
  const head = PAGE_HEAD[base] ?? { title: "Assistant", subtitle: null };
  const [openTray, setOpenTray] = useState(false);
  const unread = notifications.filter((n) => n.unread).length;
  const profile = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });
  const me = profile.data;
  const initials = me ? `${me.first_name.charAt(0)}${me.last_name.charAt(0)}`.toUpperCase() : "";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-sp-6 border-b border-stroke-subtle bg-surface-0/85 px-sp-8 backdrop-blur-md">
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

      <IconButton label={copy.shell.search}>
        <Search size={16} strokeWidth={1.5} />
      </IconButton>

      <div className="relative">
        <IconButton label={copy.shell.notifications} onClick={() => setOpenTray((v) => !v)}>
          <Bell size={16} strokeWidth={1.5} />
          {unread > 0 && (
            <span className="absolute right-sp-2 top-sp-2 h-1.5 w-1.5 rounded-r-1 bg-n-12" />
          )}
        </IconButton>

        {openTray && (
          <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-4">
            <div className="t-micro border-b border-stroke-subtle px-sp-6 py-sp-5 text-ink-4">
              {copy.shell.notifications}
            </div>
            <ul>
              {notifications.map((n) => (
                <li
                  key={n.id}
                  className="border-b border-stroke-subtle px-sp-6 py-sp-5 last:border-b-0"
                >
                  <div className="flex items-start gap-sp-4">
                    <span
                      className={cn(
                        "mt-sp-4 h-1.5 w-1.5 shrink-0 rounded-r-1",
                        n.unread ? "bg-n-12" : "bg-n-7",
                      )}
                    />
                    <div className="min-w-0">
                      <div className="t-ui text-ink-1">{n.title}</div>
                      <div className="t-caption text-ink-4">{n.detail}</div>
                      <div className="t-mono-s mt-sp-2 text-ink-5">{n.at}</div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <button className="focus-ring ml-sp-2 flex h-9 items-center gap-sp-4 rounded-r-2 border border-stroke-subtle bg-surface-2 pl-sp-3 pr-sp-5 transition-colors duration-200 hover:border-stroke-default">
        <span className="flex h-6 w-6 items-center justify-center rounded-r-1 border border-stroke-strong bg-surface-4">
          <span className="t-micro-2 text-ink-2">{initials}</span>
        </span>
        <span className="t-label hidden text-ink-2 sm:inline">{me?.first_name ?? "Account"}</span>
        <ChevronDown size={14} strokeWidth={1.5} className="text-ink-5" />
      </button>
    </header>
  );
}
