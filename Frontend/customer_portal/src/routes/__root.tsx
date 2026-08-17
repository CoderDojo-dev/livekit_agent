import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type CSSProperties, type ReactNode } from "react";
import { Toaster } from "sonner";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Button, Card } from "@/components/portal/primitives";
import { copy } from "@/lib/copy";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px] text-center">
        <div className="t-mono-l text-ink-4">404</div>
        <h1 className="t-title-2 mt-sp-5 text-ink-1">{copy.errors.notFoundTitle}</h1>
        <p className="t-body mt-sp-3 text-ink-4">{copy.errors.notFoundBody}</p>
        <div className="mt-sp-8">
          <Link to="/">
            <Button variant="primary">{copy.errors.goHome}</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px] text-center">
        <h1 className="t-title-2 text-ink-1">{copy.errors.brokenTitle}</h1>
        <p className="t-body mt-sp-3 text-ink-4">{copy.errors.brokenBody}</p>
        <div className="mt-sp-8 flex justify-center gap-sp-4">
          <Button
            variant="primary"
            onClick={() => {
              router.invalidate();
              reset();
            }}
          >
            {copy.common.tryAgain}
          </Button>
          <a href="/">
            <Button variant="quiet">{copy.errors.goHome}</Button>
          </a>
        </div>
      </Card>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Nexus Customer Portal" },
      {
        name: "description",
        content:
          "A monochrome customer portal for Nexus voice support: talk to the assistant, track requests, and manage your account.",
      },
      { name: "author", content: "Nexus" },
      { property: "og:title", content: "Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Private voice support that respects your time.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@Nexus" },
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

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
      <Toaster
        position="bottom-right"
        // Token-aligned: sonner draws with these CSS variables, so no hex value
        // enters the codebase and the toast inherits surface/stroke/ink exactly.
        style={
          {
            "--normal-bg": "var(--surface-2)",
            "--normal-text": "var(--ink-1)",
            "--normal-border": "var(--stroke-default)",
          } as CSSProperties
        }
        toastOptions={{ className: "t-ui rounded-r-3 shadow-elev-3" }}
      />
    </QueryClientProvider>
  );
}
