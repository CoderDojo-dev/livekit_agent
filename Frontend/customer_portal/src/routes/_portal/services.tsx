import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchProfile360 } from "@/lib/api/me.server";
import { fetchBalance, type BalanceItem, type RechargeItem } from "@/lib/api/billing.server";
import { date, dateTime, money, quantity } from "@/lib/format";
import {
  CreditCard,
  Globe,
  Hash,
  Layers2,
  MessageSquare,
  PhoneCall,
  Signal,
  Smartphone,
  Store,
  Wallet,
  Wifi,
  type LucideIcon,
} from "lucide-react";
import { Card, IconFrame, StatusChip } from "@/components/portal/primitives";
import { DataSection, MetricTile, PageSection } from "@/components/portal/data";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: pageTitle("Services") },
      {
        name: "description",
        content: "See your plan, your credit, and what you have left on each balance.",
      },
      { property: "og:title", content: brand.name },
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

/* One glyph per balance type and one per top-up channel. Neither map invents a
 * category: the keys are exactly the union members the API declares, so a new
 * enum value fails the build here instead of silently rendering nothing. */
const BALANCE_ICON: Record<BalanceItem["balance_type"], LucideIcon> = {
  main: Wallet,
  data: Wifi,
  voice: PhoneCall,
  sms: MessageSquare,
};

const CHANNEL_ICON: Record<RechargeItem["channel"], LucideIcon> = {
  app: Smartphone,
  web: Globe,
  ussd: Hash,
  scratch_card: CreditCard,
  agent: Store,
};

const RECHARGE_TONE: Record<RechargeItem["status"], "outline" | "dashed" | "muted"> = {
  completed: "outline",
  pending: "dashed",
  failed: "muted",
};

/**
 * True when an allowance runs out inside seven days.
 *
 * The chip this drives is the only thing on the screen that tells a customer
 * something is about to happen rather than reporting what already has. It is
 * derived from the same `expires_on` already printed under the figure, so it
 * can never disagree with the date beside it.
 */
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function expiringSoon(iso: string | null): boolean {
  if (!iso) return false;
  const at = new Date(iso).getTime();
  if (Number.isNaN(at)) return false;
  const delta = at - Date.now();
  return delta > 0 && delta <= WEEK_MS;
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
      <PageSection index={0}>
        <Card>
          <div className="grid gap-sp-7 sm:grid-cols-3">
            <MetricTile
              icon={Wallet}
              label={copy.services.tiles.credit}
              value={main ? balanceValue(main) : copy.common.notApplicable}
              hint={main?.expires_on ? copy.services.expires(date(main.expires_on)) : undefined}
              size="xl"
              pending={balanceQuery.isPending}
            />
            <MetricTile
              icon={Signal}
              label={copy.services.tiles.lines}
              value={String(activeLines)}
              hint={
                subscriptions.length > activeLines
                  ? copy.services.tiles.linesHint(subscriptions.length)
                  : undefined
              }
              // Active out of total: both numbers come from the subscriptions
              // array already rendered below, so the bar cannot drift from it.
              share={
                subscriptions.length > 0
                  ? { value: activeLines, of: subscriptions.length }
                  : undefined
              }
              size="l"
              pending={profileQuery.isPending}
            />
            <MetricTile
              icon={Layers2}
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
        index={1}
        icon={Layers2}
      >
        {(items) => (
          <div className="grid gap-sp-5 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((sub) => (
              /* The plan NAME used to be set in t-metric-l - 26px, the size
                 reserved for a headline figure. A plan is called "Smart 40",
                 not 26 point: at that weight it out-shouted the credit tile,
                 which is the only number on the page that matters. t-title-2
                 puts it back where a name belongs. */
              <Card key={sub.subscription_id} interactive className="group p-sp-7">
                <div className="flex items-start gap-sp-5">
                  <IconFrame icon={Layers2} />
                  <div className="min-w-0 flex-1">
                    <div className="t-title-2 truncate text-ink-1">{sub.plan ?? "—"}</div>
                    <div className="t-mono-s mt-sp-3 text-ink-5">{sub.msisdn ?? "—"}</div>
                  </div>
                  {sub.status ? (
                    <StatusChip
                      tone={sub.status === "active" ? "solid" : "muted"}
                      live={sub.status === "active"}
                    >
                      {sub.status}
                    </StatusChip>
                  ) : null}
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
        index={2}
        icon={Wallet}
      >
        {(items) => (
          <div className="grid gap-sp-5 sm:grid-cols-2">
            {items.map((b, i) => {
              const soon = expiringSoon(b.expires_on);
              return (
                <div
                  key={b.msisdn + b.balance_type + i}
                  className="card-lift group rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-6"
                >
                  <div className="flex items-center justify-between gap-sp-5">
                    <span className="flex min-w-0 items-center gap-sp-4">
                      <IconFrame icon={BALANCE_ICON[b.balance_type]} size="sm" />
                      <span className="t-micro-2 truncate text-ink-5">
                        {copy.labels.balanceType[b.balance_type]}
                      </span>
                    </span>
                    <StatusChip tone={b.status === "active" ? "outline" : "muted"}>
                      {b.status}
                    </StatusChip>
                  </div>
                  {/* t-metric-m, not t-metric-l: money() prints "TND 25.500"
                      and quantity() prints "12.40 GB" - long strings that ran
                      to two lines at 26px on a phone. */}
                  <div className="t-metric-m mt-sp-5 truncate text-ink-1">{balanceValue(b)}</div>
                  <div className="mt-sp-3 flex flex-wrap items-center gap-sp-4">
                    <span className="t-caption text-ink-4">
                      {b.msisdn ?? "—"}
                      {b.expires_on ? ` · ${copy.services.expires(date(b.expires_on))}` : ""}
                    </span>
                    {soon ? (
                      <StatusChip tone="dashed">{copy.services.expiringSoon}</StatusChip>
                    ) : null}
                  </div>
                </div>
              );
            })}
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
        index={3}
        icon={CreditCard}
      >
        {(items) => (
          <ul className="divide-y divide-stroke-subtle">
            {items.map((r, i) => (
              <li
                key={(r.msisdn ?? "na") + (r.created_at ?? "na") + i}
                className="group flex items-center gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
              >
                {/* The channel was buried in the caption as a word. As a glyph
                    it is scannable down the column: five top-ups from the app
                    and one from a shop is readable at a glance now. */}
                <IconFrame icon={CHANNEL_ICON[r.channel]} />
                <div className="min-w-0 flex-1">
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
                <div className="flex shrink-0 flex-col items-end gap-sp-2">
                  <StatusChip tone={RECHARGE_TONE[r.status] ?? "muted"}>
                    {copy.labels.rechargeStatus[r.status] ?? r.status}
                  </StatusChip>
                  <div className="t-mono-s text-ink-5">{dateTime(r.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataSection>
    </div>
  );
}
