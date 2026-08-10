import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { Button, Card } from "@/components/portal/primitives";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/login")({
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
      await router.navigate({ to: "/assistant" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[380px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <h1 className="t-title-3 text-ink-1">Nexus</h1>
          <p className="t-caption mt-sp-2 text-ink-4">Sign in to your self-service portal.</p>
        </div>

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
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="mt-sp-7 border-t border-stroke-subtle pt-sp-6 text-center">
          <Link to="/signup" className="t-caption text-ink-3 hover:text-ink-1">
            New here? Create your secure sign-in.
          </Link>
        </div>
      </Card>
    </div>
  );
}
