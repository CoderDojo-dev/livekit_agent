import type { ReactNode } from "react";
import { InlineNotification, Tag } from "@carbon/react";
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-header__title">{title}</h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  );
}
export function ErrorBanner({ title, error }: { title: string; error: string }) {
  return (
    <InlineNotification
      kind="error"
      lowContrast
      hideCloseButton
      title={title}
      subtitle={error}
    />
  );
}
export function VerdictTag({ verdict }: { verdict: string }) {
  const v = verdict.toUpperCase();
  const type = v === "AUTHORIZED" ? "green" : v === "REFUSED" ? "red" : "magenta";
  return (
    <Tag size="sm" type={type}>
      {v}
    </Tag>
  );
}
export function StatusTag({ status }: { status: string }) {
  const s = status.toLowerCase();
  const type =
    s === "succeeded" || s === "online" || s === "resolved" || s === "active"
      ? "green"
      : s === "failed" || s === "offline"
        ? "red"
        : s === "pending" || s === "degraded"
          ? "cyan"
          : "gray";
  return (
    <Tag size="sm" type={type}>
      {status.toUpperCase()}
    </Tag>
  );
}
export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}
