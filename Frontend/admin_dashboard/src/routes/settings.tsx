import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { pageTitle } from "@/lib/nexus/brand";
import { Card, CardHeader, Button, TextField } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { InlineError } from "@/components/nexus/states";
import { Modal } from "@/components/nexus/modal";
import { changePassword, revokeAllSessions } from "@/lib/api/auth.server";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: pageTitle("Settings") },
      { name: "description", content: "Personal account and session security." },
      { property: "og:title", content: pageTitle("Settings") },
      { property: "og:description", content: "Personal account and session security." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <PageSection index={0}>
      <AccountSecurityPanel />
    </PageSection>
  );
}

function AccountSecurityPanel() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [revokeOpen, setRevokeOpen] = useState(false);

  const change = useMutation({
    mutationFn: () => changePassword({ data: { currentPassword: current, newPassword: next } }),
    onSuccess: () => {
      void router.invalidate().then(() => router.navigate({ to: "/login" }));
    },
  });

  const revoke = useMutation({
    mutationFn: () => revokeAllSessions(),
    onSuccess: () => {
      setRevokeOpen(false);
      void router.invalidate().then(() => router.navigate({ to: "/login" }));
    },
  });

  let localError: string | null = null;
  if (current === "" || next === "" || confirm === "") {
    localError = "All fields are required.";
  } else if (next.length < 10) {
    localError = "Choose a password of at least 10 characters.";
  } else if (next === current) {
    localError = "Choose a password you have not used here before.";
  } else if (next !== confirm) {
    localError = "Passwords do not match.";
  }

  return (
    <Card>
      <CardHeader
        icon={ShieldCheck}
        title="Account Security"
        subtitle="Change your password or sign out of every device."
      />

      <div className="mt-sp-6 flex flex-wrap items-end gap-sp-5">
        <TextField
          label="Current password"
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <TextField
          label="New password"
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <TextField
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button onClick={() => change.mutate()} disabled={localError !== null || change.isPending}>
          {change.isPending ? "Changing..." : "Change password"}
        </Button>
      </div>

      {change.isError ? (
        <div className="mt-sp-5">
          <InlineError error={change.error} />
        </div>
      ) : null}
      {localError !== null && !change.isError ? (
        <p className="t-caption mt-sp-5 text-ink-3">{localError}</p>
      ) : null}

      <div className="mt-sp-6 flex items-center justify-between gap-sp-5 border-t border-stroke-subtle pt-sp-5">
        <p className="t-caption max-w-[48ch] text-ink-4">
          Signing out of all devices closes every session on this account, including this one.
        </p>
        <Button onClick={() => setRevokeOpen(true)} disabled={revoke.isPending}>
          {revoke.isPending ? "Signing out..." : "Sign out of all devices"}
        </Button>
      </div>

      {revoke.isError ? (
        <div className="mt-sp-5">
          <InlineError error={revoke.error} />
        </div>
      ) : null}

      <Modal
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        title="Sign out of all devices"
        description="Every session for this account will be closed. You will have to sign in again."
        footer={
          <>
            <Button onClick={() => setRevokeOpen(false)}>Cancel</Button>
            <Button onClick={() => revoke.mutate()} disabled={revoke.isPending}>
              {revoke.isPending ? "Signing out..." : "Sign out everywhere"}
            </Button>
          </>
        }
      >
        <div className="flex items-start gap-sp-5">
          <AlertTriangle
            size={16}
            strokeWidth={1.5}
            aria-hidden="true"
            className="mt-sp-2 text-ink-3"
          />
          <p className="t-ui text-ink-1">
            This cannot be undone. Sessions on other browsers and devices will stop working
            immediately.
          </p>
        </div>
      </Modal>
    </Card>
  );
}
