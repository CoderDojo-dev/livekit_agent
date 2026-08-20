import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ScrollText, ShieldCheck, SlidersHorizontal } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, TopProgress } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { PageSwap, Reveal } from "@/components/nexus/motion";
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

  return (
    <>
      {/* ---- The enforcement model, stated once (G4) ---- */}
      <PageSection index={0}>
        <Card>
          <CardHeader
            title="Enforcement model"
            subtitle="Thresholds are enforced from POLICY_* environment variables, not from this registry; catalog rules are governance records only."
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
      <PageSection index={1}>
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

  return (
    <div className={cn("border-b border-stroke-subtle last:border-b-0", open && "bg-surface-1/40")}>
      {/* ---- Collapsed line: everything needed to TRIAGE, nothing needed to READ ---- */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-sp-5 px-sp-6 py-sp-5 text-left transition-colors duration-[120ms] hover:bg-surface-3/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
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
            <span className="t-caption mt-sp-1 block truncate text-ink-4">{rule.description}</span>
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
