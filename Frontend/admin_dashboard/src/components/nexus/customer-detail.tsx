import { useQuery } from "@tanstack/react-query";
import { UserX } from "lucide-react";
import { Modal } from "@/components/nexus/modal";
import { StatusChip, Token, EmptyState } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import {
  getCustomer360,
  getCustomerLedger,
  getCustomerServiceActions,
  type CustomerRow,
} from "@/lib/api/customers.server";
import { customerKeys } from "@/lib/nexus/query-keys";
import {
  balanceStatusKey,
  balanceTypeLabel,
  changedByLabel,
  consentStatusKey,
  consentTypeLabel,
  customerStatusKey,
  formatAmount,
  invoiceStatusKey,
  languageLabel,
  paymentMethodLabel,
  paymentPlanStatusKey,
  paymentStatusKey,
  rechargeChannelLabel,
  serviceEventStatusKey,
  serviceEventTitle,
  subscriptionStatusKey,
  unpaidTotal,
} from "@/lib/nexus/customer-view";
import { ticketStatusKey } from "@/lib/nexus/ticket-view";
import { errorMessage, toApiError } from "@/lib/api/errors";
import { formatPhone } from "@/lib/nexus/format";
import { formatInstant } from "@/lib/nexus/audit-view";

// Mirrors the backend cap in SupervisionRepository.customer_ledger (_LEDGER_LIMIT = 50).
// When a collection is exactly this size it may be truncated, so the sections say so.
const LEDGER_CAP = 50;

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

  // Independent query: a ledger failure (route not yet deployed) must not blank out the
  // working 360 sections. It also keeps customer_360's return shape untouched.
  const ledgerQuery = useQuery({
    queryKey: customerKeys.ledger(customer?.customer_id ?? ""),
    queryFn: () => getCustomerLedger({ data: { customerId: customer!.customer_id } }),
    enabled,
  });

  // Independent query: a service-actions failure must not blank the 360 or ledger sections.
  const serviceQuery = useQuery({
    queryKey: customerKeys.serviceActions(customer?.customer_id ?? ""),
    queryFn: () => getCustomerServiceActions({ data: { customerId: customer!.customer_id } }),
    enabled,
  });

  if (!customer) return null;

  const notFound = toApiError(query.error)?.status === 404;
  const ledgerNotFound = toApiError(ledgerQuery.error)?.status === 404;
  const serviceNotFound = toApiError(serviceQuery.error)?.status === 404;

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
          {customer.contact_number ? ` \u00b7 ${formatPhone(customer.contact_number)}` : ""}
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
                      <span className="min-w-0">
                        <span className="t-ui truncate text-ink-1">{inv.invoice}</span>
                        {inv.outstanding !== inv.amount ? (
                          <span className="t-caption truncate text-ink-4">
                            Invoiced {formatAmount(inv.amount)}
                          </span>
                        ) : null}
                      </span>
                      <span className="ml-auto flex items-center gap-sp-5">
                        <span className="t-mono-l text-ink-1">{formatAmount(inv.outstanding)}</span>
                        <StatusChip status={invoiceStatusKey(inv.status) ?? ""} />
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="mt-sp-6 flex items-center border-t border-stroke-subtle pt-sp-5">
                  <span className="t-label text-ink-3">Unpaid total</span>
                  <span className="t-mono-l ml-auto text-ink-1">
                    {formatAmount(unpaidTotal(query.data!.open_invoices))}
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

          {ledgerNotFound ? null : ledgerQuery.isPending ? (
            <div className="mt-sp-7">
              <CardSkeleton lines={3} />
            </div>
          ) : ledgerQuery.isError ? (
            <div className="mt-sp-7">
              <ErrorState
                error={ledgerQuery.error}
                onRetry={() => ledgerQuery.refetch()}
                title="Ledger unavailable"
              />
            </div>
          ) : (
            <>
              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Payments</h3>
                {ledgerQuery.data!.payments.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No payments recorded. Payments are projected from authorised EXECUTE_PAYMENT
                    actions.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {ledgerQuery.data!.payments.map((payment) => (
                      <li
                        key={payment.payment_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <StatusChip status={paymentStatusKey(payment.status)} />
                        <span className="t-body text-ink-2">
                          {paymentMethodLabel(payment.method)}
                        </span>
                        <span className="t-caption text-ink-4">
                          {payment.invoice ?? "No invoice settled"}
                        </span>
                        <span className="t-caption text-ink-4">
                          {payment.paid_at ? formatInstant(payment.paid_at) : "—"}
                        </span>
                        <span className="t-mono-l ml-auto text-ink-1">
                          {formatAmount(payment.amount, payment.currency_code)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {ledgerQuery.data!.payments.length === LEDGER_CAP ? (
                  <p className="t-caption mt-sp-2 text-ink-5">Showing the latest 50 payments.</p>
                ) : null}
              </section>

              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Deferral plans</h3>
                {ledgerQuery.data!.payment_plans.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No deferral plans. Plans are projected from authorised PAYMENT_DEFERRAL actions.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {ledgerQuery.data!.payment_plans.map((plan) => (
                      <li
                        key={plan.plan_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <StatusChip status={paymentPlanStatusKey(plan.status)} />
                        <span className="t-body text-ink-2">
                          {plan.installment_count} × {formatAmount(plan.installment_amount)}
                        </span>
                        <span className="t-caption text-ink-4">
                          {plan.deferral_until
                            ? `Deferred to ${plan.deferral_until}`
                            : "No deferral date"}
                        </span>
                        <span className="t-mono-l ml-auto text-ink-1">
                          {formatAmount(plan.total_amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {ledgerQuery.data!.payment_plans.length === LEDGER_CAP ? (
                  <p className="t-caption mt-sp-2 text-ink-5">Showing the latest 50 plans.</p>
                ) : null}
              </section>

              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Consent captures</h3>
                {ledgerQuery.data!.consents.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No consent captured for this customer.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {ledgerQuery.data!.consents.map((consent) => (
                      <li
                        key={consent.consent_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <StatusChip status={consentStatusKey(consent.granted)} />
                        <span className="t-body text-ink-2">
                          {consentTypeLabel(consent.consent_type)}
                        </span>
                        <span className="t-caption text-ink-4">
                          {consent.language ? languageLabel(consent.language) : "—"}
                        </span>
                        <span className="t-caption ml-auto text-ink-4">
                          {consent.captured_at ? formatInstant(consent.captured_at) : "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {ledgerQuery.data!.consents.length === LEDGER_CAP ? (
                  <p className="t-caption mt-sp-2 text-ink-5">Showing the latest 50 consents.</p>
                ) : null}
              </section>
            </>
          )}

          {serviceNotFound ? null : serviceQuery.isPending ? (
            <div className="mt-sp-7">
              <CardSkeleton lines={3} />
            </div>
          ) : serviceQuery.isError ? (
            <div className="mt-sp-7">
              <ErrorState
                error={serviceQuery.error}
                onRetry={() => serviceQuery.refetch()}
                title="Service actions unavailable"
              />
            </div>
          ) : (
            <>
              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Live balances</h3>
                {serviceQuery.data!.balances.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No balance accounts on this customer's lines.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {serviceQuery.data!.balances.map((balance) => (
                      <li
                        key={balance.balance_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <StatusChip status={balanceStatusKey(balance.status)} />
                        <span className="t-body text-ink-2">
                          {balanceTypeLabel(balance.balance_type)}
                        </span>
                        <span className="t-caption text-ink-4">{balance.msisdn ?? "—"}</span>
                        <span className="t-caption text-ink-4">
                          {balance.expiry_date ? `Expires ${balance.expiry_date}` : "No expiry"}
                        </span>
                        <span className="t-mono-l ml-auto text-ink-1">
                          {formatAmount(balance.balance_value, balance.balance_unit)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Plan history</h3>
                {serviceQuery.data!.plan_changes.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No plan changes recorded. Written when an authorised CHANGE_PLAN action
                    completes.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {serviceQuery.data!.plan_changes.map((change) => (
                      <li
                        key={change.change_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <span className="t-body text-ink-2">
                          {change.from_plan ?? "—"} → {change.to_plan}
                        </span>
                        <span className="t-caption text-ink-4">
                          {changedByLabel(change.changed_by)}
                        </span>
                        <span className="t-caption text-ink-4">{change.msisdn ?? "—"}</span>
                        <span className="t-caption ml-auto text-ink-4">
                          {change.effective_date ?? "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="mt-sp-7">
                <h3 className="t-label text-ink-3">Service actions</h3>
                {serviceQuery.data!.events.length === 0 ? (
                  <p className="t-caption mt-sp-5 text-ink-4">
                    No service actions recorded. Top-ups, SIM cases, SIM orders and provisioning
                    requests are projected from authorised actions.
                  </p>
                ) : (
                  <ul className="mt-sp-5">
                    {serviceQuery.data!.events.map((event) => (
                      <li
                        key={event.event_id}
                        className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
                      >
                        <StatusChip status={serviceEventStatusKey(event)} />
                        <span className="t-body text-ink-2">{serviceEventTitle(event)}</span>
                        <span className="t-caption text-ink-4">{event.msisdn ?? "—"}</span>
                        <span className="t-caption text-ink-4">
                          {event.occurred_at ? formatInstant(event.occurred_at) : "—"}
                        </span>
                        <span className="t-mono-l ml-auto text-ink-1">
                          {event.source === "recharge"
                            ? formatAmount(event.amount)
                            : (event.reference ?? "—")}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {serviceQuery.data!.events.length === LEDGER_CAP ? (
                  <p className="t-caption mt-sp-2 text-ink-5">
                    Showing the latest {LEDGER_CAP} service actions.
                  </p>
                ) : null}
              </section>
            </>
          )}
        </>
      )}
    </Modal>
  );
}
