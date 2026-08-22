import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpRight, Check, Copy, Languages, MapPin, Mail, UserRound } from "lucide-react";
import {
  Button,
  Card,
  Divider,
  FieldRow,
  IconFrame,
  SectionLabel,
} from "@/components/portal/primitives";
import {
  ErrorState,
  PageSection,
  SkeletonLine,
  SkeletonList,
  SkeletonMetric,
} from "@/components/portal/data";
import { SettingsNav } from "@/components/portal/settings-nav";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { usePortalSession } from "@/lib/use-portal-session";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "identity", label: copy.profile.nav.identity, icon: UserRound },
  { id: "contact", label: copy.profile.nav.contact, icon: Mail },
  { id: "addresses", label: copy.profile.nav.addresses, icon: MapPin },
  { id: "locale", label: copy.profile.nav.locale, icon: Languages },
] as const;

/**
 * Copies the customer reference.
 *
 * The reference is the one string on this page a customer is ever asked to
 * read out — to an advisor, into a payment form, onto a shop counter — and it
 * is deliberately unselectable-looking mono text inside a read-only row. A copy
 * control is the difference between "your reference is 4471-882-01" and having
 * to transcribe it. The tick is held for a moment and then released, so the
 * button confirms itself without a toast having to say "copied" twice.
 */
function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setDone(true);
      window.setTimeout(() => setDone(false), 1600);
    } catch {
      // Clipboard access is refused outright in some embedded browsers, and a
      // button that silently does nothing is worse than one that says why.
      toast.error(copy.profile.copyFailed);
    }
  }

  return (
    <Button variant="quiet" size="sm" onClick={() => void onCopy()} aria-label={copy.profile.copy}>
      {done ? <Check size={13} strokeWidth={1.8} /> : <Copy size={13} strokeWidth={1.5} />}
      {done ? copy.profile.copied : copy.profile.copy}
    </Button>
  );
}

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
      { title: pageTitle("Profile") },
      {
        name: "description",
        content:
          "Your name, contact details, addresses, and regional settings — the information the assistant uses to reach you.",
      },
      { property: "og:title", content: brand.name },
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

  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const query = useQuery({
    // Customer-scoped like every other portal read: an unscoped key can serve
    // the previous account's details after a sign-out/sign-in in the same tab.
    queryKey: qk.profileDetail(cid),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });

  if (query.isPending) {
    return (
      <div className="grid gap-sp-7 lg:grid-cols-[200px_1fr]">
        <div className="flex gap-sp-3 lg:flex-col">
          {SECTIONS.map((s) => (
            <SkeletonLine key={s.id} className="h-9 w-28 lg:w-full" />
          ))}
        </div>
        <Card>
          <SkeletonMetric />
          <Divider className="mt-sp-7" />
          <SkeletonList rows={3} />
        </Card>
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      </Card>
    );
  }

  const me = query.data;
  const locale = localeFor(me.preferred_language);
  const numberSample = new Intl.NumberFormat(locale.tag).format(1234.56);
  const dateSample = formatDay(me.customer_since, locale.tag);

  return (
    <div className="grid gap-sp-7 lg:grid-cols-[200px_1fr]">
      <SettingsNav
        sections={SECTIONS}
        value={section}
        onChange={setSection}
        label={copy.profile.navLabel}
      />

      <div className="flex flex-col gap-sp-7">
        {section === "identity" ? (
          <PageSection>
            <Card>
              <SectionLabel>{copy.profile.identity}</SectionLabel>
              <div className="mt-sp-7 flex items-center gap-sp-6">
                {/* The initials plate now carries a dashed outer ring, the same
                    device the empty state uses: it reads as a held portrait
                    rather than as a grey square with two letters in it. */}
                <div className="relative shrink-0">
                  <div className="t-title-2 flex h-14 w-14 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-3 text-ink-1 shadow-elev-1">
                    {initialsOf(me.first_name, me.last_name)}
                  </div>
                  <span
                    aria-hidden="true"
                    className="absolute -inset-sp-3 rounded-r-4 border border-dashed border-stroke-subtle"
                  />
                </div>
                <div className="min-w-0">
                  <div className="t-title-2 truncate text-ink-1">{me.full_name}</div>
                  <div className="t-caption mt-sp-2 text-ink-4">
                    {copy.profile.customerSince(dateSample)}
                  </div>
                </div>
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
                    action={<CopyButton value={me.account_number} />}
                  />
                </>
              ) : null}
            </Card>
          </PageSection>
        ) : null}

        {section === "contact" ? (
          <PageSection>
            <Card>
              <SectionLabel>{copy.profile.contact}</SectionLabel>
              <div className="mt-sp-5">
                <FieldRow label={copy.profile.fields.email} value={me.email ?? "\u2014"} />
                <Divider />
                <FieldRow
                  label={copy.profile.fields.phone}
                  value={me.phone ?? me.msisdn ?? "\u2014"}
                  mono
                />
              </div>
            </Card>
          </PageSection>
        ) : null}

        {section === "addresses" ? (
          <PageSection>
            <Card>
              <SectionLabel>{copy.profile.addresses}</SectionLabel>
              <div className="mt-sp-6 flex items-start gap-sp-6">
                <IconFrame icon={MapPin} tone="strong" />
                <div className="min-w-0">
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
              </div>
            </Card>
          </PageSection>
        ) : null}

        {section === "locale" ? (
          <PageSection>
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
          </PageSection>
        ) : null}

        {/* A bare caption-sized text link at the bottom of a column of cards
            was the smallest and least visible target on the page. It keeps its
            quiet weight but gains a hit area and the arrow every other
            cross-screen pointer in the portal now carries. */}
        <Link
          to="/security"
          className="focus-ring group inline-flex w-fit items-center gap-sp-4 rounded-r-2 border border-stroke-subtle px-sp-5 py-sp-4 text-ink-4 transition-colors duration-200 hover:border-stroke-default hover:bg-surface-2 hover:text-ink-1"
        >
          <span className="t-ui">{copy.profile.sessionsMoved}</span>
          <ArrowUpRight
            size={14}
            strokeWidth={1.6}
            aria-hidden="true"
            className="transition-transform duration-200 group-hover:-translate-y-px group-hover:translate-x-px"
          />
        </Link>
      </div>
    </div>
  );
}
