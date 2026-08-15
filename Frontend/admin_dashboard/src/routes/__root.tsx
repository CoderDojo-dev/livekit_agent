import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { AlertTriangle, SearchX } from "lucide-react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { AppSidebar } from "@/components/nexus/app-sidebar";
import { AppShell } from "@/components/nexus/app-topbar";
import { Card, Button } from "@/components/nexus/primitives";
import { redirect, useRouterState } from "@tanstack/react-router";
import { getSession, type SessionView } from "@/lib/api/auth.server";

function NotFoundComponent() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px]">
        <div className="flex flex-col items-center py-sp-8 text-center">
          <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
            <SearchX size={18} strokeWidth={1.5} />
          </span>
          <p className="t-title-3 text-ink-1">Page not found</p>
          <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">
            The page you're looking for doesn't exist or has been moved.
          </p>
          <Button
            variant="primary"
            size="sm"
            className="mt-sp-6"
            onClick={() => void router.navigate({ to: "/overview" })}
          >
            Go to overview
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  const router = useRouter();

  useEffect(() => {
    console.error(error);
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px]">
        <div className="flex flex-col items-center py-sp-8 text-center">
          <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
            <AlertTriangle size={18} strokeWidth={1.5} />
          </span>
          <p className="t-title-3 text-ink-1">This page didn't load</p>
          <p className="t-caption mt-sp-2 max-w-[40ch] text-ink-4">
            Something went wrong on our end. You can try again or head back to the overview.
          </p>
          <div className="mt-sp-6 flex gap-sp-4">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                void router.invalidate().finally(reset);
              }}
            >
              Try again
            </Button>
            <Button size="sm" onClick={() => void router.navigate({ to: "/overview" })}>
              Go to overview
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient;
  session: SessionView | null;
}>()({
  // UX gate only. The security boundary is authedMiddleware on each server function
  // (see src/lib/api/middleware.ts).
  beforeLoad: async ({ location }) => {
    const session = await getSession();
    if (!session && location.pathname !== "/login") {
      throw redirect({ to: "/login" });
    }
    if (session && location.pathname === "/login") {
      throw redirect({ to: "/overview" });
    }
    return { session };
  },
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Nexus — Monochrome Admin Console" },
      {
        name: "description",
        content:
          "Nexus is an achromatic admin console for AI-assisted customer support: calls, tickets, conversations and analytics.",
      },
      { name: "author", content: "Nexus" },
      { property: "og:title", content: "Nexus — Monochrome Admin Console" },
      {
        property: "og:description",
        content: "AI-assisted support operations in a strictly monochrome interface.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap",
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),

  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  // The login screen is full-bleed: no sidebar, no topbar.
  if (pathname === "/login") {
    return (
      <QueryClientProvider client={queryClient}>
        <Outlet />
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AppSidebar />
      <AppShell>
        {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
        <Outlet />
      </AppShell>
    </QueryClientProvider>
  );
}
