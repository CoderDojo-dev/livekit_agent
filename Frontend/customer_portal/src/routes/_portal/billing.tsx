import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchBalance, fetchBilling, type InvoiceItem } from "@/lib/api/billing.server";
import { date, money } from "@/lib/format";
import type { Paged } from "@/lib/api/activity.server";
import { Card, Divider, SectionLabel, StatusChip } from "@/components/portal/primitives";
import {
  DataSection,
  ErrorState,
  InteractiveRow,
  MetricTile,
  PageSection,
  Pagination,
  Panel,
} from "@/components/portal/data";

export const Route = createFileRoute("/_portal/billing")({
  head: () => ({
    meta: [
      { title: pageTitle("Billing") },
      {
        name: "description",
        content: "What you owe, every invoice, and your prepaid balances and recharges.",
      },
      { property: "og:title", content: brand.name },
      {
        property: "og:description",
        content: "Your amount due, invoices, and balances in plain numbers.",
      },
    ],
  }),
  component: BillingScreen,
});

const PAGE_SIZE = 20;

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
    queryKey: qk.billing(cid, PAGE_SIZE, page * PAGE_SIZE),
    queryFn: () => fetchBilling({ data: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } }),
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
  // Postpaid is unknown until the payload lands. Rendering the invoice section
  // during load is correct: DataSection owns the skeleton, and a customer with
  // no accounts sees it collapse once, not a page that rebuilds itself.
  const postpaid = billing ? billing.accounts.length > 0 : true;
  const hasBalances = balance.balances.length > 0;

  const invoices = billing?.invoices?.items ?? [];
  const invoiceTotal = billing?.invoices?.total ?? 0;

  return (
    <div className="space-y-sp-9">
      <PageSection>
        <Card>
          {billingQuery.isError ? (
            <ErrorState error={billingQuery.error} onRetry={() => void billingQuery.refetch()} />
          ) : (
            <MetricTile
              size="xl"
              pending={billingQuery.isPending}
              label={copy.billing.amountDue}
              value={billing ? money(billing.total_outstanding, billing.currency_code) : ""}
              hint={billing?.next_due_date ? date(billing.next_due_date) : undefined}
            />
          )}
        </Card>
      </PageSection>

      {postpaid && (
        <DataSection<InvoiceItem>
          label={copy.billing.invoices}
          state={{
            isPending: billingQuery.isPending,
            isFetching: billingQuery.isFetching,
            isPlaceholderData: billingQuery.isPlaceholderData,
            error: billingQuery.error,
          }}
          items={invoices}
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
                total={invoiceTotal}
                limit={PAGE_SIZE}
                offset={page * PAGE_SIZE}
                onOffsetChange={(next) => setPage(Math.floor(next / PAGE_SIZE))}
              />
            </>
          )}
        </DataSection>
      )}

      {hasBalances && (
        <PageSection>
          <Card className="flex items-center justify-between gap-sp-6">
            <p className="t-caption max-w-md text-ink-4">{copy.billing.prepaidPointer}</p>
            <Link
              to="/services"
              className="focus-ring t-ui shrink-0 rounded-r-2 px-sp-5 py-sp-3 text-ink-2 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
            >
              {copy.billing.prepaidPointerAction}
            </Link>
          </Card>
        </PageSection>
      )}

      {!billingQuery.isPending && !balanceQuery.isPending && !postpaid && !hasBalances && (
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
