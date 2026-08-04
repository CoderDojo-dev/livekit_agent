import { Link, useRouterState } from "@tanstack/react-router";
import { NAV, NAV_SECTIONS, ACCOUNT_FALLBACK, type AccountInfo } from "@/lib/nexus/nav";
import { Avatar, PresenceDot } from "@/components/nexus/primitives";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL, hasRank } from "@/lib/api/session";
import { initials as toInitials } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

const ADMIN_ONLY_HREFS = new Set(["/policies"]);

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { session } = RootRoute.useRouteContext();

  const account: AccountInfo = session
    ? {
        name: session.sub.split("@")[0] ?? session.sub,
        role: ROLE_LABEL[session.role],
        email: session.sub,
        initials: toInitials((session.sub.split("@")[0] ?? "").replace(/[._-]/g, " ")) || "··",
      }
    : ACCOUNT_FALLBACK;

  const canSee = (href: string) =>
    !ADMIN_ONLY_HREFS.has(href) || (session !== null && hasRank(session, "administrateur"));

  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[236px] flex-col border-r border-stroke-default bg-surface-1 lg:flex">
      {/* Brand */}
      <div className="flex h-[60px] shrink-0 items-center gap-sp-5 border-b border-stroke-subtle px-sp-7">
        <span className="inline-flex size-[26px] items-center justify-center rounded-r-3 bg-n-12 text-n-0">
          <svg viewBox="0 0 16 16" className="size-[13px]" aria-hidden="true">
            <path
              d="M3 13V3l10 10V3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="square"
            />
          </svg>
        </span>
        <span className="t-title-3 text-ink-1">Nexus</span>
        <span className="t-mono-s ml-auto text-ink-5">v1.0</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-sp-5 py-sp-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section} className="mb-sp-7 last:mb-0">
            <p className="t-micro-2 mb-sp-4 px-sp-4 text-ink-5">{section}</p>
            <ul className="space-y-[2px]">
              {NAV.filter((item) => item.section === section).map((item) => {
                if (!canSee(item.href)) return null;
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <li key={item.id} className="relative">
                    <Link
                      to={item.href as "/overview"}
                      data-active={active}
                      className={cn(
                        "nav-item group relative flex h-[34px] items-center gap-sp-5 rounded-r-3 px-sp-4 transition-colors duration-[120ms]",
                        active
                          ? "bg-surface-3 text-ink-1"
                          : "text-ink-3 hover:bg-surface-2 hover:text-ink-2",
                      )}
                    >
                      <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
                      <span className="t-ui truncate">{item.label}</span>
                      {item.badge !== undefined ? (
                        item.badgeVariant === "live" ? (
                          <span className="ml-auto inline-flex items-center gap-sp-2">
                            <PresenceDot />
                            <span className="t-mono-s text-ink-3">{item.badge}</span>
                          </span>
                        ) : (
                          <span className="t-mono-s ml-auto inline-flex h-[18px] items-center rounded-r-1 bg-surface-4 px-sp-3 text-ink-2">
                            {item.badge}
                          </span>
                        )
                      ) : (
                        <span className="t-mono-s ml-auto text-ink-5 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100">
                          {item.shortcut}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Account */}
      <div className="shrink-0 border-t border-stroke-subtle p-sp-5">
        <div className="flex items-center gap-sp-5 rounded-r-3 p-sp-4 transition-colors duration-[120ms] hover:bg-surface-2">
          <Avatar initials={account.initials} name={account.name} size="md" />
          <div className="min-w-0">
            <p className="t-ui truncate text-ink-1">{account.name}</p>
            <p className="t-caption truncate text-ink-4">{account.role}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
