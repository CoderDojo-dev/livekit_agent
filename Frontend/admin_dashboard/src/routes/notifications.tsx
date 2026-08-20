import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { MailX } from "lucide-react";
import {
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
import { CountStrip } from "@/components/nexus/count-strip";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
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
import { clampPage, offsetFor } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";

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
      { title: pageTitle("Notifications") },
      {
        name: "description",
        content: "Outbound SMS, WhatsApp and email sends, with the channel and the outcome.",
      },
      { property: "og:title", content: pageTitle("Notifications") },
      { property: "og:description", content: "Every written confirmation the platform attempted." },
    ],
  }),
  component: NotificationsPage,
});

function NotificationsPage() {
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(0);

  /* Rows fit the viewport instead of the old fixed 50 (growing to 200 via "Load more", which
   * made this page ~10 500px tall). */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 480,
    min: 5,
    max: 14,
    fallback: 8,
  });

  const notificationsQuery = useQuery({
    queryKey: notificationKeys.list(channel, status, pageSize, offsetFor(page, pageSize)),
    queryFn: () =>
      listNotifications({
        data: {
          limit: pageSize,
          offset: offsetFor(page, pageSize),
          channel: channel || undefined,
          status: status || undefined,
        },
      }),
    placeholderData: keepPreviousData,
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

  useEffect(() => setPage(0), [status, channel, pageSize]);
  const safePage = clampPage(page, total, pageSize);

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection index={0}>
        <Card>
          <CountStrip
            items={STATUS_ORDER.map((key) => ({
              id: key,
              label: STATUS_LABELS[key] ?? key,
              value: statusCount(counts, key),
            }))}
            active={status}
            onSelect={setStatus}
            loading={notificationsQuery.isPending}
          />
          {/* D18.4 / §2.5 — never let this read as "every message the platform sent". */}
          <p className="t-caption mt-sp-7 max-w-[86ch] border-t border-stroke-subtle pt-sp-5 text-ink-5">
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
      <PageSection index={1}>
        <TableShell
          minWidth={780}
          bodyAsChild
          busy={notificationsQuery.isFetching && !notificationsQuery.isPending}
          toolbar={
            <Segmented
              groupId="notification-channel"
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
            <Pager
              page={safePage}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              noun="sends"
              busy={notificationsQuery.isFetching && !notificationsQuery.isPending}
              className="w-full"
            />
          }
        >
          <TableBodySwap pageKey={`${safePage}-${status}-${channel}`}>
            {notificationsQuery.isPending ? (
              <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
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
                    <span className="t-ui truncate text-ink-1">
                      {templateLabel(n.template_code)}
                    </span>
                  </Td>
                  {/* A failure reason turns this into a two-line cell, so it aligns to the top
                   * rather than dragging the whole row's vertical centring with it. */}
                  <Td stacked={n.status === "failed" && Boolean(n.failure_reason)}>
                    <div className="flex flex-col items-start gap-sp-2">
                      <StatusChip status={notificationStatusKey(n.status)} />
                      {n.status === "failed" && n.failure_reason ? (
                        <span className="t-caption max-w-[32ch] text-ink-5">
                          {n.failure_reason}
                        </span>
                      ) : null}
                    </div>
                  </Td>
                  <Td align="right">
                    <span className="t-mono whitespace-nowrap text-ink-3">
                      {notificationTime(n.created_at, timeZone)}
                    </span>
                  </Td>
                </tr>
              ))
            )}
          </TableBodySwap>
        </TableShell>
      </PageSection>
    </>
  );
}
