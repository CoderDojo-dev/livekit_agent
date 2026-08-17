import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchBalance, fetchBilling, type InvoiceItem } from "@/lib/api/billing.server";
import { date, dateTime, money, quantity } from "@/lib/format";
import {
  Card,
  Divider,
  EmptyState,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import {
  DataSection,
  ErrorState,
  InteractiveRow,
  MetricTile,
  PageSection,
  Pagination,
  Panel,
  SkeletonList,
  SkeletonMetric,
} from "@/components/portal/data";

export const Route = createFileRoute("/_portal/billing")({
  head: () => ({
    meta: [
      { title: "Billing — Nexus Customer Portal" },
      {
        name: "description",
        content: "What you owe Nexus, every invoice, and your prepaid balances and recharges.",
      },
      { property: "og:title", content: "Billing — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your amount due, invoices, and balances in plain numbers.",
      },
    ],
  }),
  component: BillingScreen,
});

const PAGE_SIZE = 10;

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

function invoicePeriod(invoice: InvoiceItem): string {
  return invoice.period_start && invoice.period_end
    ? `${date(invoice.period_start)} – ${date(invoice.period_end)}`
    : "—";
}

function BillingScreen() {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<InvoiceItem | null>(null);

  const billingQuery = useQuery({
    queryKey: qk.billing(cid),
    queryFn: () => fetchBilling(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const balanceQuery = useQuery({
    queryKey: qk.balance(cid),
    queryFn: () => fetchBalance(),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const billing = billingQuery.data;
  const balance = balanceQuery.data ?? { balances: [], recharges: [] };
  const hasBalances = balance.balances.length > 0;

  const nextDue = useMemo(() => {
    const dues = (billing?.invoices ?? [])
      .filter((i) => i.status !== "paid" && i.status !== "void")
      .map((i) => i.due_date)
      .filter((d): d is string => Boolean(d))
      .sort();
    return dues[0];
  }, [billing]);

  const rows = useMemo(
    () => (billing?.invoices ?? []).slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE),
    [billing, page],
  );

  if (billingQuery.isPending || balanceQuery.isPending) {
    return (
      <div className="space-y-sp-9">
        <PageSection>
          <Card>
            <SkeletonMetric />
          </Card>
        </PageSection>
        <PageSection label={copy.billing.invoices}>
          <Card>
            <SkeletonList rows={4} />
          </Card>
        </PageSection>
      </div>
    );
  }

  if (billingQuery.isError || !billing) {
    return (
      <Card>
        <ErrorState error={billingQuery.error} onRetry={() => void billingQuery.refetch()} />
      </Card>
    );
  }

  const postpaid = billing.accounts.length > 0;

  return (
    <div className="space-y-sp-9">
      <PageSection>
        <Card>
          <MetricTile
            size="xl"
            label={copy.billing.amountDue}
            value={money(billing.total_outstanding, billing.currency_code)}
            hint={nextDue ? date(nextDue) : undefined}
          />
        </Card>
      </PageSection>

      {postpaid && (
        <DataSection
          label={copy.billing.invoices}
          state={{
            isPending: billingQuery.isPending,
            isFetching: billingQuery.isFetching,
            error: billingQuery.error,
          }}
          items={rows}
          skeletonRows={4}
          empty={{
            title: copy.billing.noInvoices.title,
            body: copy.billing.noInvoices.body,
          }}
          onRetry={() => void billingQuery.refetch()}
        >
          {(items) => (
            <>
              <ul className="divide-y divide-stroke-subtle">
                {items.map((invoice) => (
                  <li key={invoice.invoice_number}>
                    <InteractiveRow
                      onClick={() => setSelected(invoice)}
                      className="flex items-center gap-sp-5"
                    >
                      <span className="t-mono min-w-0 flex-1 truncate text-ink-2">
                        {invoice.invoice_number}
                      </span>
                      <span className="t-caption hidden min-w-0 flex-1 truncate text-ink-4 sm:block">
                        {invoicePeriod(invoice)}
                      </span>
                      <span className="t-mono shrink-0 text-ink-1">
                        {money(invoice.total_amount, invoice.currency_code)}
                      </span>
                      <StatusChip tone={INVOICE_TONE[invoice.status]}>
                        {copy.labels.invoiceStatus[invoice.status] ?? invoice.status}
                      </StatusChip>
                    </InteractiveRow>
                  </li>
                ))}
              </ul>
              <Pagination
                total={billing.invoices.length}
                limit={PAGE_SIZE}
                offset={page * PAGE_SIZE}
                onOffsetChange={(next) => setPage(Math.floor(next / PAGE_SIZE))}
                busy={billingQuery.isFetching}
              />
            </>
          )}
        </DataSection>
      )}

      {hasBalances && (
        <PageSection label={copy.billing.balances}>
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
        </PageSection>
      )}

      {hasBalances && (
        <PageSection label={copy.billing.recharges}>
          {balance.recharges.length === 0 ? (
            <EmptyState
              title={copy.billing.noRecharges.title}
              body={copy.billing.noRecharges.body}
            />
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
        </PageSection>
      )}

      {!postpaid && !hasBalances && (
        <Card>
          <p className="t-caption text-ink-5">{copy.empty.generic}</p>
        </Card>
      )}

      <Panel
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.invoice_number ?? ""}
        subtitle={selected ? invoicePeriod(selected) : undefined}
      >
        {selected ? (
          <>
            <SectionLabel
              right={
                <StatusChip tone={INVOICE_TONE[selected.status]}>
                  {copy.labels.invoiceStatus[selected.status] ?? selected.status}
                </StatusChip>
              }
            >
              {copy.billing.invoices}
            </SectionLabel>
            <Divider className="mt-sp-7" />
            <dl className="mt-sp-7 grid grid-cols-2 gap-sp-5">
              {[
                [
                  copy.billing.amountDue,
                  money(selected.outstanding_amount, selected.currency_code),
                ],
                [copy.billing.total, money(selected.total_amount, selected.currency_code)],
                [copy.billing.issued, date(selected.issue_date)],
                [copy.billing.due, date(selected.due_date)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="t-micro-2 text-ink-5">{k}</dt>
                  <dd className="t-body-strong mt-sp-2 text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}
      </Panel>
    </div>
  );
}
