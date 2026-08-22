import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheck,
  CalendarClock,
  ChevronDown,
  Repeat,
  ScrollText,
  ShieldCheck,
  SlidersHorizontal,
  SquarePen,
  Wallet,
} from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  IconButton,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, TopProgress } from "@/components/nexus/states";
import { MetricCard, MetricRow } from "@/components/nexus/metric-card";
import { SectionHeading } from "@/components/nexus/blocks";
import { Pager } from "@/components/nexus/pager";
import { PageSwap, Reveal } from "@/components/nexus/motion";
import {
  PolicyCreateButton,
  PolicyDeleteButton,
  PolicyEditDialog,
} from "@/components/nexus/policy-edit";
import { listPolicyRules } from "@/lib/api/policies.server";
import { policyKeys } from "@/lib/nexus/query-keys";
import { pageTitle } from "@/lib/nexus/brand";
import {
  definitionEntries,
  enforcementLabel,
  governedByList,
  groupByDomain,
  ruleMatches,
  ruleStatusKey,
} from "@/lib/nexus/policy-view";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { formatInteger } from "@/lib/nexus/format";
import { useAdaptivePageSize } from "@/hooks/use-adaptive-page-size";
import { cn } from "@/lib/utils";
import type { PolicyRule } from "@/lib/api/policies.server";

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: pageTitle("Policies") },
      {
        name: "description",
        content: "Versioned operating limits the agent and advisors must respect.",
      },
      { property: "og:title", content: pageTitle("Policies") },
      { property: "og:description", content: "Thresholds, versions and enforcement state." },
    ],
  }),
  component: PoliciesPage,
});

const SCOPES = [
  { id: "all", label: "All" },
  { id: "enforced", label: "Enforced" },
  { id: "catalog", label: "Catalog" },
] as const;

type Scope = (typeof SCOPES)[number]["id"];

/**
 * "POLICY_DEFERRAL_UNPAID_THRESHOLD_TND" -> "DEFERRAL_UNPAID_THRESHOLD_TND".
 *
 * Every governed variable starts with the same POLICY_ prefix, so on a card where each one is
 * already labelled a guardrail the prefix is eight characters of pure repetition — and it was
 * what pushed these names past the card's width. The full name stays in the title attribute and
 * in the expanded rule, so nothing is lost for someone who needs to go and change it.
 */
function shortEnvVar(name: string): string {
  return name.startsWith("POLICY_") ? name.slice("POLICY_".length) : name;
}

/** Threshold label -> icon. Falls back to a generic badge for anything unmapped. */
const GUARDRAIL_ICON: Record<
  string,
  React.ComponentType<{ size?: number; strokeWidth?: number }>
> = {
  "Max payment": Wallet,
  "Min account age": CalendarClock,
  "Max deferrals": Repeat,
  "Unpaid review threshold": Wallet,
};

/**
 * Policies is a READING surface, not a data table.
 *
 * It previously rendered governance prose, an unbounded threshold list and a comma-joined env-var
 * list inside three columns of a six-column table. Because a <table> distributes width by content
 * pressure, the description column stole the width, threshold pairs wrapped mid-pair, and rows
 * ranged from 52px to ~200px tall against a grid designed for 52px — which is what read as
 * "overlapping text".
 *
 * The replacement is a disclosure list:
 *  - COLLAPSED, a policy is one scannable line: id, domain, version, enforcement, status. The
 *    whole registry fits on one screen, so you can survey it before reading any of it.
 *  - EXPANDED, the description gets `t-body` (22px line-height) at a 72ch measure, and the
 *    thresholds get a real definition grid instead of a wrapped stack.
 */
