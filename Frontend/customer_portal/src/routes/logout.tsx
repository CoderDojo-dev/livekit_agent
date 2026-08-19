import { useEffect } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { z } from "zod";
import { logout } from "@/lib/api/auth.server";
import { copy } from "@/lib/copy";

export const Route = createFileRoute("/logout")({
  validateSearch: z.object({
    reason: z.enum(["manual", "expired", "password", "revoked"]).optional(),
  }),
  component: LogoutPage,
});

const MESSAGE = {
  manual: copy.login.notice.manual,
  expired: copy.login.notice.expired,
  password: copy.security.passwordChangedSignOut,
  revoked: copy.security.revokedSignOut,
} as const;

function LogoutPage() {
  const router = useRouter();
  const search = Route.useSearch();
  const reason: "manual" | "expired" | "password" | "revoked" = search.reason ?? "manual";

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await logout();
      if (cancelled) return;
      await router.invalidate();
      await router.navigate({ to: "/login", search: { notice: reason } });
    })();
    return () => {
      cancelled = true;
    };
  }, [reason, router]);

  return (
    <div className="flex min-h-screen items-center justify-center px-sp-8">
      <p className="t-caption text-ink-4" role="status">
        {MESSAGE[reason]}
      </p>
    </div>
  );
}
