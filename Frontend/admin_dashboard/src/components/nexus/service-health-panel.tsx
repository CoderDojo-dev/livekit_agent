import { useQuery } from "@tanstack/react-query";
import { Activity, ShieldCheck } from "lucide-react";
import { Button, Card, CardHeader, EmptyState, StatusChip, Token } from "./primitives";
import { CardSkeleton, ErrorState, InlineError } from "./states";
import {
  getServiceHealth,
  type ServiceHealthProbeKind,
  type ServiceHealthStatus,
} from "@/lib/api/service-health.server";
import { queryKeys } from "@/lib/nexus/query-keys";

const STATUS_LABEL: Record<ServiceHealthStatus, string> = {
  reachable: "Reachable",
  degraded: "Degraded",
  unavailable: "Unavailable",
  unknown: "Unknown",
};

const PROBE_LABEL: Record<ServiceHealthProbeKind, string> = {
  liveness: "liveness probe",
  readiness: "readiness probe",
  none: "no probe",
};

export function ServiceHealthPanel({ isAdmin }: { isAdmin: boolean }) {
  const health = useQuery({
    queryKey: queryKeys.serviceHealth,
    queryFn: () => getServiceHealth(),
    enabled: isAdmin,
    retry: 1,
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
          subtitle={`Checked ${new Date(health.data.checked_at).toLocaleString()} / ${health.data.probe_timeout_ms} ms probe budget`}
          action={
            <div className="flex items-center gap-sp-3">
              <StatusChip status={health.data.overall} />
              <Button size="sm" onClick={() => void health.refetch()} disabled={health.isFetching}>
                {health.isFetching ? "Checking..." : "Refresh"}
              </Button>
            </div>
          }
        />
        <p
          aria-live="polite"
          aria-busy={health.isFetching}
          className="t-caption mt-sp-3 text-ink-3"
        >
          {health.isFetching
            ? "Refreshing service health"
            : `Service health ${STATUS_LABEL[health.data.overall]} — business-api liveness ${health.data.business_api_liveness.status} (${health.data.business_api_liveness.reason})`}
        </p>
        {stale ? (
          <p className="t-caption mt-sp-3 text-ink-3">
            Stale snapshot — refresh before acting on it.
          </p>
        ) : null}
        {health.isError ? (
          <div className="mt-sp-3">
            <InlineError error={health.error} />
          </div>
        ) : null}
      </div>
      {/* Four rows visible, the rest reachable by scrolling INSIDE the card.
       * A 12-service estate previously rendered 12 rows inline and made this the tallest block
       * on Overview. `overscroll-contain` keeps a wheel that hits the end from scrolling the
       * page behind it. */}
      <ul className="max-h-[264px] overflow-y-auto overscroll-contain">
        {health.data.services.map((service) => (
          <li
            key={service.id}
            className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
          >
            <div className="min-w-0">
              <p className="t-ui truncate text-ink-1">{service.name}</p>
              {/* Was: "domain / monitoring configured / liveness probe / required" plus a raw
               * `reason` string on a second line — four machine facts stacked under every row,
               * which turned a 12-service list into a wall of text.
               *
               * The domain is the one thing that identifies the service to a human. Everything
               * else moves into the title attribute: still available on hover and to a screen
               * reader, no longer competing for the row. */}
              <p className="t-caption truncate text-ink-4" title={diagnostics(service)}>
                {service.domain}
                {service.required ? null : " · optional"}
              </p>
              {/*
               * The reason is shown only when the service is NOT reachable.
               *
               * On a healthy row it read "probe_succeeded" — a machine token restating what the
               * status chip beside it already says, on every row, which is what made the panel
               * feel so noisy. When something is actually wrong, WHY is the whole point, so it
               * gets its own line rather than hiding in a tooltip.
               */}
              {service.monitoring_configured && service.status !== "reachable" ? (
                <p className="t-mono-s mt-sp-2 truncate text-ink-3">{service.reason}</p>
              ) : null}
            </div>
            <Token className="ml-auto shrink-0">
              {service.latency_ms === null ? "—" : `${service.latency_ms} ms`}
            </Token>
            {service.monitoring_configured ? (
              <StatusChip status={service.status} className="shrink-0" />
            ) : (
              <span className="t-caption shrink-0 text-ink-5">Not monitored</span>
            )}
            <span className="sr-only">
              {service.monitoring_configured
                ? `${STATUS_LABEL[service.status]}. ${diagnostics(service)}`
                : `Monitoring not configured. ${diagnostics(service)}`}
            </span>
          </li>
        ))}
      </ul>
      {health.data.services.length > 4 ? (
        <p className="t-caption border-t border-stroke-subtle px-sp-7 py-sp-4 text-ink-5">
          {health.data.services.length} services · scroll for the rest
        </p>
      ) : null}
    </Card>
  );
}

/**
 * The machine detail, assembled once for the row's tooltip and its screen-reader text.
 * Kept verbatim — it is diagnostic data and must not be paraphrased — just moved off the surface.
 */
function diagnostics(service: {
  domain: string;
  monitoring_configured: boolean;
  probe_kind: ServiceHealthProbeKind;
  required: boolean;
  reason: string;
}): string {
  return [
    service.domain,
    service.monitoring_configured ? "monitoring configured" : "monitoring not configured",
    PROBE_LABEL[service.probe_kind],
    service.required ? "required" : "optional",
    service.reason,
  ]
    .filter(Boolean)
    .join(" · ");
}
