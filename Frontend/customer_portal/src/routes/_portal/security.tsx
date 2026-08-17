import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Monitor, Smartphone, Laptop } from "lucide-react";
import { copy } from "@/lib/copy";
import { sessions, securityEvents } from "@/lib/fixtures/customer";
import {
  Button,
  Card,
  FieldRow,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/security")({
  head: () => ({
    meta: [
      { title: "Security — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Manage your Nexus sign-in and active devices.",
      },
      { property: "og:title", content: "Security — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Sign-in and active devices.",
      },
    ],
  }),
  component: SecurityScreen,
});

const SECTIONS = [
  { id: "signIn", label: copy.security.nav.signIn },
  { id: "sessions", label: copy.security.nav.sessions },
  { id: "activity", label: copy.security.nav.activity },
] as const;

const DEVICE_ICON = [Laptop, Smartphone, Monitor];

function SecurityScreen() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("signIn");

  return (
    <div className="grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav className="lg:sticky lg:top-24 lg:self-start">
        <ul className="space-y-sp-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setSection(s.id)}
                className={cn(
                  "focus-ring t-ui flex h-9 w-full items-center rounded-r-2 px-sp-5 text-left transition-colors duration-200",
                  section === s.id
                    ? "bg-surface-3 text-ink-1"
                    : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                )}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-sp-8">
        {section === "signIn" && (
          <Card>
            <SectionLabel>{copy.security.signIn}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <FieldRow
                label={copy.security.password}
                value="Last changed 12 March"
                action={
                  <Button variant="quiet" size="sm">
                    {copy.security.changePassword}
                  </Button>
                }
              />
            </div>
          </Card>
        )}

        {section === "sessions" && (
          <Card>
            <SectionLabel
              right={
                <Button variant="quiet" size="sm">
                  {copy.security.signOutAll}
                </Button>
              }
            >
              {copy.security.sessions}
            </SectionLabel>
            <ul className="mt-sp-6 divide-y divide-stroke-subtle">
              {sessions.map((s, i) => {
                const Icon = DEVICE_ICON[i % DEVICE_ICON.length]!;
                return (
                  <li key={s.id} className="flex items-center gap-sp-6 py-sp-6">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                      <Icon size={16} strokeWidth={1.5} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-sp-4">
                        <span className="t-body-strong text-ink-1">{s.device}</span>
                        {s.current && <StatusChip tone="solid">{copy.security.thisDevice}</StatusChip>}
                      </div>
                      <div className="t-caption text-ink-4">
                        {s.browser} · {s.location}
                      </div>
                    </div>
                    <span className="t-mono-s shrink-0 text-ink-5">{s.lastActive}</span>
                    {!s.current && (
                      <Button variant="quiet" size="sm">
                        {copy.security.signOutDevice}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        )}

        {section === "activity" && (
          <Card>
            <SectionLabel>{copy.security.activity}</SectionLabel>
            <ul className="mt-sp-6 divide-y divide-stroke-subtle">
              {securityEvents.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-sp-6 py-sp-5">
                  <div>
                    <div className="t-ui text-ink-1">{e.label}</div>
                    <div className="t-caption text-ink-4">{e.detail}</div>
                  </div>
                  <span className="t-mono-s text-ink-5">{e.at}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}
