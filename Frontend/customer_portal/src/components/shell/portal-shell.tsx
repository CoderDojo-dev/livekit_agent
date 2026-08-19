import { useState, type ReactNode } from "react";
import { PortalRail } from "./portal-rail";
import { PortalTopbar } from "./portal-topbar";
import { PortalTabbar } from "./portal-tabbar";
import { cn } from "@/lib/utils";

/**
 * components/shell/portal-shell.tsx — chapitre 10.
 * Rail fixe, barre superieure collante, une seule zone de defilement.
 */
export function PortalShell({ children, scene = false }: { children: ReactNode; scene?: boolean }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-surface-0">
      <PortalRail collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <PortalTabbar />
      <div
        className={cn(
          "flex flex-col transition-[padding] duration-300",
          scene ? "h-screen overflow-hidden" : "min-h-screen",
          collapsed ? "lg:pl-16" : "lg:pl-64",
        )}
      >
        <PortalTopbar />
        <main
          className={cn(
            "flex-1",
            scene
              ? "flex min-h-0 flex-col overflow-hidden px-sp-8 py-sp-7"
              : "mx-auto w-full max-w-6xl px-sp-8 py-sp-9 pb-20 lg:pb-sp-12",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
