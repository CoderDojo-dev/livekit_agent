import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, Bell, BellOff, Mail, MessageSquare, MessagesSquare } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { copy } from "@/lib/copy";
import { useTranslation } from "@/lib/i18n";
import { relative } from "@/lib/format";
import type { NotificationItem } from "@/lib/api/notifications.server";
import { IconButton, IconFrame, StatusChip } from "@/components/portal/primitives";
import { usePortalReducedMotion } from "@/hooks/use-portal-motion";

/**
 * components/shell/notification-tray.tsx — chapitre 12.4.
 *
 * Lifted out of portal-topbar.tsx, where it was inline markup with three
 * defects that a dropdown two rows from the sign-out button should not have:
 *
 *  - it did not close on an outside click or on Escape, so it stayed open over
 *    the page until the bell was pressed a second time. AccountMenu, six lines
 *    below it in the same file, has always done both;
 *  - it appeared and disappeared instantly while every other overlay in the
 *    portal (Panel, AccountMenu) cross-fades;
 *  - it carried no aria wiring at all: no `aria-expanded`, no `aria-haspopup`,
 *    no dialog role, so a screen reader was never told anything had opened.
 *
 * NO UNREAD BADGE, DELIBERATELY. The notifications endpoint returns queued /
 * sent / failed — a DELIVERY state — and has no concept of whether the customer
 * has looked at a message. A dot on the bell would be read as "unread", which
 * is a claim the data cannot support. The tray states the count in its own
 * header instead, where it is unambiguous.
 */

const CHANNEL_ICON: Record<NotificationItem["channel"], LucideIcon> = {
  sms: MessageSquare,
  whatsapp: MessagesSquare,
  email: Mail,
};

const STATUS_TONE: Record<NotificationItem["status"], "outline" | "dashed" | "muted"> = {
  sent: "outline",
  queued: "dashed",
  failed: "muted",
};

function notificationMessage(item: NotificationItem): string {
  const template = item.template_code
    ? copy.notificationTemplates[item.template_code as keyof typeof copy.notificationTemplates]
    : undefined;
  return template ?? copy.notifications.genericMessage;
}

export function NotificationTray({ items }: { items: NotificationItem[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const reduce = usePortalReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={wrapper} className="relative">
      <IconButton
        label={t("shell.notifications")}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell size={16} strokeWidth={1.5} />
      </IconButton>

      <AnimatePresence>
        {open ? (
          <motion.div
            role="dialog"
            aria-label={t("shell.notifications.heading")}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.985 }}
            transition={reduce ? { duration: 0 } : { duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="absolute end-0 top-11 z-50 w-[336px] overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-4"
          >
            <div className="flex items-center justify-between gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5">
              <span className="t-micro text-ink-4">{t("shell.notifications.heading")}</span>
              {items.length > 0 ? (
                <span className="t-mono-s text-ink-5">{items.length}</span>
              ) : null}
            </div>

            {items.length === 0 ? (
              // The empty tray used to be one grey sentence with no shape to
              // it. Same sentence, given the portal's empty-state treatment at
              // the size a dropdown can carry.
              <div className="flex flex-col items-center gap-sp-4 px-sp-6 py-sp-9 text-center">
                <IconFrame icon={BellOff} tone="strong" />
                <p className="t-caption max-w-[220px] text-ink-4">
                  {t("shell.notificationsEmpty")}
                </p>
              </div>
            ) : (
              <>
                <ul className="max-h-[52vh] overflow-y-auto">
                  {items.map((item, index) => (
                    <li
                      key={`${item.created_at}-${index}`}
                      className="group border-b border-stroke-subtle px-sp-6 py-sp-5 transition-colors duration-200 last:border-b-0 hover:bg-surface-3"
                    >
                      <div className="flex items-start gap-sp-5">
                        <IconFrame icon={CHANNEL_ICON[item.channel] ?? Bell} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="t-ui text-ink-1">{notificationMessage(item)}</div>
                          <div className="mt-sp-2 flex items-center gap-sp-4">
                            <StatusChip tone={STATUS_TONE[item.status] ?? "muted"}>
                              {copy.labels.notificationStatus[item.status] ?? item.status}
                            </StatusChip>
                            <span className="t-mono-s text-ink-5">
                              {relative(item.sent_at ?? item.created_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>

                {/* The tray showed twenty messages and then stopped, with no
                    way to reach the rest. Activity's Messages tab is the full,
                    paged list and has been all along. */}
                <Link
                  to="/activity"
                  onClick={() => setOpen(false)}
                  className="focus-ring t-ui group flex items-center justify-between gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-5 text-ink-4 transition-colors duration-200 hover:bg-surface-3 hover:text-ink-1"
                >
                  {t("shell.notifications.seeAll")}
                  <ArrowUpRight
                    size={14}
                    strokeWidth={1.6}
                    aria-hidden="true"
                    className="transition-transform duration-200 group-hover:-translate-y-px group-hover:translate-x-px"
                  />
                </Link>
              </>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
