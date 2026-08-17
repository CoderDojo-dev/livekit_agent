import { Link, useRouterState } from "@tanstack/react-router";
import { NAV, NAV_SECTIONS, ACCOUNT_FALLBACK, canSeeNavItem, type AccountInfo } from "@/lib/nexus/nav";
import { Avatar, PresenceDot } from "@/components/nexus/primitives";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import { initials as toInitials } from "@/lib/nexus/format";
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

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-sp-5 py-sp-6">
        {NAV_SECTIONS.map((section) => {
          const items = NAV.filter((item) => item.section === section && canSeeNavItem(item, session));

          if (items.length === 0) return null;

          return (
            <div key={section} className="mb-sp-7 last:mb-0">
              <p className="t-micro mb-sp-3 px-sp-3 text-ink-5">{section}</p>

              <div className="space-y-sp-1">
                {items.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;

                  return (
                    <Link
                      key={item.id}
                      to={item.href as "/overview"}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group flex min-h-9 items-center gap-sp-4 rounded-r-3 px-sp-3 text-sm transition-colors",
                        active
                          ? "bg-surface-3 font-medium text-ink-1"
                          : "text-ink-4 hover:bg-surface-2 hover:text-ink-1",
                      )}
                    >
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      <span
                        aria-hidden="true"
                        className="t-mono-s text-ink-6 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                      >
                        {item.shortcut}
                      </span>
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
