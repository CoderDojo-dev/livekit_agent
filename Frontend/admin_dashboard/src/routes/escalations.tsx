import { createFileRoute } from "@tanstack/react-router";
import { EscalationsPage } from "@/components/escalations/escalations-page";
import { pageTitle } from "@/lib/nexus/brand";

export const Route = createFileRoute("/escalations")({
  head: () => ({
    meta: [
      { title: pageTitle("Escalations") },
      {
        name: "description",
        content:
          "Handoffs from the AI to a manager agent or a human advisor, with the context dossier.",
      },
      { property: "og:title", content: pageTitle("Escalations") },
      { property: "og:description", content: "Every AI-to-human handoff and its dossier." },
    ],
  }),
  component: EscalationsPage,
});
