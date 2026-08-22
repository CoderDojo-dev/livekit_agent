import { useState, type FormEvent } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { History, KeyRound, Laptop, Monitor, MonitorSmartphone, Smartphone } from "lucide-react";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { changePassword, fetchPortalSessions, revokeAllSessions } from "@/lib/api/account.server";
import { errorMessage } from "@/lib/api/errors";
import { dateTime, deviceLabel, relative } from "@/lib/format";
import {
  Button,
  Card,
  FieldRow,
  IconFrame,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import { ErrorState, PageSection, SkeletonList } from "@/components/portal/data";
import { SettingsNav } from "@/components/portal/settings-nav";

export const Route = createFileRoute("/_portal/security")({
  head: () => ({
    meta: [
      { title: pageTitle("Security") },
      {
        name: "description",
        content: "Manage your sign-in and active devices.",
      },
      { property: "og:title", content: brand.name },
      {
        property: "og:description",
        content: "Sign-in and active devices.",
      },
    ],
  }),
  component: SecurityScreen,
});

const SECTIONS = [
  { id: "signIn", label: copy.security.nav.signIn, icon: KeyRound },
  { id: "sessions", label: copy.security.nav.sessions, icon: MonitorSmartphone },
  { id: "activity", label: copy.security.nav.activity, icon: History },
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
      <SettingsNav
        sections={SECTIONS}
        value={section}
        onChange={setSection}
        label={copy.security.navLabel}
      />

      <div className="space-y-sp-8">
        {section === "signIn" && (
          <PageSection>
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
          </PageSection>
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
                    <li key={s.session_id} className="group flex items-center gap-sp-6 py-sp-6">
                      <IconFrame icon={Icon} tone={s.current ? "strong" : "default"} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-sp-4">
                          <span className="t-body-strong text-ink-1">
                            {deviceLabel(s.user_agent)}
                          </span>
                          {s.current && (
                            <StatusChip tone="solid" live>
                              {copy.security.thisDevice}
                            </StatusChip>
                          )}
                        </div>
                        <div className="t-caption text-ink-4">
                          {s.ip_address ?? copy.common.notApplicable}
                        </div>
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
                  <li key={s.session_id} className="group flex items-center gap-sp-5 py-sp-5">
                    <IconFrame icon={History} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="t-ui text-ink-1">{copy.security.signedIn}</div>
                      <div className="t-caption truncate text-ink-4">
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
