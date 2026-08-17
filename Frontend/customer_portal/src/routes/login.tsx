import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { z } from "zod";
import { Button, Card } from "@/components/portal/primitives";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";
import { copy } from "@/lib/copy";

export const Route = createFileRoute("/login")({
  validateSearch: z.object({
    redirect: z.string().optional(),
    notice: z.enum(["manual", "expired", "password", "revoked"]).optional(),
  }),
  head: () => ({
    meta: [
      { title: "Sign in — Nexus Customer Portal" },
      { name: "description", content: "Authenticate to your self-service portal." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const router = useRouter();
  const search = Route.useSearch();
  const redirect: string | undefined = search.redirect;
  const notice: "manual" | "expired" | "password" | "revoked" | undefined = search.notice;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login({ data: { email, password } });
      await router.invalidate();
      await router.navigate({ to: redirect ?? "/assistant" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[380px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <h1 className="t-title-3 text-ink-1">{copy.login.title}</h1>
          <p className="t-caption mt-sp-2 text-ink-4">{copy.login.subtitle}</p>
        </div>

        {notice ? (
          <div
            role="status"
            className="t-caption mb-sp-6 rounded-r-2 border border-stroke-subtle bg-surface-2 px-sp-5 py-sp-4 text-ink-3"
          >
            {copy.login.notice[notice]}
          </div>
        ) : null}

        <form onSubmit={onSubmit} className="flex flex-col gap-sp-5">
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              required
              className="focus-ring t-ui-regular inline-flex h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
            />
          </label>
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              className="focus-ring t-ui-regular inline-flex h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
            />
          </label>

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? copy.login.pending : copy.login.submit}
          </Button>
        </form>

        <div className="mt-sp-7 border-t border-stroke-subtle pt-sp-6 text-center">
          <Link to="/signup" className="t-caption text-ink-3 hover:text-ink-1">
            {copy.login.newHere}
          </Link>
        </div>
      </Card>
    </div>
  );
}
