import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { isForbidden, isUnauthenticated } from "./lib/api/errors";
import type { AdminSession } from "./lib/api/session";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Supervision data is near-real-time but not live; 30 s avoids hammering business-api
        // while keeping the console usefully fresh.
        staleTime: 30_000,
        retry: (failureCount, error) => {
          // Never retry an auth verdict — it will not change without user action.
          if (isUnauthenticated(error) || isForbidden(error)) return false;
          return failureCount < 2;
        },
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient, session: null as AdminSession | null },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};

// Standard TanStack Router type registration. Without it useRouteContext() and useRouterState()
// fall back to AnyRouter/any on the templates' generated route tree, so root-context consumers
// lose session typing. Type-level only — no runtime effect.
declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof getRouter>;
  }
}
