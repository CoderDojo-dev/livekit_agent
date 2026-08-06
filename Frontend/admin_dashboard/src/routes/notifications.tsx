import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MailX } from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import { listNotifications } from "@/lib/api/notifications.server";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  channelLabel,
  notificationRecipient,
  notificationStatusKey,
  notificationTime,
  statusCount,
  templateLabel,
} from "@/lib/nexus/notification-view";
import { availabilityKeys, notificationKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";

const COLUMN_COUNT = 5;

const CHANNEL_OPTIONS = [
  { id: "", label: "All" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "sms", label: "SMS" },
  { id: "email", label: "Email" },
];

export const Route = createFileRoute("/notifications")({
  head: () => ({
    meta: [
      { title: "Notifications — Nexus" },
      {
        name: "description",
        content: "Outbound SMS, WhatsApp and email sends, with the channel and the outcome.",
      },
      { property: "og:title", content: "Notifications — Nexus" },
      { property: "og:description", content: "Every written confirmation the platform attempted." },
    ],
  }),
  component: NotificationsPage,
});

function NotificationsPage() {
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [limit, setLimit] = useState(50);

  const notificationsQuery = useQuery({
    queryKey: notificationKeys.list(channel, status, limit),
    queryFn: () =>
      listNotifications({
        data: {
          limit,
          offset: 0,
          channel: channel || undefined,
          status: status || undefined,
        },
      }),
  });

  // F14 — business timezone; shared cache with /availability, /callbacks, /calls and /tickets.
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const rows = notificationsQuery.data?.notifications ?? [];
  const total = notificationsQuery.data?.total ?? 0;
  const counts = notificationsQuery.data?.counts;

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection>
        <Card>
          <div className="grid grid-cols-3 gap-sp-6">
            {STATUS_ORDER.map((key) => {
              const active = status === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStatus(active ? "" : key)}
                  className="text-left"
                  aria-pressed={active}
                >
                  <span className="t-micro block text-ink-5">{STATUS_LABELS[key]}</span>
                  <span
                    className={
                      active ? "t-metric-m block text-ink-1" : "t-metric-m block text-ink-3"
                    }
                  >
                    {formatInteger(statusCount(counts, key))}
                  </span>
                </button>
              );
            })}
          </div>
          {/* D18.4 / §2.5 — never let this read as "every message the platform sent". */}
          <p className="t-caption mt-sp-6 text-ink-5">
            Written by the notification-service after each send attempt. A failed row means the
            provider or the contact lookup refused it; the reason is returned to the caller but not
            stored, so it cannot be shown here. Times are when the attempt was logged.
            {!timeZone && !coverageQuery.isPending
              ? " Times shown in UTC — the business timezone could not be loaded."
              : null}
          </p>
        </Card>
      </PageSection>

      {/* ---------- Table ---------- */}
      <PageSection>
        <TableShell
          toolbar={
            <Segmented
              items={CHANNEL_OPTIONS.map((o) => o.label)}
              active={CHANNEL_OPTIONS.find((o) => o.id === channel)?.label ?? "All"}
              onSelect={(label) =>
                setChannel(CHANNEL_OPTIONS.find((o) => o.label === label)?.id ?? "")
              }
            />
          }
          head={
            <tr>
              <Th>Recipient</Th>
              <Th>Channel</Th>
              <Th>Template</Th>
              <Th>Status</Th>
              {/* D18.5 — "Logged", not "Sent": sent_at is a server default written at INSERT. */}
              <Th align="right">Logged</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                Showing {rows.length} of {formatInteger(total)} sends
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </>
          }
        >
          {notificationsQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={6} />
          ) : notificationsQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={notificationsQuery.error}
              onRetry={() => notificationsQuery.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={MailX}
                  title="No notifications found"
                  description="No send attempt matches this filter."
                />
              </td>
            </tr>
          ) : (
            rows.map((n) => (
              <tr key={n.id} className="transition-colors duration-[120ms] hover:bg-surface-3">
                <Td>
                  <span className="flex items-center gap-sp-4">
                    <span className="truncate">
                      {notificationRecipient(n.customer_name, n.customer_id)}
                    </span>
                    {n.customer_vip ? <Token strong>VIP</Token> : null}
                  </span>
                </Td>
                <Td>
                  <Token mono={false}>{channelLabel(n.channel)}</Token>
                </Td>
                <Td>
                  <span className="t-ui truncate text-ink-1">{templateLabel(n.template_code)}</span>
                </Td>
                <Td>
                  <StatusChip status={notificationStatusKey(n.status)} />
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">
                    {notificationTime(n.created_at, timeZone)}
                  </span>
                </Td>
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>
    </>
  );
}
