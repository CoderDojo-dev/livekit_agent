import { createFileRoute } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { Card } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { SETTINGS_SECTIONS } from "@/lib/nexus/data";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — Nexus" },
      { name: "description", content: "Workspace configuration, members, roles, API keys and audit." },
      { property: "og:title", content: "Settings — Nexus" },
      { property: "og:description", content: "Configure the workspace and its access." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <PageSection>
      <Card padded={false}>
        <ul>
          {SETTINGS_SECTIONS.map((s) => (
            <li key={s.name} className="border-b border-stroke-subtle last:border-b-0">
              <button
                type="button"
                className="flex w-full items-center gap-sp-5 px-sp-7 py-sp-6 text-left transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <span className="min-w-0">
                  <span className="t-ui block text-ink-1">{s.name}</span>
                  <span className="t-caption block text-ink-4">{s.description}</span>
                </span>
                <ChevronRight
                  size={16}
                  strokeWidth={1.5}
                  aria-hidden="true"
                  className="ml-auto text-ink-5"
                />
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </PageSection>
  );
}
