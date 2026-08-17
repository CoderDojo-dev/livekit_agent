# COOKBOOK 2 — API / AUTH FOUNDATION

**Backend touched:** none — all six auth routes already exist on `version_92`.
**New dependencies:** none (`sonner` is already installed).
**Fixes:** D‑1 (min length 8 vs 10), D‑2 (staff can sign in), D‑3 (no sign-out anywhere), D‑4 (`Me.kind` union is wrong), plus lockout UX, session restore, and the two write routes nothing calls.

---

## 2.0 The contract, verified in `main.py` + `portal_auth.py`

| Route | Gate | Body in | Body out | Failure → status |
|---|---|---|---|---|
| `POST /api/v1/auth/login` | anonymous, bucket `login:{ip}` | `{email, password}` | `{token, expires_at, email, role, kind, customer_id}` | `invalid_credentials` 401 · `locked` 429 · `rate_limited` 429 |
| `POST /api/v1/auth/signup` | anonymous, bucket `signup:{ip}` limit 10 | `{email, password, cin, msisdn}` | same as login | `signup_failed` 401 · `weak_password` 400 · `rate_limited` 429 |
| `POST /api/v1/auth/logout` | `CurrentPrincipal` | — | `{revoked: bool}` | idempotent |
| `GET /api/v1/auth/me` | `CurrentPrincipal` | — | `{subject, kind, role, account_id, customer_id}` | 401 when the session row is gone |
| `POST /api/v1/auth/password` | `CurrentPrincipal`, 403 if `account_id is None` | `{current_password, new_password}` | `{revoked_sessions: int}` | `invalid_credentials` 401 · `weak_password` 400 |
| `POST /api/v1/auth/sessions/revoke-all` | `CurrentPrincipal`, 403 if `account_id is None` | — | `{revoked: int}` | — |

Hard rules that shape the UI:

* `MIN_PASSWORD_LENGTH = 10`, and `change_password` also rejects **re-using the current password** as `weak_password` → 400.
* `MAX_FAILED_ATTEMPTS = 5`, `LOCKOUT_MINUTES = 15` → the sixth wrong password returns **429**, not 401. `errorMessage()` has no 429 branch today, so the user currently sees a raw upstream detail.
* `signup_client` returns one message for every match failure (“We could not match those details to an account.”). Never add a client-side hint about which field was wrong.
* `change_password` and `revoke-all` both call `revoke_all()`, which kills **the current session too**. The UI must sign the user out immediately after either one; anything else leaves a cookie whose bearer token is dead.
* Bearer tokens are revalidated against `auth.portal_sessions` on **every** request, so one `GET /auth/me` detects a stale cookie.

---

## 2.1 Files

| Action | Path |
|---|---|
| modify | `src/lib/api/session.ts` |
| modify | `src/lib/api/auth.server.ts` |
| modify | `src/lib/api/me.server.ts` |
| modify | `src/lib/api/errors.ts` |
| **add** | `src/lib/api/account.server.ts` |
| modify | `src/routes/login.tsx` |
| modify | `src/routes/signup.tsx` |
| modify | `src/routes/_portal.tsx` |
| **add** | `src/routes/logout.tsx` |
| **add** | `src/components/shell/account-menu.tsx` |
| modify | `src/components/shell/portal-topbar.tsx` |
| modify | `src/routes/_portal/security.tsx` |
| modify | `src/lib/copy.ts` |
| modify | `src/routes/__root.tsx` (mount `<Toaster />`) |

---

## 2.2 `session.ts` — carry `customerId`, keep the HMAC envelope untouched

The cookie is already HMAC-SHA-256 signed, httpOnly, `SameSite=Lax`, and `CLIENT_RANK = { client: 0 }` already exists. Only the payload gains one **optional** field, so an old cookie stays valid.

```diff
 export type PortalSession = {
   token: string;
   email: string;
   role: PortalRole;
   expiresAt: string;
+  /** crm.customers.customer_id, returned by /auth/login and /auth/signup.
+    * Never sent to business-api: /me/* routes derive it from the bearer token.
+    * Held only so the UI can key client-side caches per customer. */
+  customerId?: string;
 };
```

