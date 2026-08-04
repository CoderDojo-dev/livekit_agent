import { useEffect, useState, type ReactNode } from "react";
import { useRouter, useRouterState } from "@tanstack/react-router";
import { Bell, PanelLeft, Command, LogOut } from "lucide-react";
import { PAGE_META, ACCOUNT_FALLBACK, type AccountInfo } from "@/lib/nexus/nav";
import { Avatar, IconButton, SearchInput } from "@/components/nexus/primitives";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import { logout } from "@/lib/api/auth.server";
import { initials as toInitials } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

export function AppTopbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const meta = PAGE_META[pathname];
  const [scrolled, setScrolled] = useState(false);

  const router = useRouter();
  const { session } = RootRoute.useRouteContext();

  const account: AccountInfo = session
    ? {
        // No display-name field exists on the session; the local part of the email is the
        // closest honest label. See §8.1 — a real user record would supply a full name.
        name: session.sub.split("@")[0] ?? session.sub,
        role: ROLE_LABEL[session.role],
        email: session.sub,
        initials: toInitials((session.sub.split("@")[0] ?? "").replace(/[._-]/g, " ")) || "··",
      }
    : ACCOUNT_FALLBACK;

  async function onSignOut() {
    await logout();
    await router.invalidate();
    await router.navigate({ to: "/login" });
  }

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-[60px] items-center gap-sp-6 bg-surface-0/85 px-sp-8 backdrop-blur-md transition-colors duration-[120ms]",
        scrolled ? "border-b border-stroke-default" : "border-b border-transparent",
      )}
    >
      <IconButton label="Toggle navigation" icon={PanelLeft} className="lg:hidden" />
      <div className="min-w-0">
        <h1 className="t-title-3 truncate text-ink-1">{meta?.title ?? "Nexus"}</h1>
        <p className="t-caption hidden truncate text-ink-4 sm:block">{meta?.subtitle ?? ""}</p>
      </div>
      <div className="ml-auto flex items-center gap-sp-5">
        <SearchInput placeholder="Search" className="hidden w-[220px] md:block" />
        <span className="t-mono-s hidden h-[22px] items-center gap-sp-2 rounded-r-1 border border-stroke-default px-sp-3 text-ink-4 xl:inline-flex">
          <Command size={11} strokeWidth={1.5} aria-hidden="true" />K
        </span>
        <IconButton label="Notifications" icon={Bell} />
        <span className="hidden flex-col items-end leading-tight md:flex">
          <span className="t-label text-ink-2">{account.name}</span>
          <span className="t-micro text-ink-4">{account.role}</span>
        </span>
        <Avatar initials={account.initials} name={account.name} size="sm" />
        <IconButton label="Sign out" icon={LogOut} onClick={onSignOut} />
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-0 lg:pl-[236px]">
      <AppTopbar />
      <main className="mx-auto w-full max-w-[1440px] px-sp-8 pb-sp-12 pt-sp-8">{children}</main>
    </div>
  );
}

export function PageSection({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("rise mb-sp-8 last:mb-0", className)}>{children}</section>;
}
