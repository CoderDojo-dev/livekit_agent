import { useQuery } from "@tanstack/react-query";
import { Activity, ShieldCheck } from "lucide-react";
import { Button, Card, CardHeader, EmptyState, StatusChip, Token } from "./primitives";
import { CardSkeleton, ErrorState, InlineError } from "./states";
import { getServiceHealth, type ServiceHealthStatus } from "@/lib/api/service-health.server";
import { queryKeys } from "@/lib/nexus/query-keys";

const LABEL: Record<ServiceHealthStatus, string> = {
  reachable: "Reachable",
  degraded: "Degraded",
  unavailable: "Unavailable",
  unknown: "Unknown",
};

export function ServiceHealthPanel({ isAdmin }: { isAdmin: boolean }) {
  const health = useQuery({
    queryKey: queryKeys.serviceHealth,
    queryFn: () => getServiceHealth(),
    enabled: isAdmin,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });

  if (!isAdmin)
    return (
      <Card>
        <EmptyState
          icon={ShieldCheck}
          title="Service health restricted"
          description="Runtime topology is visible only to administrators."
        />
      </Card>
    );
  if (health.isPending) return <CardSkeleton />;
  if (health.isError && !health.data)
    return (
      <Card>
        <ErrorState error={health.error} onRetry={() => void health.refetch()} />
      </Card>
    );
  if (!health.data || health.data.services.length === 0)
    return (
      <Card>
        <CardHeader
          title="Platform service health"
          subtitle="Server-side, bounded health probes."
        />
        <EmptyState
          icon={Activity}
          title="No probes configured"
          description="Configure SERVICE_HEALTH_TARGETS on business-api; no service is assumed healthy."
        />
      </Card>
    );
  const stale = Date.now() - new Date(health.data.checked_at).getTime() > 120_000;
  return (
    <Card padded={false}>
      <div className="p-sp-7">
        <CardHeader
          title="Platform service health"
          subtitle={`Checked ${new Date(health.data.checked_at).toLocaleString()} ┬╖ ${health.data.timeout_ms} ms probe budget`}
          action={
            <div className="flex items-center gap-sp-3">
              <StatusChip status={health.data.overall} />
              <Button size="sm" onClick={() => void health.refetch()} disabled={health.isFetching}>
                {health.isFetching ? "Checking..." : "Refresh"}
              </Button>
            </div>
          }
        />
        {stale ? (
          <p className="t-caption mt-sp-3 text-ink-3">
            Stale snapshot ΓÇö refresh before acting on it.
          </p>
        ) : null}
        {health.isError ? (
          <div className="mt-sp-3">
            <InlineError error={health.error} />
          </div>
        ) : null}
      </div>
      <ul>
        {health.data.services.map((service) => (
          <li
            key={service.name}
            className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
          >
            <div className="min-w-0">
              <p className="t-ui truncate text-ink-1">{service.name}</p>
              <p className="t-caption truncate text-ink-4">
                {service.domain} ┬╖ {service.configured ? "configured" : "configuration invalid"} ┬╖{" "}
                {service.required ? "required" : "optional"}
              </p>
            </div>
            <Token className="ml-auto">
              {service.latency_ms === null ? "ΓÇö" : `${service.latency_ms} ms`}
            </Token>
            <StatusChip status={service.status} />
            <span className="sr-only">
              {LABEL[service.status]}: {service.reason}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