In `verifySession`, extend the shape validation without making the field required:

```diff
   if (
     typeof parsed.token !== "string" ||
     typeof parsed.email !== "string" ||
     typeof parsed.expiresAt !== "string" ||
-    !isPortalRole(parsed.role)
+    !isPortalRole(parsed.role) ||
+    (parsed.customerId !== undefined && typeof parsed.customerId !== "string")
   ) {
     return null;
   }
```

**Do not** rename `SESSION_COOKIE` (`nexus_portal_session`) and **do not** reuse `ADMIN_SESSION_SECRET`; `.env.example` explains why, and `config.ts` throws when `PORTAL_SESSION_SECRET` is missing.

---

## 2.3 `auth.server.ts` — stop hardcoding the role (D‑2)

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { ApiError } from "./errors";
import { businessApi } from "./business-api";
import { setSessionCookie, clearSessionCookie } from "./session.server";

/** Exact shape returned by main.py auth_login / auth_signup. */
type AuthResponse = {
  token: string;
  expires_at: string;
  email: string;
  role: string;
  kind: string;
  customer_id: string | null;
};

/**
 * The portal is a client-only surface. business-api will happily authenticate a
 * conseiller/superviseur/administrateur here, but "client" is absent from
 * _ROLE_RANK, so such a session can reach nothing except /auth/*: the shell
 * would render and then 403 on every read. Refuse at the door instead, and
 * never persist a token we are not going to use.
 */
function assertClient(payload: AuthResponse, path: string): void {
  if (payload.kind !== "client" || !payload.customer_id) {
    throw new ApiError(
      403,
      "This portal is for customer accounts. Staff should use the advisor console.",
      path,
    );
  }
}

const loginInput = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const login = createServerFn({ method: "POST" })
  .validator(loginInput)
  .handler(async ({ data }) => {
    const payload = await businessApi<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: data,
      anonymous: true,
    });

    assertClient(payload, "/api/v1/auth/login");

    await setSessionCookie({
      token: payload.token,
      email: payload.email,
      role: "client",
      expiresAt: payload.expires_at,
      customerId: payload.customer_id,
    });

    return { email: payload.email, customerId: payload.customer_id };
  });

const signupInput = z.object({
  email: z.string().email(),
  /** portal_auth.MIN_PASSWORD_LENGTH === 10. Anything shorter is a certain 400. */
  password: z.string().min(10),
  cin: z.string().min(4).max(8),
  msisdn: z.string().min(6).max(20),
});

export const signup = createServerFn({ method: "POST" })
  .validator(signupInput)
  .handler(async ({ data }) => {
    const payload = await businessApi<AuthResponse>("/api/v1/auth/signup", {
      method: "POST",
      body: data,
      anonymous: true,
    });

    assertClient(payload, "/api/v1/auth/signup");

    await setSessionCookie({
      token: payload.token,
      email: payload.email,
      role: "client",
      expiresAt: payload.expires_at,
      customerId: payload.customer_id,
    });

    return { email: payload.email, customerId: payload.customer_id };
  });

/**
 * Best-effort server-side revocation, then unconditional cookie clear.
 * A 401 here means the session was already gone; the user still ends up out.
 */
export const logout = createServerFn({ method: "POST" }).handler(async () => {
  try {
    await businessApi<{ revoked: boolean }>("/api/v1/auth/logout", { method: "POST" });
  } catch {
    /* already revoked or expired — clearing the cookie is what matters */
  }
  await clearSessionCookie();
  return { ok: true } as const;
});
```

> Keep the file’s own helper names if they differ (`postJson`, `setSession`, `clearSession`, a different anonymous flag) — only the logic above is prescriptive. Verify first:
> `sed -n '1,60p' Frontend/customer_portal/src/lib/api/auth.server.ts`

---

## 2.4 `me.server.ts` — fix the union (D‑4)

```diff
 export type Me = {
   subject: string;
-  kind: "staff" | "customer";
+  /** Principal.kind in infrastructure/auth/principal.py. "service" is the
+    * X-API-Key machine principal; it can never reach the portal, but the type
+    * must not lie about what the endpoint can return. */
+  kind: "staff" | "client" | "service";
   role: string;
   account_id: string | null;
   customer_id: string | null;
 };
