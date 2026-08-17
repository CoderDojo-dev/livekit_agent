import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";
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
  return (
    <PortalShell>
      {/* Required: nested routes render here. */}
      <Outlet />
    </PortalShell>
  );
}
