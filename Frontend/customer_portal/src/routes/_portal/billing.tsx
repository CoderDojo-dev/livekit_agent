import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Banknote,
  BanknoteArrowUp,
  CalendarClock,
  CreditCard,
  FileText,
  Landmark,
  Ticket,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import {
  fetchBalance,
  fetchBilling,
  type InvoiceItem,
  type PaymentItem,
} from "@/lib/api/billing.server";
import { date, dateTime, money } from "@/lib/format";
import { Card, Divider, IconFrame, SectionLabel, StatusChip } from "@/components/portal/primitives";
import {
  DataSection,
  ErrorState,
  InteractiveRow,
  MetricTile,
  PageSection,
  Pagination,
  Panel,
  RowChevron,
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

/* billing.payments.method is a constrained enum in persistence but arrives as a
 * plain string, so both maps are keyed loosely and fall back — an enum value
 * added later renders as itself rather than as a blank cell. */
const METHOD_ICON: Record<string, LucideIcon> = {
  card: CreditCard,
  bank_transfer: Landmark,
  wallet: Wallet,
  voucher: Ticket,
  cash: Banknote,
};

const PAYMENT_TONE: Record<string, "solid" | "outline" | "dashed" | "muted"> = {
  succeeded: "outline",
  pending: "dashed",
  failed: "muted",
  refunded: "muted",
};

function invoicePeriod(invoice: InvoiceItem): string {
  return invoice.period_start && invoice.period_end
    ? `${date(invoice.period_start)} – ${date(invoice.period_end)}`
    : "—";
}

/** The most recent payment that actually settled. A pending or failed capture
 *  is not "what you last paid", and showing one as such would be a small lie
 *  about the state of the account. */
function lastSettled(payments: PaymentItem[]): PaymentItem | undefined {
  return payments
    .filter((payment) => payment.status === "succeeded" && payment.paid_at)
    .sort((a, b) => new Date(b.paid_at!).getTime() - new Date(a.paid_at!).getTime())[0];
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
  const payments = billing?.payments ?? [];
  const settled = lastSettled(payments);
  // Counted over the loaded page only, and labelled as a count of invoices —
  // the endpoint gives a whole-account invoice total but no whole-account paid
  // total, so this qualifies the page rather than claiming to describe the
  // account.
  const paidOnPage = invoices.filter((invoice) => invoice.status === "paid").length;

  return (
    <div className="space-y-sp-9">
      {/*
        THE HEADLINE.

        This was one tile alone on a full-width card: a single figure with two
        thirds of a card of empty space beside it. The two facts that qualify
        it — when the next payment is due, and what was last actually paid —
        were both already in the payload and both thrown away. Three tiles, one
        card, no new request.
      */}
      <PageSection index={0}>
        <Card>
          {billingQuery.isError ? (
            <ErrorState error={billingQuery.error} onRetry={() => void billingQuery.refetch()} />
          ) : (
            <div className="grid gap-sp-7 sm:grid-cols-2 lg:grid-cols-3">
              <MetricTile
                icon={Wallet}
                size="xl"
                pending={billingQuery.isPending}
                label={copy.billing.amountDue}
                value={billing ? money(billing.total_outstanding, billing.currency_code) : ""}
                hint={billing?.next_due_date ? date(billing.next_due_date) : undefined}
              />
              <MetricTile
                icon={CalendarClock}
                size="l"
                pending={billingQuery.isPending}
                label={copy.billing.nextDue}
                value={
                  billing?.next_due_date ? date(billing.next_due_date) : copy.billing.nextDueNone
                }
                hint={
                  billing && invoiceTotal > 0
                    ? copy.billing.invoiceCountHint(paidOnPage)
                    : undefined
                }
              />
              <MetricTile
                icon={BanknoteArrowUp}
                size="l"
                pending={billingQuery.isPending}
                label={copy.billing.lastPayment}
                value={
                  settled ? money(settled.amount, settled.currency_code) : copy.billing.noPaymentYet
                }
                hint={settled?.paid_at ? date(settled.paid_at) : undefined}
              />
            </div>
          )}
        </Card>
      </PageSection>

      {postpaid && (
        <DataSection<InvoiceItem>
          label={copy.billing.invoices}
          index={1}
          icon={FileText}
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
                      <IconFrame icon={FileText} />
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
                      <RowChevron />
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

      {/*
        THE PAYMENTS.

        /me/billing has returned a `payments` array since the endpoint was
        written and no screen has ever rendered it, so "did my payment go
        through?" — the single most common billing question there is — had no
        answer anywhere in the portal. It is a short unpaged list by design on
        the server side ("context for the invoices, not a browsable ledger"),
        so it gets a section and no pager.
      */}
      {postpaid && (
        <DataSection<PaymentItem>
          label={copy.billing.payments}
          index={2}
          icon={BanknoteArrowUp}
          right={<span className="t-caption text-ink-5">{copy.billing.paymentsNote}</span>}
          state={{
            isPending: billingQuery.isPending,
            isFetching: billingQuery.isFetching,
            isPlaceholderData: billingQuery.isPlaceholderData,
            error: billingQuery.error,
          }}
          items={payments}
          skeletonRows={3}
          empty={copy.billing.noPayments}
          onRetry={() => void billingQuery.refetch()}
        >
          {(items) => (
            <ul className="divide-y divide-stroke-subtle">
              {items.map((payment, index) => {
                const method = payment.method ?? "";
                const Icon = METHOD_ICON[method] ?? Banknote;
                return (
                  <li
                    key={`${payment.invoice_number ?? "na"}-${payment.paid_at ?? index}`}
                    className="group flex items-center gap-sp-5 py-sp-6 first:pt-0 last:pb-0"
                  >
                    <IconFrame icon={Icon} />
                    <div className="min-w-0 flex-1">
                      <div className="t-body-strong text-ink-1">
                        {money(payment.amount, payment.currency_code)}
                      </div>
                      <div className="t-caption mt-sp-1 truncate text-ink-5">
                        {copy.labels.paymentMethod[
                          method as keyof typeof copy.labels.paymentMethod
                        ] ?? method}
                        {payment.invoice_number ? ` · ${payment.invoice_number}` : ""}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-sp-2">
                      <StatusChip tone={PAYMENT_TONE[payment.status] ?? "muted"}>
                        {copy.labels.paymentStatus[
                          payment.status as keyof typeof copy.labels.paymentStatus
                        ] ?? payment.status}
                      </StatusChip>
                      <span className="t-mono-s text-ink-5">{dateTime(payment.paid_at)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </DataSection>
      )}

      {hasBalances && (
        <PageSection index={3}>
          <Link to="/services" className="focus-ring group block rounded-r-5">
            <Card interactive className="flex items-center justify-between gap-sp-6 p-sp-7">
              <div className="flex min-w-0 items-center gap-sp-5">
                <IconFrame icon={Wallet} />
                <p className="t-body min-w-0 text-ink-3">{copy.billing.prepaidPointer}</p>
              </div>
              <span className="t-ui inline-flex shrink-0 items-center gap-sp-3 text-ink-4 transition-colors duration-200 group-hover:text-ink-1">
                {copy.billing.prepaidPointerAction}
                <ArrowUpRight
                  size={15}
                  strokeWidth={1.6}
                  aria-hidden="true"
                  className="transition-transform duration-200 group-hover:-translate-y-px group-hover:translate-x-px"
                />
              </span>
            </Card>
          </Link>
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

            {/* How much of this invoice is actually settled. Both numbers are
                on the row above; the bar only draws the relationship between
                them, and it is skipped entirely when the total is missing or
                zero rather than rendering a full bar over no data. */}
            {selected.total_amount ? (
              <div className="mt-sp-7">
                <div className="flex items-baseline justify-between gap-sp-5">
                  <span className="t-micro-2 text-ink-5">{copy.billing.settled}</span>
                  <span className="t-mono-s text-ink-4">
                    {copy.billing.outstandingOf(
                      money(
                        selected.total_amount - (selected.outstanding_amount ?? 0),
                        selected.currency_code,
                      ),
                      money(selected.total_amount, selected.currency_code),
                    )}
                  </span>
                </div>
                <div className="mt-sp-4 h-1.5 w-full overflow-hidden rounded-r-1 border border-stroke-subtle bg-surface-3">
                  <div
                    className="h-full bg-ink-2 transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          0,
                          ((selected.total_amount - (selected.outstanding_amount ?? 0)) /
                            selected.total_amount) *
                            100,
                        ),
                      )}%`,
                    }}
                  />
                </div>
              </div>
            ) : null}

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
                <div
                  key={k}
                  className="rounded-r-2 border border-stroke-subtle bg-surface-2 p-sp-5"
                >
                  <dt className="t-micro-2 text-ink-5">{k}</dt>
                  <dd className="t-body-strong mt-sp-2 text-ink-1">{v}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}
      </Panel>
    </div>
  );
}