```

Keep `fetchProfileDetail` and its 16-field `ProfileDetail` type exactly as they are — they match `me_profile_detail` one-for-one and `/profile` already depends on them. `fetchMe` stops being dead code in §2.7.

---

## 2.5 `errors.ts` — 429 and the client-surface refusal

```diff
+/** 429 — portal_auth lockout (5 failures / 15 min) or the login/signup rate bucket. */
+export function isRateLimited(error: unknown): boolean {
+  return isApiError(error) && error.status === 429;
+}
+
 export function errorMessage(error: unknown): string {
+  if (isRateLimited(error))
+    return "Too many attempts. For your safety, try again in about 15 minutes.";
   if (isForbidden(error)) return "Your account does not grant access to this page.";
   if (isUnauthenticated(error)) return "Your session has expired. Sign in again.";
   if (isApiError(error)) return error.detail || "The service returned an unexpected response.";
   if (typeof error === "string") return error;
   return "Could not reach the service. Check that business-api is running.";
 }
```

Order matters: 429 is checked first, and the lockout message is the single most important string on a login screen. The existing comment (*“Matches require_role() in security.py”*) stays accurate — a 403 from `/me/*` means `current_client` refused a non-client principal.

---

## 2.6 `account.server.ts` — the two write routes nothing calls today

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { clearSessionCookie } from "./session.server";
import { authedMiddleware } from "./middleware";

/**
 * POST /api/v1/auth/password
 *
 * Verified backend behaviour (portal_auth.change_password):
 *  - wrong current password        -> invalid_credentials -> 401
 *  - fewer than 10 characters      -> weak_password       -> 400
 *  - same as the current password  -> weak_password       -> 400
 *  - on success: rotates the hash, stamps password_changed_at, and calls
 *    revoke_all() — THIS SESSION INCLUDED.
 *
 * Because the bearer token dies with the change, the cookie is cleared here and
 * the caller must send the user to /login.
 */
export const changePassword = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      current_password: z.string().min(1),
      new_password: z.string().min(10),
    }),
  )
  .handler(async ({ data }) => {
    const payload = await businessApi<{ revoked_sessions: number }>(
      "/api/v1/auth/password",
      { method: "POST", body: data },
    );
    await clearSessionCookie();
    return payload;
  });

/**
 * POST /api/v1/auth/sessions/revoke-all
 * revoke_all() also kills the caller's own session, so the cookie goes too.
 */
export const revokeAllSessions = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async () => {
    const payload = await businessApi<{ revoked: number }>(
      "/api/v1/auth/sessions/revoke-all",
      { method: "POST" },
    );
    await clearSessionCookie();
    return payload;
  });
```

> Confirm the middleware export name first: `sed -n '1,40p' Frontend/customer_portal/src/lib/api/middleware.ts`.
> Cookbook 3 appends `fetchPortalSessions` to this same file.

---

## 2.7 Guarded routes + session restore

`_portal.tsx` already redirects to `/login` when `getSession()` is empty, with `redirect({ to: "/login", search: { redirect: location.href } })`. Two gaps: an expired-but-present cookie still renders the shell, and `/login` ignores `search.redirect`.

```diff
 export const Route = createFileRoute("/_portal")({
   beforeLoad: async ({ location }) => {
     const session = await getSession();
     if (!session) {
       throw redirect({ to: "/login", search: { redirect: location.href } });
     }
+    // The cookie carries the bearer expiry. business-api revalidates the
+    // session row on every request anyway, so a locally expired cookie can
+    // only produce a shell full of 401s. Bounce it here instead.
+    if (Date.parse(session.expiresAt) <= Date.now()) {
+      throw redirect({ to: "/logout", search: { reason: "expired" } });
+    }
     return { session };
   },
   component: PortalLayout,
 });
