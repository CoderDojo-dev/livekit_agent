import { useQuery } from "@tanstack/react-query";
import { UserX } from "lucide-react";
import { Modal } from "@/components/nexus/modal";
import { StatusChip, Token, EmptyState } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getCustomer360, type CustomerRow } from "@/lib/api/customers.server";
import { customerKeys } from "@/lib/nexus/query-keys";
import {
  customerStatusKey,
  formatAmount,
  invoiceStatusKey,
  languageLabel,
  outstandingTotal,
  subscriptionStatusKey,
} from "@/lib/nexus/customer-view";
import { ticketStatusKey } from "@/lib/nexus/ticket-view";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { maskPhone } from "@/lib/nexus/format";

type Props = {
  customer: CustomerRow | null;
  onClose: () => void;
};

export function CustomerDetail({ customer, onClose }: Props) {
  const enabled = Boolean(customer);

  const query = useQuery({
    queryKey: customerKeys.detail(customer?.customer_id ?? ""),
    queryFn: () => getCustomer360({ data: { customerId: customer!.customer_id } }),
    enabled,
  });

  if (!customer) return null;

  const notFound = isApiError(query.error) && query.error.status === 404;

  return (
    <Modal open onClose={onClose} title={customer.name}>
      {/* Header strip — from the row, because customer_360 omits status/email/phone */}
      <div className="flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle pb-sp-5">
        <StatusChip status={customerStatusKey(customer.status) ?? ""} />
        {customer.vip ? <Token strong>VIP</Token> : null}
        <Token mono={false}>{languageLabel(customer.preferred_language)}</Token>
        {customer.segment ? <Token mono={false}>{customer.segment}</Token> : null}
        <span className="t-caption ml-auto text-ink-4">
          {customer.email ?? "\u2014"}
          {customer.contact_number ? ` \u00b7 ${maskPhone(customer.contact_number)}` : ""}
        </span>
      </div>

      {query.isPending ? (
        <div className="mt-sp-7">
          <CardSkeleton />
        </div>
      ) : notFound ? (
        <div className="mt-sp-7">
          <EmptyState
            icon={UserX}
            title="Customer no longer available"
            description="This record was removed after the list was loaded. Refresh the table."
          />
        </div>
      ) : query.isError ? (
        <div className="mt-sp-7">
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        </div>
      ) : (
        <>
          {/* Subscriptions */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Subscriptions</h3>
            {query.data!.subscriptions.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">No subscriptions on record.</p>
            ) : (
              <ul className="mt-sp-5">
                {query.data!.subscriptions.map((s) => (
                  <li
                    key={s.subscription_id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <span className="min-w-0">
                      <span className="t-ui truncate text-ink-1">{s.msisdn}</span>
                      <span className="t-caption truncate text-ink-4">{s.plan}</span>
                    </span>
                    <span className="ml-auto">
                      <StatusChip status={subscriptionStatusKey(s.status) ?? ""} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Open invoices */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Open invoices</h3>
            {query.data!.open_invoices.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">Nothing outstanding.</p>
            ) : (
              <>
                <ul className="mt-sp-5">
                  {query.data!.open_invoices.map((inv) => (
                    <li
                      key={inv.invoice}
                      className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                    >
                      <span className="t-ui truncate text-ink-1">{inv.invoice}</span>
                      <span className="ml-auto flex items-center gap-sp-5">
                        <span className="t-mono-l text-ink-1">{formatAmount(inv.amount)}</span>
                        <StatusChip status={invoiceStatusKey(inv.status) ?? ""} />
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="mt-sp-6 flex items-center border-t border-stroke-subtle pt-sp-5">
                  <span className="t-label text-ink-3">Total invoiced</span>
                  <span className="t-mono-l ml-auto text-ink-1">
                    {formatAmount(outstandingTotal(query.data!.open_invoices))}
                  </span>
                </div>
              </>
            )}
          </section>

          {/* Tickets */}
          <section className="mt-sp-7">
            <h3 className="t-label text-ink-3">Tickets</h3>
            {query.data!.tickets.length === 0 ? (
              <p className="t-caption mt-sp-5 text-ink-4">No tickets raised.</p>
            ) : (
              <ul className="mt-sp-5">
                {query.data!.tickets.map((t) => (
                  <li
                    key={String(t.glpi_id)}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                  >
                    <span className="min-w-0">
                      <span className="t-ui truncate text-ink-1">{t.subject}</span>
                      <span className="t-caption truncate text-ink-4">#{t.glpi_id}</span>
                    </span>
                    <span className="ml-auto">
                      <StatusChip status={ticketStatusKey(t.status)} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Modal>
  );
}
