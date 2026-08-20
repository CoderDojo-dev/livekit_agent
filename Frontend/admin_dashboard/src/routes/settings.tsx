import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Palette, ShieldCheck, SlidersHorizontal, UserCog } from "lucide-react";
import { pageTitle } from "@/lib/nexus/brand";
import {
  Avatar,
  Button,
  Card,
  CardHeader,
  Segmented,
  TextField,
  Token,
} from "@/components/nexus/primitives";
import { SectionHeading } from "@/components/nexus/blocks";
import { SettingRow, SettingToggle } from "@/components/nexus/setting-row";
import { PageSection } from "@/components/nexus/app-topbar";
import { InlineError } from "@/components/nexus/states";
import { Modal } from "@/components/nexus/modal";
import { changePassword, revokeAllSessions } from "@/lib/api/auth.server";
import { updatePreferences, usePreferences } from "@/lib/nexus/preferences";
import { Route as RootRoute } from "@/routes/__root";
import { ROLE_LABEL } from "@/lib/api/session";
import type { SessionView } from "@/lib/api/auth.server";
import { initials } from "@/lib/nexus/format";

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
  const { session } = RootRoute.useRouteContext();

  return (
    <>
      {/* Identity first: who you are signed in as frames everything below it. */}
      <PageSection index={0}>
        <SectionHeading title="Account" hint="This session" icon={UserCog} />
        <IdentityCard session={session} />
      </PageSection>

      <PageSection index={1}>
        <SectionHeading
          title="Appearance"
          hint="Stored on this device only — never sent to the server"
          icon={Palette}
        />
        <AppearancePanel />
      </PageSection>

      <PageSection index={2}>
        <SectionHeading
          title="Interface"
          hint="How much this console shows you"
          icon={SlidersHorizontal}
        />
        <InterfacePanel />
      </PageSection>

      <PageSection index={3}>
        <SectionHeading title="Security" hint="Password and active sessions" icon={ShieldCheck} />
        <AccountSecurityPanel />
      </PageSection>
    </>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Identity
 * ------------------------------------------------------------------------------------------- */

function IdentityCard({ session }: { session: SessionView | null }) {
  const name = session ? (session.sub.split("@")[0] ?? session.sub) : "—";

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-sp-6">
        <Avatar
          size="xl"
          initials={initials(name.replace(/[._-]/g, " ")) || "··"}
          name={session?.sub ?? "Signed out"}
        />
        <div className="min-w-0">
          <p className="t-title-2 truncate text-ink-1">{name}</p>
          <p className="t-caption mt-sp-2 truncate text-ink-4">{session?.sub ?? "—"}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-sp-4">
          {/* The role is granted by the backend and is not editable here — a Token, not a control,
           * so nobody mistakes it for something they can change. */}
          <Token strong mono={false}>
            {session ? ROLE_LABEL[session.role] : "—"}
          </Token>
          <span className="t-caption text-ink-5">Role is set by an administrator</span>
        </div>
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Appearance
 * ------------------------------------------------------------------------------------------- */

function AppearancePanel() {
  const prefs = usePreferences();

  return (
    <Card>
      <SettingRow
        title="Theme"
        description="Dark is this console's native mode. Light is available for bright rooms and for printing a screen."
        control={
          <Segmented
            groupId="settings-theme"
            items={["Dark", "Light"]}
            active={prefs.theme === "light" ? "Light" : "Dark"}
            onSelect={(label) => updatePreferences({ theme: label === "Light" ? "light" : "dark" })}
          />
        }
      />
      <SettingRow
        title="Text size"
        description="Enlarges reading text — table content, descriptions and captions. Metrics keep their size so the hierarchy still reads at a glance."
        control={
          <Segmented
            groupId="settings-text"
            items={["Default", "Large"]}
            active={prefs.textSize === "large" ? "Large" : "Default"}
            onSelect={(label) =>
              updatePreferences({ textSize: label === "Large" ? "large" : "default" })
            }
          />
        }
      />
      <SettingRow
        title="Reduce motion"
        description="Turns off page transitions, pager cross-fades and the modal animation. Your operating system setting is already respected — this is for when it is not set."
        control={
          <SettingToggle
            name="Reduce motion"
            value={prefs.reduceMotion}
            onChange={(next) => updatePreferences({ reduceMotion: next })}
          />
        }
      />
    </Card>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Interface
 * ------------------------------------------------------------------------------------------- */

function InterfacePanel() {
  const prefs = usePreferences();

  return (
    <Card>
      <SettingRow
        title="Table density"
        description="Compact shortens every table row, fitting roughly a third more records on the same screen."
        control={
          <Segmented
            groupId="settings-density"
            items={["Comfortable", "Compact"]}
            active={prefs.density === "compact" ? "Compact" : "Comfortable"}
            onSelect={(label) =>
              updatePreferences({ density: label === "Compact" ? "compact" : "comfortable" })
            }
          />
        }
      />
      <SettingRow
        title="Queue badges"
        description="Shows open escalations, open tickets and pending callbacks beside their sidebar entries. Turning this off stops the background poll entirely."
        control={
          <SettingToggle
            name="Queue badges"
            value={prefs.showNavCounts}
            onChange={(next) => updatePreferences({ showNavCounts: next })}
          />
        }
      />
      <SettingRow
        title="Keyboard hints"
        description="Pins the shortcut hints in the sidebar instead of revealing them on hover."
        control={
          <SettingToggle
            name="Keyboard hints"
            value={prefs.showShortcuts}
            onChange={(next) => updatePreferences({ showShortcuts: next })}
          />
        }
      />
    </Card>
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
