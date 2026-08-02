import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { copy } from "@/lib/copy";
import { customer } from "@/lib/fixtures/customer";
import {
  Button,
  Card,
  Divider,
  FieldRow,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/profile")({
  head: () => ({
    meta: [
      { title: "Profile — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Your name, contact details, addresses, and regional settings — the information the Nexus assistant uses to reach you.",
      },
      { property: "og:title", content: "Profile — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Who you are and how we reach you.",
      },
    ],
  }),
  component: ProfileScreen,
});

const SECTIONS = [
  { id: "identity", label: copy.profile.nav.identity },
  { id: "contact", label: copy.profile.nav.contact },
  { id: "addresses", label: copy.profile.nav.addresses },
  { id: "locale", label: copy.profile.nav.locale },
] as const;

function ProfileScreen() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("identity");

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
        {section === "identity" && (
          <Card>
            <SectionLabel>{copy.profile.identity}</SectionLabel>
            <div className="mt-sp-7 flex items-center gap-sp-7">
              <div className="flex h-16 w-16 items-center justify-center rounded-r-4 border border-stroke-strong bg-surface-4 shadow-elev-1">
                <span className="t-metric-m text-ink-1">{customer.initials}</span>
              </div>
              <div>
                <div className="t-title-2 text-ink-1">{customer.fullName}</div>
                <div className="t-mono-s mt-sp-2 text-ink-5">
                  {copy.profile.customerSince(customer.customerSince)}
                </div>
                <div className="mt-sp-5 flex gap-sp-4">
                  <Button variant="secondary" size="sm">
                    {copy.profile.changePhoto}
                  </Button>
                  <Button variant="ghost" size="sm">
                    {copy.profile.remove}
                  </Button>
                </div>
              </div>
            </div>
            <Divider className="my-sp-7" />
            <div className="divide-y divide-stroke-subtle">
              <FieldRow
                label={copy.profile.fields.fullName}
                value={customer.fullName}
                action={<Button variant="quiet" size="sm">{copy.profile.edit}</Button>}
              />
              <FieldRow
                label={copy.profile.fields.preferredName}
                value={customer.preferredName}
                action={<Button variant="quiet" size="sm">{copy.profile.edit}</Button>}
              />
              <FieldRow
                label={copy.profile.fields.dateOfBirth}
                value={customer.dateFormat}
                hint={copy.profile.locked}
              />
              <FieldRow
                label={copy.profile.fields.reference}
                value={customer.reference}
                mono
                action={<Button variant="quiet" size="sm">{copy.profile.copy}</Button>}
              />
            </div>
          </Card>
        )}

        {section === "contact" && (
          <Card>
            <SectionLabel>{copy.profile.contact}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <FieldRow
                label={copy.profile.fields.email}
                value={customer.email}
                action={
                  <div className="flex items-center gap-sp-4">
                    <StatusChip tone="outline">VERIFIED</StatusChip>
                    <Button variant="quiet" size="sm">{copy.profile.edit}</Button>
                  </div>
                }
              />
              <FieldRow
                label={copy.profile.fields.phone}
                value={customer.phone}
                mono
                action={
                  <div className="flex items-center gap-sp-4">
                    <StatusChip tone="dashed">UNVERIFIED</StatusChip>
                    <Button variant="quiet" size="sm">{copy.profile.edit}</Button>
                  </div>
                }
              />
            </div>
          </Card>
        )}

        {section === "addresses" && (
          <Card>
            <SectionLabel
              right={<Button variant="quiet" size="sm">{copy.profile.edit}</Button>}
            >
              {copy.profile.addresses}
            </SectionLabel>
            <div className="mt-sp-7">
              <div className="t-label text-ink-4">{copy.profile.billingAddress}</div>
              <address className="t-body mt-sp-3 not-italic text-ink-1">
                {customer.billingAddress.map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </address>
            </div>
            <Divider className="my-sp-7" />
            <div className="t-caption text-ink-4">{copy.profile.sameAddress}</div>
          </Card>
        )}

        {section === "locale" && (
          <Card>
            <SectionLabel>{copy.profile.locale}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <FieldRow label={copy.profile.fields.language} value={customer.language} />
              <FieldRow label={copy.profile.fields.region} value={customer.region} />
              <FieldRow label={copy.profile.fields.timeZone} value={customer.timeZone} mono />
              <FieldRow label={copy.profile.fields.dateFormat} value={customer.dateFormat} />
              <FieldRow label={copy.profile.fields.numberFormat} value={customer.numberFormat} mono />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
