import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem } from "@/lib/api/billing.server";
import { date, quantity } from "@/lib/format";
import { Card, StatusChip } from "@/components/portal/primitives";
import { ErrorState, PageSection, SkeletonList, SkeletonMetric } from "@/components/portal/data";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: "Services — Nexus Customer Portal" },
      {
        name: "description",
        content: "See your Nexus plan, and how much prepaid data you have left.",
      },
      { property: "og:title", content: "Services — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your plan and your balances in plain numbers.",
      },
    ],
  }),
  component: ServicesScreen,
});

function isDataBalance(balance: BalanceItem): boolean {
  return balance.balance_type === "data" && (balance.unit === "GB" || balance.unit === "MB");
}

function ServicesScreen() {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const profileQuery = useQuery({
    queryKey: qk.profile360(cid),
    queryFn: () => fetchProfile360(),
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(cid),
    queryFn: () => fetchBalance(),
    staleTime: 30_000,
  });

  if (profileQuery.isPending || balanceQuery.isPending) {
    return (
      <div className="space-y-sp-9">
        <PageSection label={copy.services.plan}>
          <Card>
            <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
              <SkeletonMetric />
              <SkeletonMetric />
              <SkeletonMetric />
            </div>
          </Card>
        </PageSection>
        <PageSection label={copy.services.balances}>
          <Card>
            <SkeletonList rows={3} />
          </Card>
        </PageSection>
      </div>
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <Card>
        <ErrorState error={profileQuery.error} onRetry={() => void profileQuery.refetch()} />
      </Card>
    );
  }

  const subscriptions = profileQuery.data.subscriptions;
  const dataBalances = (balanceQuery.data?.balances ?? []).filter(isDataBalance);

  return (
    <div className="space-y-sp-9">
      <PageSection label={copy.services.plan}>
        {subscriptions.length === 0 ? (
          <Card>
            <p className="t-caption text-ink-5">{copy.empty.generic}</p>
          </Card>
        ) : (
          <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
            {subscriptions.map((sub) => (
              <Card key={sub.subscription_id}>
                <div className="flex items-start justify-between gap-sp-5">
                  <div className="min-w-0">
                    <div className="t-metric-l truncate text-ink-1">{sub.plan ?? "—"}</div>
                    <div className="t-mono-s mt-sp-4 text-ink-5">{sub.msisdn ?? "—"}</div>
                  </div>
                  {sub.status ? <StatusChip tone="solid">{sub.status}</StatusChip> : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </PageSection>

      {dataBalances.length > 0 && (
        <PageSection label={copy.services.balances}>
          {balanceQuery.isError ? (
            <Card>
              <ErrorState error={balanceQuery.error} onRetry={() => void balanceQuery.refetch()} />
            </Card>
          ) : (
            <Card>
              <ul className="divide-y divide-stroke-subtle">
                {dataBalances.map((b, i) => (
                  <li
                    key={`${b.msisdn}-${b.balance_type}-${i}`}
                    className="flex items-baseline justify-between gap-sp-5 py-sp-5 first:pt-0 last:pb-0"
                  >
                    <span className="t-ui text-ink-2">
                      {b.msisdn ?? "—"} ·{" "}
                      {copy.labels.balanceType[b.balance_type] ?? b.balance_type}
                    </span>
                    <span className="t-mono text-ink-3">
                      {quantity(b.value, b.unit)}
                      {b.expires_on ? ` · expires ${date(b.expires_on)}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </PageSection>
      )}
    </div>
  );
}
