import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchBalance, fetchBilling, type InvoiceItem } from "@/lib/api/billing.server";
import { errorMessage } from "@/lib/api/errors";
import { date, dateTime, money, quantity } from "@/lib/format";
import { Button, Card, SectionLabel, StatusChip } from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/billing")({
  head: () => ({
    meta: [
      { title: "Billing — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Your next Nexus charge, your payment method, six months of spend, and every invoice available as a PDF.",
      },
      { property: "og:title", content: "Billing — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Invoices, payment methods, and what is coming next — explained line by line.",
      },
    ],
  }),
  component: BillingScreen,
});

const INVOICE_TONE: Record<
  InvoiceItem["status"],
  "solid" | "outline" | "dashed" | "dotted" | "muted"
> = {
  draft: "muted",
  issued: "dashed",
  paid: "outline",
  partial: "dashed",
  overdue: "solid",
  disputed: "dotted",
  void: "muted",
};

function BillingScreen() {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const billingQuery = useQuery({
    queryKey: qk.billing(cid),
    queryFn: () => fetchBilling(),
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(cid),
    queryFn: () => fetchBalance(),
    staleTime: 30_000,
  });

  if (billingQuery.isPending || balanceQuery.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading your billing…</p>
      </Card>
    );
  }

  if (billingQuery.isError || !billingQuery.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(billingQuery.error)}
        </p>
        <Button variant="secondary" className="mt-sp-6" onClick={() => void billingQuery.refetch()}>
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  const billing = billingQuery.data;
  const balance = balanceQuery.data ?? { balances: [], recharges: [] };
  const hasAccounts = billing.accounts.length > 0;
  const hasBalances = balance.balances.length > 0;

  return (
    <div className="space-y-sp-10">
      {hasAccounts && (
        <>
          <div className="grid gap-sp-7 lg:grid-cols-[minmax(0,1fr)_360px]">
            <section className="space-y-sp-6">
              <SectionLabel>{copy.billing.amountDue}</SectionLabel>
              <Card>
                <div className="flex items-end justify-between gap-sp-6">
                  <div>
                    <div className="t-metric-xl text-ink-1">
                      {money(billing.total_outstanding, billing.currency_code)}
                    </div>
                    <div className="t-caption mt-sp-2 text-ink-4">{billing.currency_code}</div>
                  </div>
                  <StatusChip tone="outline">
                    {billing.total_outstanding > 0 ? "OUTSTANDING" : "CLEARED"}
                  </StatusChip>
                </div>
              </Card>
            </section>

            <section className="space-y-sp-6">
              <SectionLabel>{copy.billing.accounts}</SectionLabel>
              <Card>
                <ul className="space-y-sp-5">
                  {billing.accounts.map((a) => (
                    <li
                      key={a.account_number}
                      className="flex items-center justify-between gap-sp-5"
                    >
                      <div className="min-w-0">
                        <div className="t-mono text-ink-1">{a.account_number}</div>
                        <div className="t-caption text-ink-5">
                          {a.account_type} · cycle day {a.billing_cycle_day ?? "—"}
                        </div>
                      </div>
                      <StatusChip tone="muted">{a.status}</StatusChip>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          </div>

          <section className="space-y-sp-6">
            <SectionLabel>{copy.billing.invoices}</SectionLabel>
            {billing.invoices.length === 0 ? (
              <Card>
                <p className="t-caption text-ink-5">{copy.empty.generic}</p>
              </Card>
            ) : (
              <div className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-stroke-subtle">
                      {["INVOICE", "PERIOD", "DUE", "AMOUNT", "STATUS"].map((h) => (
                        <th
                          key={h}
                          className="t-micro-2 px-sp-7 py-sp-5 text-left font-semibold text-ink-5"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {billing.invoices.map((inv) => (
                      <tr
                        key={inv.invoice_number}
                        className="border-b border-stroke-subtle transition-colors duration-200 last:border-b-0 hover:bg-surface-2"
                      >
                        <td className="t-mono px-sp-7 py-sp-6 text-ink-2">{inv.invoice_number}</td>
                        <td className="t-ui px-sp-7 py-sp-6 text-ink-1">
                          {inv.period_start && inv.period_end
                            ? `${date(inv.period_start)} – ${date(inv.period_end)}`
                            : "—"}
                        </td>
                        <td className="t-mono px-sp-7 py-sp-6 text-ink-4">{date(inv.due_date)}</td>
                        <td className="t-mono px-sp-7 py-sp-6 text-ink-1">
                          {money(inv.total_amount, inv.currency_code)}
                        </td>
                        <td className="px-sp-7 py-sp-6">
                          <StatusChip tone={INVOICE_TONE[inv.status]}>
                            {copy.labels.invoiceStatus[inv.status] ?? inv.status}
                          </StatusChip>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="space-y-sp-6">
            <SectionLabel>{copy.billing.payments}</SectionLabel>
            {billing.payments.length === 0 ? (
              <Card>
                <p className="t-caption text-ink-5">{copy.empty.generic}</p>
              </Card>
            ) : (
              <Card>
                <ul className="divide-y divide-stroke-subtle">
                  {billing.payments.map((p, i) => (
                    <li
                      key={`${p.invoice_number}-${i}`}
                      className="flex items-center justify-between gap-sp-5 py-sp-5 first:pt-0 last:pb-0"
                    >
                      <div className="min-w-0">
                        <div className="t-body-strong text-ink-1">
                          {money(p.amount, p.currency_code)}
                        </div>
                        <div className="t-caption text-ink-5">
                          {p.method ?? "—"} · {p.invoice_number ?? "—"}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="t-ui text-ink-3">{p.status}</div>
                        <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(p.paid_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>
        </>
      )}

      {hasBalances && (
        <>
          <section className="space-y-sp-6">
            <SectionLabel>{copy.billing.balances}</SectionLabel>
            <div className="grid gap-sp-6 sm:grid-cols-2">
              {balance.balances.map((b, i) => (
                <Card key={`${b.msisdn}-${b.balance_type}-${i}`}>
                  <div className="flex items-center justify-between gap-sp-5">
                    <div className="t-caption text-ink-5">{b.msisdn ?? "—"}</div>
                    <StatusChip tone={b.status === "active" ? "outline" : "muted"}>
                      {b.status}
                    </StatusChip>
                  </div>
                  <div className="t-metric-l mt-sp-5 text-ink-1">{quantity(b.value, b.unit)}</div>
                  <div className="t-caption mt-sp-2 text-ink-4">
                    {copy.labels.balanceType[b.balance_type] ?? b.balance_type}
                    {b.expires_on ? ` · expires ${date(b.expires_on)}` : ""}
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <section className="space-y-sp-6">
            <SectionLabel>{copy.billing.recharges}</SectionLabel>
            {balance.recharges.length === 0 ? (
              <Card>
                <p className="t-caption text-ink-5">{copy.empty.generic}</p>
              </Card>
            ) : (
              <Card>
                <ul className="divide-y divide-stroke-subtle">
                  {balance.recharges.map((r, i) => (
                    <li
                      key={`${r.msisdn}-${i}`}
                      className="flex items-center justify-between gap-sp-5 py-sp-5 first:pt-0 last:pb-0"
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
                        <div className="t-caption text-ink-5">
                          {r.msisdn ?? "—"} · {copy.labels.rechargeChannel[r.channel] ?? r.channel}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="t-ui text-ink-3">{r.status}</div>
                        <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(r.created_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>
        </>
      )}

      {!hasAccounts && !hasBalances && (
        <Card>
          <p className="t-caption text-ink-5">{copy.empty.generic}</p>
        </Card>
      )}
    </div>
  );
}
