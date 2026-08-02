import { Outlet, createFileRoute } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";

export const Route = createFileRoute("/_portal")({
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
