import { useState } from "react";
import { useRouterState } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { Bell, Lock } from "lucide-react";
import { PAGE_HEAD } from "@/lib/nav";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchNotifications, type NotificationItem } from "@/lib/api/notifications.server";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { relative } from "@/lib/format";
import { AccountMenu } from "@/components/shell/account-menu";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { IconButton, StatusChip } from "@/components/portal/primitives";

/**
 * components/shell/portal-topbar.tsx — chapitre 12.
 * Titre de page a gauche, assurance et compte a droite.
 */
function notificationMessage(item: NotificationItem): string {
  const template = item.template_code
    ? copy.notificationTemplates[item.template_code as keyof typeof copy.notificationTemplates]
    : undefined;
  return template ?? copy.notifications.genericMessage;
}

export function PortalTopbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const base = "/" + pathname.split("/").filter(Boolean)[0];
  const head = PAGE_HEAD[base] ?? { title: "Assistant", subtitle: null };
  const [openTray, setOpenTray] = useState(false);
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

      <ThemeToggle />

      <div className="relative">
        <IconButton label={copy.shell.notifications} onClick={() => setOpenTray((v) => !v)}>
          <Bell size={16} strokeWidth={1.5} />
        </IconButton>

        {openTray && (
          <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-4">
            <div className="t-micro border-b border-stroke-subtle px-sp-6 py-sp-5 text-ink-4">
              {copy.notifications.heading}
            </div>
            {items.length === 0 ? (
              <p className="t-caption px-sp-6 py-sp-6 text-ink-4">
                {copy.shell.notificationsEmpty}
              </p>
            ) : (
              <ul>
                {items.map((n, i) => (
                  <li
                    key={`${n.created_at}-${i}`}
                    className="border-b border-stroke-subtle px-sp-6 py-sp-5 last:border-b-0"
                  >
                    <div className="flex items-start gap-sp-4">
                      <div className="min-w-0">
                        <div className="t-ui text-ink-1">{notificationMessage(n)}</div>
                        <div className="t-caption mt-sp-1 text-ink-4">
                          {copy.labels.notificationChannel[
                            n.channel as keyof typeof copy.labels.notificationChannel
                          ] ?? n.channel}{" "}
                          ·{" "}
                          {copy.labels.notificationStatus[
                            n.status as keyof typeof copy.labels.notificationStatus
                          ] ?? n.status}
                        </div>
                        <div className="t-mono-s mt-sp-2 text-ink-5">
                          {relative(n.sent_at ?? n.created_at)}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <AccountMenu name={me?.full_name ?? "Account"} email={me?.email ?? ""} />
    </header>
  );
}
