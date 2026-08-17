import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import {
  Card,
  CardHeader,
  Avatar,
  PresenceDot,
  Token,
  EmptyState,
} from "@/components/nexus/primitives";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { ServiceHealthPanel } from "@/components/nexus/service-health-panel";
import { getKpis, getSystemOverview } from "@/lib/api/analytics.server";
import { getVerdictDistribution } from "@/lib/api/decisions.server";
import { listAdvisors } from "@/lib/api/advisors.server";
import { analyticsKeys, queryKeys } from "@/lib/nexus/query-keys";
import { formatRatio, rateContext, verdictShare, verdictTotal } from "@/lib/nexus/analytics-view";
import { advisorStatusKey, advisorPresenceLabel } from "@/lib/nexus/advisor-view";
import { formatInteger, formatCompact, initials } from "@/lib/nexus/format";
import { errorMessage } from "@/lib/api/errors";
import { hasRank } from "@/lib/api/session";
import { Route as RootRoute } from "@/routes/__root";

export const Route = createFileRoute("/overview")({
  head: () => ({
    meta: [
      { title: "Overview â€” Nexus" },
      {
        name: "description",
        content: "Platform totals, containment KPIs and who is on the floor.",
      },
      { property: "og:title", content: "Overview â€” Nexus" },
      { property: "og:description", content: "Current state of the support platform." },
    ],
  }),
  component: OverviewPage,
});

function OverviewPage() {
  const { session } = RootRoute.useRouteContext();
  const isAdmin = session !== null && hasRank(session, "administrateur");
  const kpis = useQuery({ queryKey: analyticsKeys.kpis(), queryFn: () => getKpis() });
  const system = useQuery({ queryKey: analyticsKeys.system(), queryFn: () => getSystemOverview() });
  const verdicts = useQuery({
    queryKey: analyticsKeys.verdicts(),
    queryFn: () => getVerdictDistribution(),
  });
  const advisors = useQuery({
    queryKey: queryKeys.advisors.list(false),
    queryFn: () => listAdvisors({ data: { includeInactive: false } }),
  });

  return (
    <>
      {/* ---- Containment KPIs (all-time; no comparison exists, so no deltas) ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        {kpis.isPending ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : kpis.isError ? (
          <div className="xl:col-span-4">
            <ErrorState error={kpis.error} onRetry={() => void kpis.refetch()} />
          </div>
        ) : (
          <>
            <HeroStat
              label="Total sessions"
              value={formatCompact(kpis.data.total_sessions)}
              context="All sessions ever recorded"
            />
            <StatCard
              label="Containment rate"
              value={formatRatio(kpis.data.containment_rate)}
              context={rateContext(kpis.data, "Resolved without escalation")}
              meta={`${formatInteger(kpis.data.resolved)} resolved`}
            />
            <StatCard
              label="Escalation rate"
              value={formatRatio(kpis.data.escalation_rate)}
              context={rateContext(kpis.data, "Handed to an advisor")}
              meta={`${formatInteger(kpis.data.escalated)} escalated`}
            />
            <StatCard
              label="Avg. frustration"
              value={kpis.data.avg_frustration.toFixed(2)}
              context="Mean peak frustration per session"
            />
          </>
        )}
      </PageSection>

      {/* ---- Policy verdict mix (last 100 verdicts) ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-3">
        {verdicts.isPending ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : verdicts.isError ? (
          <div className="xl:col-span-3">
            <ErrorState error={verdicts.error} onRetry={() => void verdicts.refetch()} />
          </div>
        ) : (
          (() => {
            const mix = verdicts.data.verdict_distribution;
            const total = verdictTotal(mix);
            return (
              <>
                <StatCard
                  label="Authorized"
                  value={formatInteger(mix.authorized)}
                  context={verdictShare(mix.authorized, total)}
                />
                <StatCard
                  label="Refused"
                  value={formatInteger(mix.refused)}
                  context={verdictShare(mix.refused, total)}
                />
                <StatCard
                  label="Escalated"
                  value={formatInteger(mix.escalated)}
                  context={verdictShare(mix.escalated, total)}
                />
              </>
            );
          })()
        )}
      </PageSection>

      <PageSection className="grid gap-sp-6 xl:grid-cols-2">
        {/* ---- Team availability (real: advisor registry) ---- */}
        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader title="Team Availability" subtitle="Advisors currently on the floor." />
          </div>
          {advisors.isPending ? (
            <div className="px-sp-7 pb-sp-7">
              <CardSkeleton />
            </div>
          ) : advisors.isError ? (
            <div className="px-sp-7 pb-sp-7">
              <ErrorState error={advisors.error} onRetry={() => void advisors.refetch()} />
            </div>
          ) : advisors.data.length === 0 ? (
            <div className="px-sp-7 pb-sp-7">
              <EmptyState
                icon={Users}
                title="No advisors"
                description="Register an advisor to see availability here."
              />
            </div>
          ) : (
            <ul>
              {advisors.data.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                >
                  <Avatar initials={initials(a.full_name)} name={a.full_name} />
                  <div className="min-w-0">
                    <p className="t-ui truncate text-ink-1">{a.full_name}</p>
                    <p className="t-caption inline-flex items-center gap-sp-3 text-ink-4">
                      <PresenceDot live={advisorStatusKey(a) === "online"} />
                      {advisorPresenceLabel(a.status)}
                    </p>
                  </div>
                  <span className="t-label ml-auto text-ink-3">{a.language ?? "â€”"}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ---- Service inventory. NO status: see Cookbook 9 Â§0. ---- */}
        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader
              title="Service Catalog"
              subtitle="Services reported by system overview and the domain each owns. Runtime health is not reported."
            />
          </div>
          {system.isPending ? (
            <div className="px-sp-7 pb-sp-7">
              <CardSkeleton />
            </div>
          ) : system.isError ? (
            <div className="px-sp-7 pb-sp-7">
              <ErrorState error={system.error} onRetry={() => void system.refetch()} />
            </div>
          ) : (
            <ul>
              {system.data.services.map((s) => (
                <li
                  key={`${s.name}-${s.port}`}
                  className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                >
                  <div className="min-w-0">
                    <p className="t-ui truncate text-ink-1">{s.name}</p>
                    <p className="t-caption truncate text-ink-4">{s.domain}</p>
                  </div>
                  <Token className="ml-auto">{s.port}</Token>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </PageSection>

      <PageSection>
        <ServiceHealthPanel isAdmin={isAdmin} />
      </PageSection>

      {/* ---- Platform totals ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        {system.isPending || system.isError ? null : (
          <>
            <StatCard
              label="Customers"
              value={formatInteger(system.data.metrics.total_customers)}
              context="Records in the CRM"
            />
            <StatCard
              label="Turns"
              value={formatCompact(system.data.metrics.total_turns)}
              context="Transcript turns persisted"
            />
            <StatCard
              label="Actions"
              value={formatInteger(system.data.metrics.total_actions)}
              context="Entries in the action ledger"
            />
            <StatCard
              label="Audit entries"
              value={formatCompact(system.data.metrics.total_audit_entries)}
              context="Hash-chained audit records"
            />
          </>
        )}
      </PageSection>
    </>
  );
}
