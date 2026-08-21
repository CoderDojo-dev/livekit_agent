import { useEffect, useState, type ReactNode } from "react";
import { useRouter, useRouterState } from "@tanstack/react-router";
import { LogOut, PanelLeft } from "lucide-react";
import { PAGE_META, ACCOUNT_FALLBACK, type AccountInfo } from "@/lib/nexus/nav";
import { Avatar, IconButton } from "@/components/nexus/primitives";
import { SidebarContent } from "@/components/nexus/app-sidebar";
import { ThemeToggle } from "@/components/nexus/theme-toggle";
import { LanguageToggle } from "@/components/nexus/language-toggle";
import { useTranslation } from "@/lib/nexus/i18n";
import { RouteProgress } from "@/components/nexus/route-progress";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import { logout } from "@/lib/api/auth.server";
import { initials as toInitials } from "@/lib/nexus/format";
import { BRAND } from "@/lib/nexus/brand";
import { cn } from "@/lib/utils";

export function AppTopbar() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const meta = PAGE_META[pathname];
  const [scrolled, setScrolled] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const router = useRouter();
  const { session } = RootRoute.useRouteContext();
  const { t } = useTranslation();

  const account: AccountInfo = session
    ? {
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
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetTrigger asChild>
          <button
            type="button"
            aria-label={t("shell.openNavigation")}
            className="inline-flex size-9 shrink-0 items-center justify-center rounded-r-3 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          >
            <PanelLeft className="size-4" aria-hidden="true" />
          </button>
        </SheetTrigger>

        <SheetContent side="left" className="w-[min(88vw,320px)] p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
            <SheetDescription>Navigate the {BRAND.name}.</SheetDescription>
          </SheetHeader>

          <SidebarContent className="flex" onNavigate={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="min-w-0">
        <h1 className="t-title-3 truncate text-ink-1">{meta?.title ?? BRAND.shortName}</h1>
        {meta?.subtitle ? (
          <p className="t-caption hidden truncate text-ink-5 sm:block">{meta.subtitle}</p>
        ) : null}
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-sp-4">
        <div className="hidden min-w-0 text-right sm:block">
          <p className="truncate text-sm font-medium text-ink-1">{account.name}</p>
          <p className="t-caption truncate text-ink-5">{account.role}</p>
        </div>

        <Avatar initials={account.initials} size="sm" />

        {/* Separated from the account block: theme is a view setting, sign-out is an account
         * action, and putting a hairline between them stops the two being fired by mistake. */}
        <span aria-hidden="true" className="mx-sp-1 h-[20px] w-px bg-stroke-default" />

        <LanguageToggle />
        <ThemeToggle />
        <IconButton label={t("shell.signOut")} icon={LogOut} onClick={() => void onSignOut()} />
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-0 lg:ps-[236px]">
      <AppTopbar />
      {/* Global loading signal for route transitions and any in-flight query. */}
      <RouteProgress />
      <main className="mx-auto w-full max-w-[1440px] px-sp-8 pb-sp-10 pt-sp-7">{children}</main>
    </div>
  );
}

/**
 * A band of a page.
 *
 * `index` staggers the mount animation. Every section used to carry `.rise` with no delay, so a
 * five-band page performed one synchronised 240ms lurch; a 40ms cascade reads as the page
 * assembling instead. Capped at 4 so a long page never makes the reader wait on its last band,
 * and neutralised entirely by the `prefers-reduced-motion` block in styles.css.
 */
export function PageSection({
  children,
  className,
  index = 0,
}: {
  children: ReactNode;
  className?: string | undefined;
  index?: number | undefined;
}) {
  return (
    <section
      className={cn("rise mb-sp-7 last:mb-0", className)}
      style={{ "--rise-delay": `${Math.min(index, 4) * 40}ms` } as React.CSSProperties}
    >
      {children}
    </section>
  );
}
