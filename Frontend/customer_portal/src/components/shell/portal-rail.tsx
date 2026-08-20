import { Link, useRouterState } from "@tanstack/react-router";
import { BrandMark } from "@/components/shell/brand-mark";
import {
  AudioLines,
  History,
  Inbox,
  Layers2,
  ReceiptText,
  LifeBuoy,
  UserRound,
  SlidersHorizontal,
  Shield,
  Info,
  PanelLeft,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { brand, copy } from "@/lib/copy";
import { CountBadge } from "@/components/portal/primitives";
import { useNavCounts } from "@/hooks/use-nav-counts";
import { cn } from "@/lib/utils";

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

/**
 * components/shell/portal-rail.tsx — chapitre 11.
 * Dix destinations, trois groupes, un pied de marque.
 */
export function PortalRail({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const counts = useNavCounts();

  return (
    <nav
      aria-label="Portal"
      className={cn(
        "fixed inset-y-0 left-0 z-20 hidden shrink-0 flex-col border-r border-stroke-subtle bg-surface-1 transition-[width] duration-300 lg:flex",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div className="flex h-16 items-center gap-sp-5 border-b border-stroke-subtle px-sp-6">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-r-2 border border-stroke-strong bg-surface-4 text-ink-1 shadow-elev-1">
          <BrandMark />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="t-title-3 truncate text-ink-1">{brand.name}</div>
            <div className="t-micro-2 truncate text-ink-5">{brand.version}</div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-sp-4 py-sp-7">
        {NAV.map((group) => (
          <div key={group.section} className="mb-sp-8 last:mb-0">
            {!collapsed && (
              <div className="t-micro-2 px-sp-4 pb-sp-4 text-ink-5">{group.section}</div>
            )}
            <ul className="space-y-sp-1">
              {group.items.map((item) => {
                const Icon = ICONS[item.icon] ?? Info;
                const active = pathname.startsWith(item.href);
                // null while the count is still unknown: rendering 0 would
                // state something false about the account.
                const count = counts[item.href] ?? null;
                return (
                  <li key={item.href}>
                    <Link
                      to={item.href}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "focus-ring group relative flex h-9 items-center gap-sp-5 rounded-r-2 px-sp-4 transition-colors duration-200",
                        active
                          ? "bg-surface-3 text-ink-1"
                          : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "absolute left-0 top-sp-3 h-3 w-px bg-n-12 transition-opacity duration-200",
                          active ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <Icon size={16} strokeWidth={1.5} className="shrink-0" />
                      {!collapsed && <span className="t-ui truncate">{item.label}</span>}
                      {!collapsed && (
                        <span className="ml-auto flex shrink-0 items-center gap-sp-4">
                          {/* The shortcut sits BEFORE the badge and only fades
                              in, so it never displaces the count: it holds its
                              width at rest and nothing on the row moves on
                              hover. */}
                          <span className="t-mono-s text-ink-5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                            {item.key}
                          </span>
                          {count !== null && count > 0 ? (
                            <CountBadge count={count} tone={active ? "strong" : "muted"} />
                          ) : null}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-stroke-subtle p-sp-4">
        <button
          onClick={onToggle}
          className="focus-ring flex h-9 w-full items-center gap-sp-5 rounded-r-2 px-sp-4 text-ink-4 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-2"
        >
          <PanelLeft size={16} strokeWidth={1.5} className="shrink-0" />
          {!collapsed && <span className="t-label">{copy.shell.collapseRail}</span>}
        </button>
      </div>
    </nav>
  );
}