function PoliciesPage() {
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState<Scope>("all");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: policyKeys.rules(),
    queryFn: () => listPolicyRules(),
  });

  const rules = useMemo(() => rulesQuery.data?.rules ?? [], [rulesQuery.data]);

  const filtered = useMemo(
    () =>
      rules
        .filter((rule) => ruleMatches(rule, search))
        .filter((rule) =>
          scope === "all" ? true : scope === "enforced" ? rule.enforced : !rule.enforced,
        ),
    [rules, search, scope],
  );

  /* Collapsed rows are one line, so more of them fit than a stacked table row would allow. */
  const pageSize = useAdaptivePageSize({
    rowHeight: 58,
    chrome: 520,
    min: 5,
    max: 12,
    fallback: 8,
  });

  /* A filter that shrinks the set must not strand the reader on a page that no longer exists. */
  useEffect(() => setPage(0), [search, scope]);
  const safePage = clampPage(page, filtered.length, pageSize);

  const visible = slicePage(filtered, safePage, pageSize);
  const groups = useMemo(() => groupByDomain(visible), [visible]);

  const enforcedCount = rules.filter((rule) => rule.enforced).length;

  /**
   * The live guardrails, flattened out of the enforced rules.
   *
   * business-api overlays each governed rule's `definition` with the CURRENT value of its
   * POLICY_* variable before it reaches us (see policy_view.overlay), so these are the numbers
   * the deterministic policy engine is applying right now — not a seeded literal that could have
   * drifted. Each threshold is paired with the env var that governs it, because that variable is
   * the only place the number can actually be changed.
   */
  const guardrails = useMemo(
    () =>
      rules
        .filter((rule) => rule.enforced)
        .flatMap((rule) => {
          const envVars = governedByList(rule);
          return definitionEntries(rule.definition).map((entry, index) => ({
            key: `${rule.rule_id}:${entry.label}`,
            label: entry.label,
            value: entry.value,
            rule: rule.rule_id,
            /* One rule can be governed by several variables, in the same order its definition
             * keys are emitted; fall back to the first rather than mislabelling. */
            envVar: shortEnvVar(envVars[index] ?? envVars[0] ?? "—"),
            fullEnvVar: envVars[index] ?? envVars[0] ?? "—",
            icon: GUARDRAIL_ICON[entry.label] ?? BadgeCheck,
          }));
        }),
    [rules],
  );

  return (
    <>
      {/* ================= Guardrails: what the agent is actually held to ================= */}
      <PageSection index={0}>
        <SectionHeading
          title="Guardrails in force"
          hint="Live values the policy engine is applying right now"
          icon={ShieldCheck}
        />

        {rulesQuery.isPending ? (
          <MetricRow>
            <CardSkeleton lines={2} />
            <CardSkeleton lines={2} />
            <CardSkeleton lines={2} />
            <CardSkeleton lines={2} />
          </MetricRow>
        ) : guardrails.length === 0 ? (
          <Card>
            <EmptyState
              icon={ShieldCheck}
              compact
              title="No enforced thresholds"
              description="No registry rule is currently governed by a POLICY_* variable."
            />
          </Card>
        ) : (
          <MetricRow>
            {guardrails.map((rail) => (
              <MetricCard
                key={rail.key}
                compact
                label={rail.label}
                value={rail.value}
                icon={rail.icon}
                /* The rule id identifies the guardrail; the env var is the only actionable fact.
                 * "Status: Enforced" was dropped — the band is titled "Guardrails in force", so
                 * every card in it is enforced by definition. The variable name is long, so it
                 * gets the full footer row and truncates with its value on hover. */
                context={rail.rule}
                footer={[{ label: "Set by", value: rail.envVar, title: rail.fullEnvVar }]}
              />
            ))}
          </MetricRow>
        )}
      </PageSection>

      {/* ---- The enforcement model, stated once (G4) ---- */}
      <PageSection index={1}>
        <Card>
          <CardHeader
            title="How these are changed"
            subtitle="These numbers are read from POLICY_* environment variables by the policy engine and mirrored here at read time. They are deliberately NOT stored in this registry, so what you see is always what is enforced — editing a row here could never move a threshold, and is not offered."
            icon={ShieldCheck}
            action={
              rulesQuery.data ? (
                <div className="flex items-center gap-sp-5">
                  <span className="t-caption text-ink-5">
                    <span className="t-mono text-ink-1">{formatInteger(enforcedCount)}</span>{" "}
                    enforced
                  </span>
                  <span className="t-caption text-ink-5">
                    <span className="t-mono text-ink-2">
                      {formatInteger(rules.length - enforcedCount)}
                    </span>{" "}
                    catalog
                  </span>
                </div>
              ) : null
            }
          />
        </Card>
      </PageSection>

      {/* ---- The registry ---- */}
      <PageSection index={2}>
        <Card padded={false} className="overflow-hidden">
          <div className="relative flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5">
            <SearchInput
              placeholder="Search policies"
              className="w-full sm:w-[260px]"
              value={search}
              onChange={setSearch}
            />
            <Segmented
              groupId="policy-scope"
              items={SCOPES.map((option) => option.label)}
              active={SCOPES.find((option) => option.id === scope)!.label}
              onSelect={(label) => setScope(SCOPES.find((o) => o.label === label)!.id)}
            />
            <span className="ml-auto">
              <PolicyCreateButton />
            </span>
            <TopProgress
              active={rulesQuery.isFetching && !rulesQuery.isPending}
              className="absolute inset-x-0 bottom-[-1px]"
            />
          </div>

          {rulesQuery.isPending ? (
            <div className="p-sp-7">
              <CardSkeleton lines={6} />
            </div>
          ) : rulesQuery.isError ? (
            <div className="p-sp-7">
              <ErrorState error={rulesQuery.error} onRetry={() => void rulesQuery.refetch()} />
            </div>
          ) : rules.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="No policies registered"
              description="The governance registry is empty."
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="No matching policies"
              description="No rule matches this search or scope."
            />
          ) : (
            <PageSwap pageKey={safePage}>
              <div>
                {groups.map((group) => (
                  <section key={group.domain}>
                    {/* Domain rail. Sticky so the grouping survives the expanded panel above it. */}
                    <h3 className="sticky top-[60px] z-10 border-y border-stroke-subtle bg-surface-1/95 px-sp-6 py-sp-3 t-micro-2 text-ink-5 backdrop-blur-sm">
                      {group.domain}
                    </h3>
                    {group.rules.map((rule) => (
                      <PolicyRow
                        key={rule.rule_id}
                        rule={rule}
                        open={expanded === rule.rule_id}
                        onToggle={() =>
                          setExpanded((current) => (current === rule.rule_id ? null : rule.rule_id))
                        }
                      />
                    ))}
                  </section>
                ))}
              </div>
            </PageSwap>
          )}

          {filtered.length > 0 ? (
            <div className="border-t border-stroke-subtle px-sp-6 py-sp-5">
              <Pager
                page={safePage}
                pageSize={pageSize}
                total={filtered.length}
                onPageChange={(next) => {
                  setPage(next);
                  // Collapsing on page change avoids an expanded panel from page 2 lingering
                  // over an unrelated rule on page 3.
                  setExpanded(null);
                }}
                noun="policies"
              />
            </div>
          ) : null}
        </Card>
      </PageSection>
    </>
  );
}

