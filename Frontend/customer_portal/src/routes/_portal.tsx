import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";
import { getSession } from "@/lib/api/auth.server";

export const Route = createFileRoute("/_portal")({
  // UX gate only. The security boundary is authedMiddleware on each server function
  // (see src/lib/api/middleware.ts).
  beforeLoad: async () => {
    const session = await getSession();
    if (!session) {
      throw redirect({ to: "/login" });
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
