import { Outlet, createFileRoute, redirect, useRouterState } from "@tanstack/react-router";
import { useIsFetching } from "@tanstack/react-query";
import { PortalShell } from "@/components/shell/portal-shell";
import { TabPanel, TopProgress } from "@/components/portal/data";
import { getSession } from "@/lib/api/auth.server";

export const Route = createFileRoute("/_portal")({
  // UX gate only. The security boundary is authedMiddleware on each server function
  // (see src/lib/api/middleware.ts).
  beforeLoad: async ({ location }) => {
    const session = await getSession();
    if (!session) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
    // The cookie carries the bearer expiry. business-api revalidates the
    // session row on every request anyway, so a locally expired cookie can
    // only produce a shell full of 401s. Bounce it here instead.
    if (session.exp * 1000 <= Date.now()) {
      throw redirect({ to: "/logout", search: { reason: "expired" } });
    }
    return { session };
  },
  component: PortalLayout,
});

function PortalLayout() {
  const navigating = useRouterState({ select: (s) => s.status === "pending" });
  const fetching = useIsFetching() > 0;
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <PortalShell>
      <TopProgress active={navigating || fetching} />
      <TabPanel id={pathname}>
        <Outlet />
      </TabPanel>
    </PortalShell>
  );
}
