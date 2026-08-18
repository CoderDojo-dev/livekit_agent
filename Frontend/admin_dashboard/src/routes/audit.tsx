import { createFileRoute, redirect } from "@tanstack/react-router";
import { AuditPage } from "@/components/audit/audit-page";
import { hasRank } from "@/lib/api/session";

export const Route = createFileRoute("/audit")({
  beforeLoad: ({ context }) => {
    if (context.session === null) {
      throw redirect({ to: "/login" });
    }
    if (!hasRank(context.session, "administrateur")) {
      throw redirect({ to: "/settings" });
    }
  },
  head: () => ({
    meta: [
      { title: "Audit — Nexus" },
      {
        name: "description",
        content:
          "Administrator-only audit ledger, integrity verification and retention operations.",
      },
      { property: "og:title", content: "Audit — Nexus" },
      {
        property: "og:description",
        content: "Audit ledger and operational data controls.",
      },
    ],
  }),
  component: AuditPage,
});
