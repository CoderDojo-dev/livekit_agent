import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem } from "@/lib/api/billing.server";
import { errorMessage } from "@/lib/api/errors";
import { date, quantity } from "@/lib/format";
import { Button, Card, SectionLabel, StatusChip } from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: "Services — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "See your Nexus plan, what it includes, and how much of your allowance you have used.",
      },
      { property: "og:title", content: "Services — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your plan and your usage in plain numbers.",
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
      <Card>
        <p className="t-caption text-ink-5">Loading your plan…</p>
      </Card>
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(profileQuery.error)}
        </p>
        <Button variant="secondary" className="mt-sp-6" onClick={() => void profileQuery.refetch()}>
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  const subscriptions = profileQuery.data.subscriptions;
  const dataBalances = (balanceQuery.data?.balances ?? []).filter(isDataBalance);

  return (
    <div className="space-y-sp-10">
      <section className="space-y-sp-6">
        <SectionLabel>{copy.services.plan}</SectionLabel>
        {subscriptions.length === 0 ? (
          <Card>
            <p className="t-caption text-ink-5">{copy.empty.generic}</p>
          </Card>
        ) : (
          <Card>
            <ul className="divide-y divide-stroke-subtle">
              {subscriptions.map((sub) => (
                <li
                  key={sub.subscription_id}
                  className="flex flex-col gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
                >
                  <div className="flex flex-wrap items-center gap-sp-5">
                    <h3 className="t-metric-l text-ink-1">{sub.plan ?? "—"}</h3>
                    {sub.status ? <StatusChip tone="solid">{sub.status}</StatusChip> : null}
                  </div>
                  <div className="t-mono-s text-ink-5">{sub.msisdn ?? "—"}</div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {dataBalances.length > 0 && (
        <section className="space-y-sp-6">
          <SectionLabel>{copy.services.usage}</SectionLabel>
          <Card>
            <ul className="divide-y divide-stroke-subtle">
              {dataBalances.map((b, i) => (
                <li
                  key={`${b.msisdn}-${b.balance_type}-${i}`}
                  className="flex items-baseline justify-between gap-sp-5 py-sp-5 first:pt-0 last:pb-0"
                >
                  <span className="t-ui text-ink-2">
                    {b.msisdn ?? "—"} · {copy.labels.balanceType[b.balance_type] ?? b.balance_type}
                  </span>
                  <span className="t-mono text-ink-3">
                    {quantity(b.value, b.unit)}
                    {b.expires_on ? ` · expires ${date(b.expires_on)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
    </div>
  );
}
