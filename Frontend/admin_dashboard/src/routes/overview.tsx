import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Boxes,
  CheckCircle2,
  Database,
  Frown,
  Gauge,
  MessagesSquare,
  Scale,
  ShieldAlert,
  Users,
  Zap,
} from "lucide-react";
import {
  Card,
  CardHeader,
  Avatar,
  PresenceDot,
  Token,
  EmptyState,
  Segmented,
} from "@/components/nexus/primitives";
import {
  HeroStat,
  StatCard,
  LineChart,
  Legend,
  SectionHeading,
  ShareBar,
} from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, TopProgress } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { PageSwap } from "@/components/nexus/motion";
import { MetricCard, MetricRow } from "@/components/nexus/metric-card";
import { ServiceHealthPanel } from "@/components/nexus/service-health-panel";
import { getAnalyticsTrend, getKpis, getSystemOverview } from "@/lib/api/analytics.server";
import { getVerdictDistribution } from "@/lib/api/decisions.server";
import { listAdvisors } from "@/lib/api/advisors.server";
import { analyticsKeys, queryKeys } from "@/lib/nexus/query-keys";
import {
  dayLabel,
  formatRatio,
  isChartable,
  rateContext,
  verdictTotal,
} from "@/lib/nexus/analytics-view";
import { advisorStatusKey, advisorPresenceLabel } from "@/lib/nexus/advisor-view";
import { formatInteger, formatCompact, initials } from "@/lib/nexus/format";
import { slicePage } from "@/lib/nexus/paginate";
import { hasRank } from "@/lib/api/session";
import { BRAND } from "@/lib/nexus/brand";
import { pageTitle } from "@/lib/nexus/brand";
import { Route as RootRoute } from "@/routes/__root";

export const Route = createFileRoute("/overview")({
  head: () => ({
    meta: [
      { title: pageTitle("Overview") },
      {
        name: "description",
        content: "Platform totals, containment KPIs and who is on the floor.",
      },
      { property: "og:title", content: pageTitle("Overview") },
      { property: "og:description", content: "Current state of the support platform." },
    ],
  }),
  component: OverviewPage,
});

const RANGES = [
  { id: 7, label: "7d" },
  { id: 14, label: "14d" },
  { id: 30, label: "30d" },
] as const;

/** Rows visible in the two roster panels before paging. Keeps both cards the same height as the
 *  chart card beside them, so the band reads as one row rather than three stacked boxes. */
const PANEL_PAGE_SIZE = 5;

