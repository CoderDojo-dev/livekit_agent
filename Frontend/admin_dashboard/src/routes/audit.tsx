import { createFileRoute, redirect } from "@tanstack/react-router";
import { AuditPage } from "@/components/audit/audit-page";
import { hasRank } from "@/lib/api/session";
import { pageTitle } from "@/lib/nexus/brand";

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
      { title: pageTitle("Audit") },
      {
        name: "description",
        content:
          "Administrator-only audit ledger, integrity verification and retention operations.",
      },
      { property: "og:title", content: pageTitle("Audit") },
      {
        property: "og:description",
        content: "Audit ledger and operational data controls.",
      },
    ],
  }),
  component: AuditPage,
});
