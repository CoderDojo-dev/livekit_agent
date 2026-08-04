import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import {
  CardHeader,
  EmptyState,
  SearchInput,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { listPolicyRules } from "@/lib/api/policies.server";
import { policyKeys } from "@/lib/nexus/query-keys";
import {
  definitionEntries,
  enforcementLabel,
  governedByList,
  groupByDomain,
  ruleMatches,
  ruleStatusKey,
} from "@/lib/nexus/policy-view";
import type { PolicyRule } from "@/lib/api/policies.server";

const COLUMN_COUNT = 6;

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: "Policies — Nexus" },
      {
        name: "description",
        content: "Versioned operating limits the agent and advisors must respect.",
      },
      { property: "og:title", content: "Policies — Nexus" },
      { property: "og:description", content: "Thresholds, versions and enforcement state." },
    ],
  }),
  component: PoliciesPage,
});

function PoliciesPage() {
  const [search, setSearch] = useState("");

  const rulesQuery = useQuery({
    queryKey: policyKeys.rules(),
    queryFn: () => listPolicyRules(),
  });

  const rules = useMemo(() => rulesQuery.data?.rules ?? [], [rulesQuery.data]);

  const filtered = useMemo(() => rules.filter((r) => ruleMatches(r, search)), [rules, search]);
  const groups = useMemo(() => groupByDomain(filtered), [filtered]);

  return (
    <PageSection>
      {/* G4 — the enforcement model, stated once. */}
      <CardHeader
        title="Enforcement model"
        subtitle="Thresholds are enforced from POLICY_* environment variables, not from this registry; catalog rules are governance records only."
      />

      <div className="mt-sp-6">
        <TableShell
          toolbar={
            <SearchInput
              placeholder="Search policies"
              className="w-[260px]"
              value={search}
              onChange={setSearch}
            />
          }
          head={
            <tr>
              <Th>Policy</Th>
              <Th>Domain</Th>
              <Th>Thresholds</Th>
              <Th>Enforcement</Th>
              <Th align="right">Version</Th>
              <Th>Status</Th>
            </tr>
          }
          footer={<span className="t-caption text-ink-4">{filtered.length} policies</span>}
        >
          {rulesQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={6} />
          ) : rulesQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={rulesQuery.error}
              onRetry={() => rulesQuery.refetch()}
            />
          ) : rules.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={ScrollText}
                  title="No policies registered"
                  description="The governance registry is empty."
                />
              </td>
            </tr>
          ) : (
            groups.map((group) => (
              <GroupRows key={group.domain} domain={group.domain} rules={group.rules} />
            ))
          )}
        </TableShell>
      </div>
    </PageSection>
  );
}

function GroupRows({ domain, rules }: { domain: string; rules: PolicyRule[] }) {
  return (
    <>
      <tr className="bg-surface-1">
        <td colSpan={COLUMN_COUNT} className="px-sp-6 py-sp-2">
          <span className="t-micro-2 text-ink-5">Domain · {domain}</span>
        </td>
      </tr>
      {rules.map((rule) => {
        const entries = definitionEntries(rule.definition);
        const governedBy = governedByList(rule);
        return (
          <tr key={rule.rule_id} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="t-mono text-ink-1">{rule.rule_id}</span>
              {rule.description ? (
                <span className="t-caption mt-sp-1 block text-ink-4">{rule.description}</span>
              ) : null}
            </Td>
            <Td>
              <span className="t-ui text-ink-2">{rule.domain}</span>
            </Td>
            <Td>
              {/* G3 — one label+Token pair per definition key, stacked. */}
              {entries.length === 0 ? (
                <span className="t-caption text-ink-5">—</span>
              ) : (
                <div className="flex flex-col gap-sp-2">
                  {entries.map((entry) => (
                    <span key={entry.label} className="flex items-baseline gap-sp-3">
                      <span className="t-caption text-ink-4">{entry.label}</span>
                      <Token>{entry.value}</Token>
                    </span>
                  ))}
                </div>
              )}
            </Td>
            <Td>
              {/* G4 — enforced vs catalog, plus the actionable env var names. */}
              <Token strong={rule.enforced}>{enforcementLabel(rule)}</Token>
              {governedBy.length > 0 ? (
                <span className="t-mono mt-sp-2 block text-ink-4">{governedBy.join(", ")}</span>
              ) : null}
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{rule.version}</span>
            </Td>
            <Td>
              <StatusChip status={ruleStatusKey(rule.active)} />
            </Td>
          </tr>
        );
      })}
    </>
  );
}