function OverviewPage() {
  const { session } = RootRoute.useRouteContext();
  const isAdmin = session !== null && hasRank(session, "administrateur");

  const [days, setDays] = useState<number>(7);

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

  /**
   * The trend that restores this page's chart.
   *
   * Deliberately the SAME query key /analytics uses, so moving between the two screens is a cache
   * hit rather than a second fetch of a byte-identical response. `keepPreviousData` keeps the
   * curve on screen while a new window loads, so switching 7d/30d dissolves instead of blanking.
   */
  const trend = useQuery({
    queryKey: analyticsKeys.trend(days),
    queryFn: () => getAnalyticsTrend({ data: { days } }),
    placeholderData: keepPreviousData,
  });

  const daily = trend.data?.daily ?? [];
  /** Sessions per day, for the sparkline on the lead KPI. */
  const sessionSeries = daily.map((point) => point.current);

  return (
    <>
      {/* ================= Band 1 — support performance ================= */}
      <PageSection index={0}>
        <SectionHeading
          title="Support performance"
          hint="All-time, across every recorded session"
          icon={Gauge}
        />

        <MetricRow>
          {kpis.isPending ? (
            <>
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </>
          ) : kpis.isError ? (
            <div className="md:col-span-2 xl:col-span-4">
              <Card>
                <ErrorState error={kpis.error} onRetry={() => void kpis.refetch()} />
              </Card>
            </div>
          ) : (
            <>
              {/*
               * The reference card shape: icon + label, a dominant number, then the two figures
               * that qualify it under a rule, with the corner action linking to the page that
               * owns the detail.
               *
               * These remain all-time figures with no prior period on the wire, so no card here
               * shows a delta. The sparkline on the lead card is the WINDOWED session trend, and
               * its context line says so.
               */}
              <MetricCard
                label="Total sessions"
                value={formatCompact(kpis.data.total_sessions)}
                context="All sessions ever recorded"
                icon={MessagesSquare}
                to="/calls"
                actionLabel="Open calls and transcripts"
                {...(sessionSeries.length >= 2 ? { series: sessionSeries } : {})}
                footer={[
                  { label: "Resolved", value: formatInteger(kpis.data.resolved) },
                  { label: "Escalated", value: formatInteger(kpis.data.escalated) },
                ]}
              />
              <MetricCard
                label="Containment rate"
                value={formatRatio(kpis.data.containment_rate)}
                context={rateContext(kpis.data, "Resolved without escalation")}
                icon={CheckCircle2}
                footer={[
                  { label: "Resolved", value: formatInteger(kpis.data.resolved) },
                  { label: "Of total", value: formatCompact(kpis.data.total_sessions) },
                ]}
              />
              <MetricCard
                label="Escalation rate"
                value={formatRatio(kpis.data.escalation_rate)}
                context={rateContext(kpis.data, "Handed to an advisor")}
                icon={ShieldAlert}
                to="/escalations"
                actionLabel="Open escalations"
                footer={[
                  { label: "Escalated", value: formatInteger(kpis.data.escalated) },
                  { label: "Of total", value: formatCompact(kpis.data.total_sessions) },
                ]}
              />
              <MetricCard
                label="Avg. frustration"
                value={kpis.data.avg_frustration.toFixed(2)}
                context="Mean peak frustration per session"
                icon={Frown}
                footer={[
                  { label: "Scale", value: "0–10" },
                  { label: "Measured", value: "Peak per call" },
                ]}
              />
            </>
          )}
        </MetricRow>
      </PageSection>

      {/* ================= Band 2 — volume trend + verdict mix ================= */}
      <PageSection index={1}>
        <SectionHeading
          title="Volume & policy"
          hint={trend.data ? `Daily sessions, ${trend.data.timezone}` : undefined}
          icon={BarChart3}
        />

        <div className="grid gap-sp-6 xl:grid-cols-[1.6fr_1fr]">
          {/* ---- The curve this page lost ---- */}
          <Card padded={false} className="overflow-hidden">
            <div className="relative">
              <div className="p-sp-7">
                <CardHeader
                  title="Volume trend"
                  subtitle="Sessions per day against the preceding period of equal length."
                  icon={Activity}
                  action={
                    <div className="flex flex-wrap items-center justify-end gap-sp-5">
                      <Legend
                        items={[{ label: "This period", strong: true }, { label: "Previous" }]}
                      />
                      <Segmented
                        groupId="overview-range"
                        items={RANGES.map((range) => range.label)}
                        active={RANGES.find((range) => range.id === days)!.label}
                        onSelect={(label) =>
                          setDays(RANGES.find((range) => range.label === label)!.id)
                        }
                      />
                    </div>
                  }
                />
              </div>
              {/* Switching the window keeps the old curve and dims it, rather than collapsing
               * the card to a skeleton and bouncing the whole band. */}
              <TopProgress active={trend.isFetching} className="absolute inset-x-0 top-0" />
            </div>

            <div className="px-sp-7 pb-sp-7">
              {trend.isPending ? (
                <div className="h-[220px] rounded-r-3 bg-surface-3/40" aria-hidden="true" />
              ) : trend.isError ? (
                <ErrorState error={trend.error} onRetry={() => void trend.refetch()} />
              ) : isChartable(daily) ? (
                <div
                  className={
                    trend.isFetching ? "opacity-60 transition-opacity" : "transition-opacity"
                  }
                >
                  <LineChart
                    data={daily.map((point) => ({
                      day: dayLabel(point.day),
                      current: point.current,
                      previous: point.previous,
                    }))}
                  />
                </div>
              ) : (
                <EmptyState
                  icon={BarChart3}
                  compact
                  title="Not enough data"
                  description={`No sessions were recorded in the last ${days} days.`}
                />
              )}
            </div>
          </Card>

          {/* ---- Verdict mix: one metric split three ways, not three metrics ---- */}
          <Card className="flex flex-col">
            <CardHeader
              title="Policy verdicts"
              subtitle="Share of the most recent 100 decisions."
              icon={Scale}
            />

            <div className="mt-sp-7 flex-1">
              {verdicts.isPending ? (
                <div className="space-y-sp-5" role="status">
                  <span className="sr-only">Loading</span>
                  <span className="shimmer block h-[10px] rounded-r-1" />
                  <span className="shimmer block h-[10px] w-[70%] rounded-r-1" />
                  <span className="shimmer block h-[10px] w-[45%] rounded-r-1" />
                </div>
              ) : verdicts.isError ? (
                <ErrorState error={verdicts.error} onRetry={() => void verdicts.refetch()} />
              ) : (
                (() => {
                  const mix = verdicts.data.verdict_distribution;
                  const total = verdictTotal(mix);
                  return (
                    <>
                      <ShareBar
                        total={total}
                        parts={[
                          { label: "Authorized", value: mix.authorized },
                          { label: "Refused", value: mix.refused },
                          // Escalations are the ones a human has to act on, so they carry the
                          // strong weight — emphasis by weight, never by hue.
                          { label: "Escalated", value: mix.escalated, strong: true },
                        ]}
                      />
                      <p className="t-caption mt-sp-7 border-t border-stroke-subtle pt-sp-5 text-ink-5">
                        {total === 0
                          ? "The policy engine has not recorded a verdict yet."
                          : `${formatInteger(total)} verdicts in the window.`}
                      </p>
                    </>
                  );
                })()
              )}
            </div>
          </Card>
        </div>
      </PageSection>

      {/* ================= Band 3 — the floor ================= */}
      <PageSection index={2}>
        <SectionHeading
          title="On the floor"
          hint="Who is available, and what is deployed"
          icon={Users}
        />

        <div className="grid gap-sp-6 xl:grid-cols-2">
          <AdvisorPanel query={advisors} />
          <ServiceCatalogPanel query={system} />
        </div>
      </PageSection>

      {/* ================= Band 4 — runtime health ================= */}
      <PageSection index={3}>
        <SectionHeading title="Runtime" hint="Server-side probes" icon={Zap} />
        <ServiceHealthPanel isAdmin={isAdmin} />
      </PageSection>

      {/* ================= Band 5 — platform totals ================= */}
      <PageSection index={4}>
        <SectionHeading
          title="Platform totals"
          hint={`Cumulative records held by ${BRAND.name}`}
          icon={Database}
        />

        <MetricRow>
          {system.isPending ? (
            <>
              <CardSkeleton lines={2} />
              <CardSkeleton lines={2} />
              <CardSkeleton lines={2} />
              <CardSkeleton lines={2} />
            </>
          ) : system.isError ? (
            <div className="md:col-span-2 xl:col-span-4">
              <Card>
                <ErrorState error={system.error} onRetry={() => void system.refetch()} />
              </Card>
            </div>
          ) : (
            <>
              <MetricCard
                label="Customers"
                value={formatInteger(system.data.metrics.total_customers)}
                context="Records in the CRM"
                icon={Users}
                to="/customers"
                actionLabel="Open customers"
              />
              <MetricCard
                label="Turns"
                value={formatCompact(system.data.metrics.total_turns)}
                context="Transcript turns persisted"
                icon={MessagesSquare}
                to="/calls"
                actionLabel="Open calls and transcripts"
              />
              <MetricCard
                label="Actions"
                value={formatInteger(system.data.metrics.total_actions)}
                context="Entries in the action ledger"
                icon={Boxes}
                to="/decisions"
                actionLabel="Open decisions"
              />
              <MetricCard
                label="Audit entries"
                value={formatCompact(system.data.metrics.total_audit_entries)}
                context="Hash-chained audit records"
                icon={Database}
                to="/audit"
                actionLabel="Open audit"
              />
            </>
          )}
        </MetricRow>
      </PageSection>
    </>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Roster panels
 *
 * Both used to render EVERY row, so a 40-advisor estate produced a 2 000px card sitting beside a
 * 400px one. They now page at PANEL_PAGE_SIZE, which keeps the two cards the same height as each
 * other and removes the page's longest scroll.
 * ------------------------------------------------------------------------------------------- */

function PanelFrame({
  title,
  subtitle,
  icon,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <Card padded={false} className="flex flex-col overflow-hidden">
      <div className="p-sp-7">
        <CardHeader title={title} subtitle={subtitle} icon={icon} />
      </div>
      <div className="flex-1">{children}</div>
      {footer ? (
        <div className="border-t border-stroke-subtle px-sp-7 py-sp-5">{footer}</div>
      ) : null}
    </Card>
  );
}

function AdvisorPanel({
  query,
}: {
  query: ReturnType<typeof useQuery<Awaited<ReturnType<typeof listAdvisors>>>>;
}) {
  const [page, setPage] = useState(0);

  const rows = query.data ?? [];
  const visible = slicePage(rows, page, PANEL_PAGE_SIZE);

  return (
    <PanelFrame
      title="Team availability"
      subtitle="Advisors currently on the floor."
      icon={Users}
      footer={
        rows.length > 0 ? (
          <Pager
            page={page}
            pageSize={PANEL_PAGE_SIZE}
            total={rows.length}
            onPageChange={setPage}
            noun="advisors"
          />
        ) : null
      }
    >
      {query.isPending ? (
        <div className="px-sp-7 pb-sp-7">
          <CardSkeleton lines={4} />
        </div>
      ) : query.isError ? (
        <div className="px-sp-7 pb-sp-7">
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Users}
          compact
          title="No advisors"
          description="Register an advisor to see availability here."
        />
      ) : (
        <PageSwap pageKey={page}>
          <ul>
            {visible.map((advisor) => (
              <li
                key={advisor.id}
                className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5 transition-colors duration-[120ms] hover:bg-surface-3/50"
              >
                <Avatar initials={initials(advisor.full_name)} name={advisor.full_name} />
                <div className="min-w-0">
                  <p className="t-ui truncate text-ink-1">{advisor.full_name}</p>
                  <p className="t-caption inline-flex items-center gap-sp-3 text-ink-4">
                    <PresenceDot live={advisorStatusKey(advisor) === "online"} />
                    {advisorPresenceLabel(advisor.status)}
                  </p>
                </div>
                <span className="t-label ml-auto shrink-0 text-ink-3">
                  {advisor.language ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </PageSwap>
      )}
    </PanelFrame>
  );
}

function ServiceCatalogPanel({
  query,
}: {
  query: ReturnType<typeof useQuery<Awaited<ReturnType<typeof getSystemOverview>>>>;
}) {
  const [page, setPage] = useState(0);

  const rows = query.data?.services ?? [];
  const visible = slicePage(rows, page, PANEL_PAGE_SIZE);

  return (
    <PanelFrame
      title="Service catalog"
      subtitle="Services reported by system overview and the domain each owns. Runtime health is not reported here."
      icon={Boxes}
      footer={
        rows.length > 0 ? (
          <Pager
            page={page}
            pageSize={PANEL_PAGE_SIZE}
            total={rows.length}
            onPageChange={setPage}
            noun="services"
          />
        ) : null
      }
    >
      {query.isPending ? (
        <div className="px-sp-7 pb-sp-7">
          <CardSkeleton lines={4} />
        </div>
      ) : query.isError ? (
        <div className="px-sp-7 pb-sp-7">
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Boxes}
          compact
          title="No services reported"
          description="System overview returned an empty service inventory."
        />
      ) : (
        <PageSwap pageKey={page}>
          <ul>
            {visible.map((service) => (
              <li
                key={`${service.name}-${service.port}`}
                className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5 transition-colors duration-[120ms] hover:bg-surface-3/50"
              >
                <div className="min-w-0">
                  <p className="t-ui truncate text-ink-1">{service.name}</p>
                  <p className="t-caption truncate text-ink-4">{service.domain}</p>
                </div>
                <Token className="ml-auto shrink-0">{service.port}</Token>
              </li>
            ))}
          </ul>
        </PageSwap>
      )}
    </PanelFrame>
  );
}
