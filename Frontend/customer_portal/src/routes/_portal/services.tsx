import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360, type Subscription360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem, type RechargeItem } from "@/lib/api/billing.server";
import { date, dateTime, money, quantity } from "@/lib/format";
import { Card, StatusChip } from "@/components/portal/primitives";
import { DataSection, MetricTile } from "@/components/portal/data";

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

// The API returns main credit, data, voice and SMS. Order is presentation
// priority, not API order.
const BALANCE_ORDER: Array<BalanceItem["balance_type"]> = ["main", "data", "voice", "sms"];

type BalanceGroup = {
  type: BalanceItem["balance_type"];
  label: string;
  items: BalanceItem[];
};

function groupBalances(items: BalanceItem[]): BalanceGroup[] {
  return BALANCE_ORDER.map((type) => ({
    type,
    label: copy.services.balanceTypes[type],
    items: items.filter((b) => b.balance_type === type),
  })).filter((group) => group.items.length > 0);
}

function balanceValue(item: BalanceItem): string {
  if (item.value == null) return "-";
  // TND is money and must carry the currency code; GB/MB/MIN/SMS are counts
  // and must not be formatted as money.
  return item.unit === "TND" ? money(item.value) : quantity(item.value, item.unit);
}

const BALANCE_TONE: Record<BalanceItem["status"], "outline" | "muted" | "dashed"> = {
  active: "outline",
  expired: "muted",
  suspended: "dashed",
};

const RECHARGE_TONE: Record<RechargeItem["status"], "dashed" | "outline" | "muted"> = {
  pending: "dashed",
  completed: "outline",
  failed: "muted",
};

function SubscriptionCards({ items }: { items: Subscription360[] }) {
  return (
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
  );
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

  // No early return. Each section owns its own pending and error state, so a
  // failing balance request can never hide the plan, and a slow profile can
  // never blank the page.
  const balances = balanceQuery.data?.balances ?? [];
  const recharges = balanceQuery.data?.recharges ?? [];
  const subscriptions = profileQuery.data?.subscriptions ?? [];
  const groups = groupBalances(balances);
  const credit = balances.find((b) => b.balance_type === "main");
  const data = balances.find((b) => b.balance_type === "data");
  const plan = subscriptions[0]?.plan;

  return (
    <div className="flex flex-col gap-sp-8">
      <div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile
          label={copy.services.tiles.credit}
          value={credit ? balanceValue(credit) : "-"}
          pending={balanceQuery.isPending}
        />
        <MetricTile
          label={copy.services.tiles.data}
          value={data ? balanceValue(data) : "-"}
          pending={balanceQuery.isPending}
        />
        <MetricTile
          label={copy.services.tiles.plan}
          value={plan ?? "-"}
          pending={profileQuery.isPending}
        />
      </div>

      <DataSection
        label={copy.services.balances}
        state={balanceQuery}
        items={groups}
        empty={copy.services.balancesEmpty}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(groups) => (
          <div className="flex flex-col gap-sp-6">
            {groups.map((group) => (
              <section key={group.type}>
                <h3 className="t-label text-ink-4">{group.label}</h3>
                <ul className="mt-sp-3 grid grid-cols-1 gap-sp-3 lg:grid-cols-2">
                  {group.items.map((item, i) => (
                    <li
                      key={`${item.msisdn ?? "na"}-${i}`}
                      className="portal-section flex items-baseline justify-between gap-sp-4"
                    >
                      <div className="min-w-0">
                        <p className="t-body-l text-ink-1">{balanceValue(item)}</p>
                        {item.msisdn ? <p className="t-caption text-ink-4">{item.msisdn}</p> : null}
                      </div>
                      <div className="text-right">
                        <StatusChip tone={BALANCE_TONE[item.status]}>
                          {copy.services.balanceStatus[item.status]}
                        </StatusChip>
                        {item.expires_on ? (
                          <p className="t-caption text-ink-4">
                            {copy.services.expires} {date(item.expires_on)}
                          </p>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </DataSection>

      <DataSection
        label={copy.services.subscriptions}
        state={profileQuery}
        items={subscriptions}
        empty={copy.services.subscriptionsEmpty}
        onRetry={() => void profileQuery.refetch()}
      >
        {(items) => <SubscriptionCards items={items} />}
      </DataSection>

      <DataSection
        label={copy.services.recharges}
        state={balanceQuery}
        items={recharges}
        empty={copy.services.rechargesEmpty}
        onRetry={() => void balanceQuery.refetch()}
      >
        {(items) => (
          <ul className="divide-y divide-stroke-subtle">
            {items.map((r, i) => (
              <li
                key={`${r.created_at ?? "na"}-${i}`}
                className="flex items-baseline justify-between gap-sp-4 py-sp-3"
              >
                <div className="min-w-0">
                  <p className="t-body text-ink-1">{money(r.amount ?? 0)}</p>
                  <p className="t-caption text-ink-4">
                    {copy.services.rechargeChannels[r.channel]}
                    {r.bonus_amount ? ` - includes ${money(r.bonus_amount)} bonus` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <StatusChip tone={RECHARGE_TONE[r.status]}>
                    {copy.services.rechargeStatus[r.status]}
                  </StatusChip>
                  <p className="t-caption text-ink-4">{dateTime(r.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataSection>
    </div>
  );
}