/* ---------------------------------------------------------------------------------------------
 * One policy
 * ------------------------------------------------------------------------------------------- */

function PolicyRow({
  rule,
  open,
  onToggle,
}: {
  rule: PolicyRule;
  open: boolean;
  onToggle: () => void;
}) {
  const entries = definitionEntries(rule.definition);
  const governedBy = governedByList(rule);
  const [editing, setEditing] = useState(false);

  return (
    <div
      className={cn(
        "group/policy border-b border-stroke-subtle last:border-b-0",
        open && "bg-surface-1/40",
      )}
    >
      {/* The positioning context is this ROW only, so the action lane stays vertically centred on
       * the collapsed line even when the panel below it is open. */}
      <div className="relative">
        {/* ---- Collapsed line: everything needed to TRIAGE, nothing needed to READ ---- */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          /* pr reserves the action lane. It sits on the BUTTON, not on an inner span: the status
           * chip is the row's last child, so padding applied further in left it sitting under the
           * edit/delete icons. */
          className="flex w-full items-center gap-sp-5 py-sp-5 pl-sp-6 pr-[88px] text-left transition-colors duration-[120ms] hover:bg-surface-3/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          <ChevronDown
            size={14}
            strokeWidth={1.5}
            aria-hidden="true"
            className={cn(
              "shrink-0 text-ink-5 transition-transform duration-[200ms]",
              open && "rotate-180",
            )}
          />

          <span className="min-w-0 flex-1">
            <span className="t-mono block truncate text-ink-1">{rule.rule_id}</span>
            {rule.description ? (
              /* One line here, in full below. A registry you cannot scan is a registry nobody
               * reads, so the collapsed row deliberately truncates rather than wrapping. */
              <span className="t-caption mt-sp-1 block truncate text-ink-4">
                {rule.description}
              </span>
            ) : null}
          </span>

          <span className="hidden shrink-0 items-center gap-sp-4 md:flex">
            {entries.length > 0 ? (
              <span className="t-caption text-ink-5">
                {entries.length} threshold{entries.length === 1 ? "" : "s"}
              </span>
            ) : null}
            <Token strong={rule.enforced}>{enforcementLabel(rule)}</Token>
            <span className="t-mono w-[36px] text-right text-ink-3">v{rule.version}</span>
          </span>

          <StatusChip status={ruleStatusKey(rule.active)} className="shrink-0" />
        </button>

        {/* Actions sit OUTSIDE the disclosure button: nesting a button inside a button is invalid
         * HTML and would make the whole row un-clickable for keyboard users. Absolutely positioned
         * over the row's right edge so the collapsed line keeps its existing layout. */}
        <div className="absolute right-sp-6 top-1/2 flex -translate-y-1/2 items-center gap-sp-2 opacity-45 transition-opacity duration-[120ms] group-hover/policy:opacity-100 focus-within:opacity-100">
          <IconButton
            size="sm"
            label={`Edit ${rule.rule_id}`}
            icon={SquarePen}
            onClick={() => setEditing(true)}
          />
          <PolicyDeleteButton rule={rule} />
        </div>
      </div>

      {editing ? <PolicyEditDialog rule={rule} onClose={() => setEditing(false)} /> : null}

      {/* ---- Expanded: a reading layout, not a table cell ---- */}
      <Reveal open={open}>
        <div className="grid gap-sp-8 px-sp-6 pb-sp-7 pl-[46px] lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            {rule.description ? (
              <>
                <p className="t-micro mb-sp-3 text-ink-5">Description</p>
                {/* t-body is 14/22 — a real reading line-height at a 72ch measure, instead of
                 * 12/16 caption text stretched across a 1200px table cell. */}
                <p className="t-body max-w-[72ch] text-ink-2">{rule.description}</p>
              </>
            ) : (
              <p className="t-caption text-ink-5">This rule carries no description.</p>
            )}

            {governedBy.length > 0 ? (
              <div className="mt-sp-7">
                <p className="t-micro mb-sp-3 text-ink-5">Governed by</p>
                <div className="flex flex-wrap gap-sp-3">
                  {governedBy.map((variable) => (
                    <Token key={variable}>{variable}</Token>
                  ))}
                </div>
                <p className="t-caption mt-sp-4 max-w-[64ch] text-ink-5">
                  Changing this policy means changing these environment variables on the service
                  that enforces them — not this registry.
                </p>
              </div>
            ) : null}
          </div>

          {/* Thresholds as a definition grid: label and value each get their own column, so a
           * long label can never push its value onto the next line. */}
          <div className="lg:border-l lg:border-stroke-subtle lg:pl-sp-7">
            <p className="t-micro mb-sp-4 flex items-center gap-sp-3 text-ink-5">
              <SlidersHorizontal size={12} strokeWidth={1.5} aria-hidden="true" />
              Thresholds
            </p>
            {entries.length === 0 ? (
              <p className="t-caption text-ink-5">No thresholds defined.</p>
            ) : (
              <dl className="space-y-sp-4">
                {entries.map((entry) => (
                  <div
                    key={entry.label}
                    className="flex items-baseline justify-between gap-sp-5 border-b border-stroke-subtle pb-sp-4 last:border-b-0 last:pb-0"
                  >
                    <dt className="t-caption min-w-0 text-ink-4">{entry.label}</dt>
                    <dd className="shrink-0">
                      <Token>{entry.value}</Token>
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </div>
      </Reveal>
    </div>
  );
}
