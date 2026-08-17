import { createFileRoute } from "@tanstack/react-router";
import { copy } from "@/lib/copy";
import { invoices, nextCharge, spend, type InvoiceStatus } from "@/lib/fixtures/billing";
import { Card, Divider, SectionLabel, StatusChip } from "@/components/portal/primitives";

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

const TONE: Record<InvoiceStatus, "solid" | "outline" | "dashed" | "dotted" | "muted"> = {
  paid: "outline",
  pending: "solid",
  failed: "dashed",
  refunded: "dotted",
  void: "muted",
};

function BillingScreen() {
  const max = Math.max(...spend.map((s) => s.value));

  return (
    <div className="space-y-sp-10">
      <div className="grid gap-sp-7 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-sp-6">
          <SectionLabel>{copy.billing.nextCharge}</SectionLabel>
          <Card>
            <div className="flex items-end justify-between gap-sp-6">
              <div>
                <div className="t-metric-xl text-ink-1">{nextCharge.amount}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  on {nextCharge.date} · {nextCharge.method}
                </div>
              </div>
              <StatusChip tone="dotted">SCHEDULED</StatusChip>
            </div>
            <Divider className="my-sp-7" />
            <ul className="space-y-sp-5">
              {nextCharge.lines.map((l) => (
                <li key={l.label} className="flex items-center justify-between">
                  <span className="t-ui text-ink-3">{l.label}</span>
                  <span className="t-mono text-ink-1">{l.amount}</span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      </div>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.billing.spend}</SectionLabel>
        <Card>
          <div className="flex h-40 items-end gap-sp-6">
            {spend.map((s) => (
              <div
                key={s.month}
                className="flex h-full flex-1 flex-col items-center justify-end gap-sp-4"
              >
                <span className="t-mono-s text-ink-5">£{s.value}.00</span>
                <div
                  className="w-full rounded-r-1 border border-stroke-strong bg-surface-4"
                  style={{ height: `${(s.value / max) * 82}%` }}
                />
                <span className="t-micro-2 text-ink-5">{s.month}</span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.billing.invoices}</SectionLabel>
        <div className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
          <table className="w-full">
            <thead>
              <tr className="border-b border-stroke-subtle">
                {["INVOICE", "PERIOD", "DATE", "AMOUNT", "STATUS"].map((h) => (
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
              {invoices.map((inv) => (
                <tr
                  key={inv.id}
                  className="border-b border-stroke-subtle transition-colors duration-200 last:border-b-0 hover:bg-surface-2"
                >
                  <td className="t-mono px-sp-7 py-sp-6 text-ink-2">{inv.ref}</td>
                  <td className="t-ui px-sp-7 py-sp-6 text-ink-1">{inv.period}</td>
                  <td className="t-mono px-sp-7 py-sp-6 text-ink-4">{inv.date}</td>
                  <td className="t-mono px-sp-7 py-sp-6 text-ink-1">{inv.amount}</td>
                  <td className="px-sp-7 py-sp-6">
                    <StatusChip tone={TONE[inv.status]}>
                      {copy.billing.status[inv.status]}
                    </StatusChip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
