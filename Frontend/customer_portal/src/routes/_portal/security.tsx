import { useState, type FormEvent } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Monitor, Smartphone, Laptop } from "lucide-react";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { changePassword, fetchPortalSessions, revokeAllSessions } from "@/lib/api/account.server";
import { errorMessage } from "@/lib/api/errors";
import { dateTime, deviceLabel, relative } from "@/lib/format";
import { Button, Card, FieldRow, SectionLabel, StatusChip } from "@/components/portal/primitives";
import { ErrorState, SkeletonList } from "@/components/portal/data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/security")({
  head: () => ({
    meta: [
      { title: "Security — Nexus Customer Portal" },
      {
        name: "description",
        content: "Manage your Nexus sign-in and active devices.",
      },
      { property: "og:title", content: "Security — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Sign-in and active devices.",
      },
    ],
  }),
  component: SecurityScreen,
});

const SECTIONS = [
  { id: "signIn", label: copy.security.nav.signIn },
  { id: "sessions", label: copy.security.nav.sessions },
  { id: "activity", label: copy.security.nav.activity },
] as const;

const DEVICE_ICON = [Laptop, Smartphone, Monitor];

function ChangePasswordPanel() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);

  const inputClass =
    "focus-ring t-ui-regular inline-flex h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (next !== confirm) {
      toast.error(copy.signup.mismatch);
      return;
    }
    setPending(true);
    try {
      // Success revokes every session, this one included: portal_auth
      // .change_password() calls revoke_all(). Going to /logout is the only
      // correct next step — the bearer token in our cookie is already dead.
      await changePassword({ data: { current_password: current, new_password: next } });
      await router.invalidate();
      await router.navigate({ to: "/logout", search: { reason: "password" } });
    } catch (caught) {
      toast.error(errorMessage(caught));
      setPending(false);
    }
  }

  if (!open) {
    return (
      <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>
        {copy.security.changePassword}
      </Button>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-sp-4 md:max-w-sm">
      <input
        type="password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        placeholder={copy.security.currentPassword}
        autoComplete="current-password"
        required
        className={inputClass}
      />
      <input
        type="password"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        placeholder={copy.security.newPassword}
        autoComplete="new-password"
        minLength={10}
        required
        className={inputClass}
      />
      <input
        type="password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder={copy.signup.confirmLabel}
        autoComplete="new-password"
        minLength={10}
        required
        className={inputClass}
      />
      <p className="t-caption text-ink-4">{copy.security.passwordRule}</p>
      <div className="flex gap-sp-4">
        <Button type="submit" variant="primary" size="sm" disabled={pending}>
          {pending ? copy.security.savingPassword : copy.security.savePassword}
        </Button>
        <Button type="button" variant="quiet" size="sm" onClick={() => setOpen(false)}>
          {copy.common.close}
        </Button>
      </div>
    </form>
  );
}

async function onRevokeAll(router: ReturnType<typeof useRouter>) {
  try {
    const { revoked } = await revokeAllSessions();
    toast.success(copy.security.revokedCount(revoked));
    await router.navigate({ to: "/logout", search: { reason: "revoked" } });
  } catch (caught) {
    toast.error(errorMessage(caught));
  }
}

function SecurityScreen() {
  const router = useRouter();
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("signIn");
  const session = usePortalSession();

  const query = useQuery({
    queryKey: qk.sessions(session?.customerId ?? "unknown"),
    queryFn: () => fetchPortalSessions(),
    staleTime: 30_000,
  });

  if (query.isPending) {
    return <SkeletonList rows={3} />;
  }

  if (query.isError || !query.data) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const { password_changed_at: passwordChangedAt, sessions } = query.data;

  return (
    <div className="grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav className="lg:sticky lg:top-24 lg:self-start">
        <ul className="space-y-sp-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setSection(s.id)}
                className={cn(
                  "focus-ring t-ui flex h-9 w-full items-center rounded-r-2 px-sp-5 text-left transition-colors duration-200",
                  section === s.id
                    ? "bg-surface-3 text-ink-1"
                    : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                )}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-sp-8">
        {section === "signIn" && (
          <Card>
            <SectionLabel>{copy.security.signIn}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <FieldRow
                label={copy.security.password}
                value={
                  passwordChangedAt
                    ? copy.security.lastChanged(relative(passwordChangedAt))
                    : copy.security.lastChangedNever
                }
                action={<ChangePasswordPanel />}
              />
            </div>
          </Card>
        )}

        {section === "sessions" && (
          <Card>
            <SectionLabel
              right={
                sessions.length > 0 ? (
                  <Button variant="secondary" size="sm" onClick={() => void onRevokeAll(router)}>
                    {copy.security.signOutAll}
                  </Button>
                ) : null
              }
            >
              {copy.security.sessions}
            </SectionLabel>
            {sessions.length === 0 ? (
              <p className="t-caption mt-sp-6 text-ink-5">{copy.security.sessionsEmpty}</p>
            ) : (
              <ul className="mt-sp-6 divide-y divide-stroke-subtle">
                {sessions.map((s, i) => {
                  const Icon = DEVICE_ICON[i % DEVICE_ICON.length]!;
                  return (
                    <li key={s.session_id} className="flex items-center gap-sp-6 py-sp-6">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                        <Icon size={16} strokeWidth={1.5} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-sp-4">
                          <span className="t-body-strong text-ink-1">
                            {deviceLabel(s.user_agent)}
                          </span>
                          {s.current && (
                            <StatusChip tone="solid">{copy.security.thisDevice}</StatusChip>
                          )}
                        </div>
                        <div className="t-caption text-ink-4">{s.ip_address ?? "—"}</div>
                      </div>
                      <span className="t-mono-s shrink-0 text-ink-5">
                        {relative(s.signed_in_at)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        )}

        {section === "activity" && (
          <Card>
            <SectionLabel>{copy.security.activity}</SectionLabel>
            {sessions.length === 0 ? (
              <p className="t-caption mt-sp-6 text-ink-5">{copy.empty.generic}</p>
            ) : (
              <ul className="mt-sp-6 divide-y divide-stroke-subtle">
                {sessions.map((s) => (
                  <li
                    key={s.session_id}
                    className="flex items-center justify-between gap-sp-6 py-sp-5"
                  >
                    <div className="min-w-0">
                      <div className="t-ui text-ink-1">{copy.security.signedIn}</div>
                      <div className="t-caption text-ink-4">
                        {deviceLabel(s.user_agent)}
                        {s.ip_address ? ` · ${s.ip_address}` : ""}
                      </div>
                    </div>
                    <span className="t-mono-s shrink-0 text-ink-5">{dateTime(s.signed_in_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
