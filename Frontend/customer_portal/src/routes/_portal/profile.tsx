import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Divider,
  FieldRow,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { errorMessage } from "@/lib/api/errors";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "identity", label: copy.profile.nav.identity },
  { id: "contact", label: copy.profile.nav.contact },
  { id: "addresses", label: copy.profile.nav.addresses },
  { id: "locale", label: copy.profile.nav.locale },
] as const;

/** crm.customers stores only a language code. Everything below is derived, never invented. */
const LOCALES = {
  fr: { label: "Fran\u00e7ais", tag: "fr-TN" },
  ar: { label: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629", tag: "ar-TN" },
  en: { label: "English", tag: "en-GB" },
} as const;

const TIME_ZONE = "Africa/Tunis";

function localeFor(code: string) {
  return LOCALES[code as keyof typeof LOCALES] ?? LOCALES.fr;
}

function initialsOf(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

function formatDay(iso: string | null, tag: string) {
  if (!iso) return "\u2014";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "\u2014";
  return new Intl.DateTimeFormat(tag, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: TIME_ZONE,
  }).format(at);
}

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
  component: ProfilePage,
});

function ProfilePage() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("identity");

  const query = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });

  if (query.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading your details\u2026</p>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(query.error)}
        </p>
        <Button variant="secondary" className="mt-sp-6" onClick={() => void query.refetch()}>
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  const me = query.data;
  const locale = localeFor(me.preferred_language);
  const numberSample = new Intl.NumberFormat(locale.tag).format(1234.56);
  const dateSample = formatDay(me.customer_since, locale.tag);

  return (
    <div className="grid gap-sp-7 lg:grid-cols-[200px_1fr]">
      <nav className="flex gap-sp-3 lg:flex-col">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(s.id)}
            aria-pressed={section === s.id}
            className={cn(
              "focus-ring t-label rounded-r-2 px-sp-5 py-sp-3 text-left transition-colors duration-200",
              section === s.id
                ? "bg-surface-3 text-ink-1"
                : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
            )}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="flex flex-col gap-sp-7">
        {section === "identity" ? (
          <Card>
            <SectionLabel>{copy.profile.identity}</SectionLabel>
            <div className="mt-sp-7 flex items-center gap-sp-6">
              <div className="t-title-3 flex h-14 w-14 items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-1">
                {initialsOf(me.first_name, me.last_name)}
              </div>
              <div className="min-w-0">
                <div className="t-title-3 truncate text-ink-1">{me.full_name}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {copy.profile.customerSince(dateSample)}
                </div>
              </div>
              {me.vip ? (
                <StatusChip tone="solid" className="ml-auto">
                  VIP
                </StatusChip>
              ) : null}
            </div>
            <Divider className="mt-sp-7" />
            <FieldRow label={copy.profile.fields.fullName} value={me.full_name} />
            {me.account_number ? (
              <>
                <Divider />
                <FieldRow
                  label={copy.profile.fields.reference}
                  value={me.account_number}
                  mono
                  hint={copy.profile.locked}
                />
              </>
            ) : null}
          </Card>
        ) : null}

        {section === "contact" ? (
          <Card>
            <SectionLabel>{copy.profile.contact}</SectionLabel>
            <div className="mt-sp-5">
              <FieldRow
                label={copy.profile.fields.email}
                value={me.email ?? "\u2014"}
                action={me.email ? <StatusChip tone="outline">VERIFIED</StatusChip> : null}
              />
              <Divider />
              <FieldRow
                label={copy.profile.fields.phone}
                value={me.phone ?? me.msisdn ?? "\u2014"}
                mono
                action={<StatusChip tone="dashed">UNVERIFIED</StatusChip>}
              />
            </div>
          </Card>
        ) : null}

        {section === "addresses" ? (
          <Card>
            <SectionLabel>{copy.profile.addresses}</SectionLabel>
            <div className="mt-sp-6">
              <div className="t-label text-ink-4">{copy.profile.billingAddress}</div>
              {me.address_lines.length === 0 ? (
                <p className="t-body mt-sp-3 text-ink-5">{copy.empty.generic}</p>
              ) : (
                <div className="t-body-strong mt-sp-3 text-ink-1">
                  {me.address_lines.map((line) => (
                    <div key={line}>{line}</div>
                  ))}
                </div>
              )}
              <p className="t-caption mt-sp-5 text-ink-5">{copy.profile.locked}</p>
            </div>
          </Card>
        ) : null}

        {section === "locale" ? (
          <Card>
            <SectionLabel>{copy.profile.locale}</SectionLabel>
            <div className="mt-sp-5">
              <FieldRow label={copy.profile.fields.language} value={locale.label} />
              <Divider />
              <FieldRow label={copy.profile.fields.region} value={me.region ?? "\u2014"} />
              <Divider />
              <FieldRow label={copy.profile.fields.timeZone} value={TIME_ZONE} mono />
              <Divider />
              <FieldRow label={copy.profile.fields.dateFormat} value={dateSample} />
              <Divider />
              <FieldRow label={copy.profile.fields.numberFormat} value={numberSample} mono />
            </div>
          </Card>
        ) : null}

        <Link to="/security" className="t-caption text-ink-3 hover:text-ink-1 focus-ring">
          {copy.profile.sessionsMoved}
        </Link>
      </div>
    </div>
  );
}
