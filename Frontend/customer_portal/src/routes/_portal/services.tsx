import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem, type RechargeItem } from "@/lib/api/billing.server";
import { date, dateTime, money, quantity } from "@/lib/format";
import { Card, StatusChip } from "@/components/portal/primitives";
import { DataSection, MetricTile, PageSection } from "@/components/portal/data";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: "Services — Nexus Customer Portal" },
      {
        name: "description",
        content: "See your Nexus plan, your credit, and what you have left on each balance.",
      },
      { property: "og:title", content: "Services — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your plan, your balances, and your recent top-ups in plain numbers.",
      },
    ],
  }),
  component: ServicesScreen,
});

/* Balance types in the order a customer thinks about them: money first, then
 * the bundles that money bought. Anything the OCS invents later sorts last
 * instead of vanishing - the version_94 data-only filter is exactly the bug
 * this ordering replaces. */
const BALANCE_ORDER: Array<BalanceItem["balance_type"]> = ["main", "data", "voice", "sms"];

function orderBalances(items: BalanceItem[]): BalanceItem[] {
  return [...items].sort((a, b) => {
    const ai = BALANCE_ORDER.indexOf(a.balance_type);
    const bi = BALANCE_ORDER.indexOf(b.balance_type);
    return (ai < 0 ? BALANCE_ORDER.length : ai) - (bi < 0 ? BALANCE_ORDER.length : bi);
  });
}

/** Main balance is currency; every other type is a metered quantity. */
function balanceValue(item: BalanceItem): string {
  return item.balance_type === "main" && item.unit === "TND"
    ? money(item.value, "TND")
    : quantity(item.value, item.unit);
}

function ServicesScreen() {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const profileQuery = useQuery({
    queryKey: qk.profile360(cid),
    queryFn: () => fetchProfile360(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(cid),
    queryFn: () => fetchBalance(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const subscriptions = profileQuery.data?.subscriptions ?? [];
  const balances = orderBalances(balanceQuery.data?.balances ?? []);
  const recharges = balanceQuery.data?.recharges ?? [];
  const main = balances.find((b) => b.balance_type === "main");
  const activeLines = subscriptions.filter((s) => s.status === "active").length;

  return (
    <div className="space-y-sp-9">
      <PageSection>
        <Card>
          <div className="grid gap-sp-7 sm:grid-cols-3">
            <MetricTile
              label={copy.services.tiles.credit}
              value={main ? balanceValue(main) : copy.common.notApplicable}
              hint={main?.expires_on ? copy.services.expires(date(main.expires_on)) : undefined}
              size="xl"
              pending={balanceQuery.isPending}
            />
            <MetricTile
              label={copy.services.tiles.lines}
              value={String(activeLines)}
              hint={
                subscriptions.length > activeLines
                  ? copy.services.tiles.linesHint(subscriptions.length)
                  : undefined
              }
              size="l"
              pending={profileQuery.isPending}
            />
            <MetricTile
              label={copy.services.tiles.plan}
              value={subscriptions[0]?.plan ?? copy.common.notApplicable}
              hint={subscriptions[0]?.msisdn ?? undefined}
              size="l"
              pending={profileQuery.isPending}
            />
          </div>
        </Card>
      </PageSection>

      <DataSection
        label={copy.services.plan}
        state={{
          isPending: profileQuery.isPending,
          isFetching: profileQuery.isFetching,
          isPlaceholderData: profileQuery.isPlaceholderData,
          error: profileQuery.error,
        }}
        items={subscriptions}
        skeletonRows={2}
        empty={{
          title: copy.services.subscriptionsEmpty.title,
          body: copy.services.subscriptionsEmpty.body,
        }}
        onRetry={() => void profileQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((sub) => (
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
      </DataSection>

      <DataSection<BalanceItem>
        label={copy.services.balances}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={balances}
        skeletonRows={3}
        empty={{
          title: copy.services.balancesEmpty.title,
          body: copy.services.balancesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <div className="grid gap-sp-6 sm:grid-cols-2">
            {items.map((b, i) => (
              <div
                key={b.msisdn + b.balance_type + i}
                className="rounded-r-3 border border-stroke-subtle p-sp-6"
              >
                <div className="flex items-center justify-between gap-sp-5">
                  <span className="t-micro-2 text-ink-5">
                    {copy.labels.balanceType[b.balance_type]}
                  </span>
                  <StatusChip tone={b.status === "active" ? "outline" : "muted"}>
                    {b.status}
                  </StatusChip>
                </div>
                <div className="t-metric-l mt-sp-5 text-ink-1">{balanceValue(b)}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {b.msisdn ?? "—"}
                  {b.expires_on ? ` · ${copy.services.expires(date(b.expires_on))}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </DataSection>

      <DataSection<RechargeItem>
        label={copy.services.recharges}
        state={{
          isPending: balanceQuery.isPending,
          isFetching: balanceQuery.isFetching,
          isPlaceholderData: balanceQuery.isPlaceholderData,
          error: balanceQuery.error,
        }}
        items={recharges}
        skeletonRows={3}
        empty={{
          title: copy.services.rechargesEmpty.title,
          body: copy.services.rechargesEmpty.body,
        }}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <ul className="divide-y divide-stroke-subtle">
            {items.map((r, i) => (
              <li
                key={(r.msisdn ?? "na") + (r.created_at ?? "na") + i}
                className="flex items-center justify-between gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <div className="t-body-strong text-ink-1">
                    {money(r.amount)}
                    {r.bonus_amount ? (
                      <span className="t-caption text-ink-4">
                        {" "}
                        {copy.billing.bonus(money(r.bonus_amount))}
                      </span>
                    ) : null}
                  </div>
                  <div className="t-caption mt-sp-1 truncate text-ink-5">
                    {r.msisdn ?? "—"} · {copy.labels.rechargeChannel[r.channel]}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="t-ui text-ink-3">{r.status}</div>
                  <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(r.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataSection>
    </div>
  );
}
