import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  NAV,
  NAV_SECTIONS,
  ACCOUNT_FALLBACK,
  canSeeNavItem,
  type AccountInfo,
} from "@/lib/nexus/nav";
import { Avatar, NavBadge, PresenceDot } from "@/components/nexus/primitives";
import { BrandMark } from "@/components/nexus/brand-mark";
import { CountSwap } from "@/components/nexus/motion";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import { initials as toInitials } from "@/lib/nexus/format";
import { BRAND } from "@/lib/nexus/brand";
import { getNavCounts } from "@/lib/api/nav-counts.server";
import { navKeys } from "@/lib/nexus/query-keys";
import { cn } from "@/lib/utils";

type SidebarContentProps = {
  className?: string;
  onNavigate?: () => void;
};

export function SidebarContent({ className, onNavigate }: SidebarContentProps) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const { session } = RootRoute.useRouteContext();

  /**
   * Live queue counts. One request for all three badges (see nav-counts.server.ts).
   *
   * `staleTime` keeps navigation between pages from refetching; `refetchInterval` keeps a rail
   * that stays mounted for hours from going quietly stale. Both are conservative on purpose —
   * a badge is ambient information, not a live ticker, and it must never compete for bandwidth
   * with the page the user is actually reading.
   */
  const counts = useQuery({
    queryKey: navKeys.counts(),
    queryFn: () => getNavCounts(),
    enabled: session !== null,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    // A failed badge fetch must never surface an error state in the navigation rail.
    retry: 1,
  });

  const account: AccountInfo = session
    ? {
        name: session.sub.split("@")[0] ?? session.sub,
        role: ROLE_LABEL[session.role],
        email: session.sub,
        initials: toInitials((session.sub.split("@")[0] ?? "").replace(/[._-]/g, " ")) || "··",
      }
    : ACCOUNT_FALLBACK;

  return (
    <aside className={cn("h-full flex-col border-r border-stroke-default bg-surface-1", className)}>
      <div className="flex h-[60px] shrink-0 items-center gap-sp-5 border-b border-stroke-subtle px-sp-7">
        <BrandMark />
        <span className="t-title-3 truncate text-ink-1">{BRAND.shortName}</span>
        <span className="t-mono-s ml-auto shrink-0 text-ink-5">{BRAND.version}</span>
      </div>

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-sp-5 py-sp-6">
        {NAV_SECTIONS.map((section) => {
          const items = NAV.filter(
            (item) => item.section === section && canSeeNavItem(item, session),
          );

          if (items.length === 0) return null;

          return (
            <div key={section} className="mb-sp-7 last:mb-0">
              <p className="t-micro mb-sp-3 px-sp-3 text-ink-5">{section}</p>

              <div className="space-y-sp-1">
                {items.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;

                  /* null (not permitted, or the upstream did not answer) renders NO badge.
                   * Zero renders one: "0 open escalations" is a useful, earned fact, whereas a
                   * badge we could not compute must not be shown as if it were zero. */
                  const count = item.countKey ? (counts.data?.[item.countKey] ?? null) : null;

                  return (
                    <Link
                      key={item.id}
                      to={item.href as "/overview"}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      /* `nav-item` + data-active activate the 2px rail defined in styles.css.
                       * That rule shipped with the design bible but no element ever carried the
                       * class, so the active state was carried by a 4-value background step
                       * alone. `relative` gives the ::before pseudo-element its origin. */
                      className={cn(
                        "nav-item group relative flex min-h-9 items-center gap-sp-4 rounded-r-3 px-sp-3 text-sm",
                        "transition-[background-color,color] duration-[120ms]",
                        active
                          ? "bg-surface-3 font-medium text-ink-1"
                          : "text-ink-4 hover:bg-surface-2 hover:text-ink-1",
                      )}
                      data-active={active ? "true" : "false"}
                    >
                      <Icon
                        className={cn(
                          "size-4 shrink-0 transition-colors duration-[120ms]",
                          active ? "text-ink-1" : "text-ink-5 group-hover:text-ink-2",
                        )}
                        aria-hidden="true"
                      />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>

                      {count !== null ? (
                        <NavBadge
                          count={count}
                          attention={item.countAttention === true && count > 0}
                        >
                          <CountSwap value={count > 999 ? "999+" : count} />
                        </NavBadge>
                      ) : (
                        /* The shortcut hint only occupies the trailing slot when no badge does.
                         * A badge and a hint fighting for the same 40px was the reason counts
                         * had nowhere to go. */
                        <span
                          aria-hidden="true"
                          className="t-mono-s text-ink-5 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 group-focus-visible:opacity-100"
                        >
                          {item.shortcut}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="flex shrink-0 items-center gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-5">
        <div className="relative shrink-0">
          <Avatar initials={account.initials} size="sm" />
          <PresenceDot live className="absolute -bottom-px -right-px" />
        </div>

        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink-1">{account.name}</p>
          <p className="t-caption truncate text-ink-5">{account.role}</p>
        </div>
      </div>
    </aside>
  );
}

export function AppSidebar() {
  return <SidebarContent className="fixed inset-y-0 left-0 z-20 hidden w-[236px] lg:flex" />;
}