```

**Add** `src/routes/logout.tsx` — the one place a session ends, reachable from the menu, from `_portal.tsx`, and from any 401 handler:

```tsx
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
  const { reason = "manual" } = Route.useSearch();

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
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <p className="t-caption text-ink-4" role="status">
        {MESSAGE[reason]}
      </p>
    </div>
  );
}
```

> `/logout` is a **new route file** — `routeTree.gen.ts` must be regenerated and committed, or Cookbook 7’s typecheck fails.

---

## 2.8 `login.tsx` — lockout wording, notice banner, redirect honoured

```diff
+import { z } from "zod";
+
 export const Route = createFileRoute("/login")({
+  validateSearch: z.object({
+    redirect: z.string().optional(),
+    notice: z.enum(["manual", "expired", "password", "revoked"]).optional(),
+  }),
   head: () => ({ /* unchanged */ }),
   component: LoginPage,
 });

 function LoginPage() {
   const router = useRouter();
+  const { redirect, notice } = Route.useSearch();
@@
     try {
       await login({ data: { email, password } });
       await router.invalidate();
-      await router.navigate({ to: "/assistant" });
+      await router.navigate({ to: redirect ?? "/assistant" });
     } catch (caught) {
       setError(caught);
       setPending(false);
     }
```

Above the form, a token-correct notice strip (no new colours):

```tsx
{notice ? (
  <div
    role="status"
    className="t-caption mb-sp-6 rounded-r-2 border border-stroke-subtle bg-surface-2 px-sp-5 py-sp-4 text-ink-3"
  >
    {copy.login.notice[notice]}
  </div>
) : null}
```

Nothing else changes: `errorMessage(error)` now covers 401 (backend detail), 429 (the new lockout sentence), and 403 (the client-surface refusal from §2.3).

---

## 2.9 `signup.tsx` — the certain-400 fix (D‑1)

```diff
-            <span className="t-label text-ink-4">Password (min. 8 characters)</span>
+            <span className="t-label text-ink-4">{copy.signup.passwordLabel}</span>
             <input
               type="password"
               value={password}
               onChange={(event) => setPassword(event.target.value)}
               autoComplete="new-password"
-              minLength={8}
+              minLength={10}
               required
               className={inputClass}
             />
@@
             <input
               type="password"
               value={confirm}
               onChange={(event) => setConfirm(event.target.value)}
               autoComplete="new-password"
-              minLength={8}
+              minLength={10}
               required
               className={inputClass}
             />
@@
-      setError("Passwords do not match.");
+      setError(copy.signup.mismatch);
@@
-      await router.navigate({ to: "/assistant" });
+      await router.navigate({ to: "/profile" });
```

> Why `/profile`: until Cookbook 5 lands, `/assistant` is a scripted demo, while `/profile` is the one screen already backed by real data. Revert this line in Cookbook 5.

Copy additions:

```ts
  signup: {
    title: "Create your sign-in",
    subtitle: "A password keeps your data out of other people's hands.",
    passwordLabel: "Password (at least 10 characters)",
    confirmLabel: "Confirm password",
    cinLabel: "Last 4 digits of your CIN",
    phoneLabel: "Phone number on the account",
    mismatch: "Those two passwords are not the same.",
    submit: "Create my sign-in",
    pending: "Creating your sign-in…",
    haveOne: "Already have a sign-in? Use it here.",
  },
  login: {
    title: "Nexus",
    subtitle: "Sign in to your self-service portal.",
    submit: "Sign in",
    pending: "Signing in…",
    newHere: "New here? Create your secure sign-in.",
    notice: {
      manual: "You are signed out.",
      expired: "Your session expired. Sign in again.",
      password: "Your password was changed. Sign in with the new one.",
      revoked: "All devices were signed out. Sign in again.",
    },
  },
```

---

## 2.10 Sign-out actually exists (D‑3)

**Add** `src/components/shell/account-menu.tsx` — existing primitives and tokens only; the panel uses the `--d-3`/`--ease-out` timings already in `styles.css`:

```tsx
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, LogOut, Shield, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

/**
 * The topbar identity button was inert (no onClick), so the portal had no way
 * out. This is the only sign-out affordance; it routes to /logout, which is the
 * only place that calls the logout server function.
 */
export function AccountMenu({ name, email }: { name: string; email: string }) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

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

  const initials =
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "—";

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={copy.shell.account}
        onClick={() => setOpen((value) => !value)}
        className="focus-ring flex h-9 items-center gap-sp-4 rounded-r-2 px-sp-3 text-ink-3 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-1"
      >
        <span className="t-mono-s flex h-7 w-7 items-center justify-center rounded-r-2 border border-stroke-default bg-surface-3 text-ink-2">
          {initials}
        </span>
        <span className="t-ui hidden max-w-[160px] truncate md:block">{name}</span>
        <ChevronDown
          size={14}
          strokeWidth={1.5}
          className={cn("transition-transform duration-200", open && "rotate-180")}
        />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -4, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.985 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="absolute right-0 top-11 z-30 w-64 overflow-hidden rounded-r-3 border border-stroke-default bg-surface-2 shadow-elev-3"
          >
            <div className="border-b border-stroke-subtle px-sp-6 py-sp-5">
              <div className="t-body-strong truncate text-ink-1">{name}</div>
              <div className="t-caption truncate text-ink-4">{email}</div>
            </div>
            <div className="p-sp-2">
              <MenuLink to="/profile" icon={UserRound} label={copy.shell.menu.profile} onDone={() => setOpen(false)} />
              <MenuLink to="/security" icon={Shield} label={copy.shell.menu.security} onDone={() => setOpen(false)} />
            </div>
            <div className="border-t border-stroke-subtle p-sp-2">
              <MenuLink
                to="/logout"
                search={{ reason: "manual" as const }}
                icon={LogOut}
                label={copy.shell.signOut}
                onDone={() => setOpen(false)}
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function MenuLink({
  to,
  search,
  icon: Icon,
  label,
  onDone,
}: {
  to: string;
  search?: Record<string, string>;
  icon: typeof UserRound;
  label: string;
  onDone: () => void;
}) {
  return (
    <Link
      to={to}
      search={search}
      role="menuitem"
      onClick={onDone}
      className="focus-ring t-ui flex h-9 items-center gap-sp-5 rounded-r-2 px-sp-4 text-ink-3 transition-colors duration-200 hover:bg-surface-3 hover:text-ink-1"
    >
      <Icon size={15} strokeWidth={1.5} />
      {label}
    </Link>
  );
}
```

**Modify** `portal-topbar.tsx`: delete the inert `Search` `IconButton`; replace the inert account `<button>` with `<AccountMenu name={…} email={…} />` fed by the `fetchProfileDetail` query the file already runs (`full_name`, `email`); leave the notification tray for Cookbook 3.

```ts
  shell: {
    // …existing keys…
    menu: { profile: "Your profile", security: "Security" },
  },
```

---

## 2.11 `/security` — two real actions replace three fake ones

After Cookbook 1 removes the MFA callout, the passkeys row, and the “Your data” section, `/security` keeps `signIn`, `sessions`, `activity`. This cookbook wires the first; Cookbook 3 supplies the other two.

```tsx
import { useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { toast } from "sonner";
import { changePassword, revokeAllSessions } from "@/lib/api/account.server";
import { errorMessage } from "@/lib/api/errors";
import { Button } from "@/components/portal/primitives";
import { copy } from "@/lib/copy";

function ChangePasswordPanel() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);

  const inputClass =
    "focus-ring t-ui-regular inline-flex h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5";

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
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
      <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
        placeholder={copy.security.currentPassword} autoComplete="current-password" required className={inputClass} />
      <input type="password" value={next} onChange={(e) => setNext(e.target.value)}
        placeholder={copy.security.newPassword} autoComplete="new-password" minLength={10} required className={inputClass} />
      <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
        placeholder={copy.signup.confirmLabel} autoComplete="new-password" minLength={10} required className={inputClass} />
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
```

> Wording matters: the route is `revoke-all`, which **includes** the current session. `copy.security.signOutAll` currently reads “Sign out of all other devices”, which is false. Change it to “Sign out of every device”.

```ts
  security: {
    // …surviving keys…
    signOutAll: "Sign out of every device",
    currentPassword: "Current password",
    newPassword: "New password",
    passwordRule: "At least 10 characters. Changing it signs you out everywhere.",
    savePassword: "Change password",
    savingPassword: "Changing…",
    passwordChangedSignOut: "Password changed. Signing you out…",
    revokedSignOut: "Signing out every device…",
    revokedCount: (n: number) => `${n} session${n === 1 ? "" : "s"} signed out.`,
    lastChanged: (when: string) => `Last changed ${when}`,
    lastChangedNever: "Never changed",
  },
```

---

## 2.12 Error toasts

`sonner ^2.0.7` is already a dependency (verified) and nothing mounts it. In `__root.tsx`, after `<Outlet />`:

```tsx
import { Toaster } from "sonner";

<Toaster
  position="bottom-right"
  // Token-aligned: sonner draws with these CSS variables, so no hex value
  // enters the codebase and the toast inherits surface/stroke/ink exactly.
  style={
    {
      "--normal-bg": "var(--surface-2)",
      "--normal-text": "var(--ink-1)",
      "--normal-border": "var(--stroke-default)",
    } as React.CSSProperties
  }
  toastOptions={{ className: "t-ui rounded-r-3 shadow-elev-3" }}
/>
```

**Toast policy:** mutations only (password changed, sessions revoked, copy-to-clipboard, retry failed). Read failures render inline inside the section that failed — never a toast — so the page keeps its shape (Cookbook 4 §4.6).

---

## 2.13 Acceptance tests (manual, against a live stack)

Stack: business-api `:8108`, portal `:8080`, `PORTAL_SESSION_SECRET` set, `CORS_ORIGINS` including `http://localhost:8080` (the default is `http://localhost:5174`).

| # | Action | Expected |
|---|---|---|
| 1 | Sign in as a **client** | cookie `nexus_portal_session` set, httpOnly, `SameSite=Lax`; land on `/assistant` or `redirect` |
| 2 | Sign in as **conseiller** | 403 with the staff-console sentence; **no** cookie written |
| 3 | Sign up with a 9-character password | blocked in the browser before any request |
| 4 | Sign up with 10 characters and a wrong CIN | one generic message, no field hint |
| 5 | 6 wrong passwords in a row | attempts 1–5 show the invalid-credentials detail; the 6th shows the 15-minute lockout sentence |
| 6 | Account menu → Sign out | `/logout` → `POST /auth/logout` → `/login?notice=manual`; cookie gone |
| 7 | Delete the session row in the DB, reload | 401 → `/logout?reason=expired` → `/login?notice=expired` |
| 8 | Hand-edit the cookie `expiresAt` into the past | `_portal.tsx` bounces before any `/me/*` call fires |
| 9 | Change password with the wrong current one | toast from the 401 detail; still signed in |
| 10 | Change password to the current one | 400 `weak_password`; still signed in |
| 11 | Change password successfully | `revoked_sessions >= 1`; forced sign-out; new password works, old one 401s |
| 12 | Sign out of every device from two browsers | both land on `/login`; `revoked` ≥ 2 |
| 13 | Tamper with one byte of the cookie signature | `verifySession` returns null → `/login`, no crash |

### Rollback

Every change is additive or a one-line revert. The cookie payload gains an **optional** field, so an old build reads a new cookie without error. No backend state changes.
