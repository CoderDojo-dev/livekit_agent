import { createFileRoute } from "@tanstack/react-router";
import { EscalationsPage } from "@/components/escalations/escalations-page";

export const Route = createFileRoute("/escalations")({
  head: () => ({
    meta: [
      { title: "Escalations — Nexus" },
      {
        name: "description",
        content:
          "Handoffs from the AI to a manager agent or a human advisor, with the context dossier.",
      },
      { property: "og:title", content: "Escalations — Nexus" },
      { property: "og:description", content: "Every AI-to-human handoff and its dossier." },
    ],
  }),
  component: EscalationsPage,
});
