import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { LogIn } from "lucide-react";
import { Button, Card, TextField } from "@/components/nexus/primitives";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Nexus" },
      { name: "description", content: "Authenticate to the Nexus admin console." },
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
      await router.navigate({ to: "/overview" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[380px]">
        <div className="mb-sp-7 flex flex-col items-center text-center">
          <span className="mb-sp-6 inline-flex size-[40px] items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-4">
            <LogIn size={18} strokeWidth={1.5} />
          </span>
          <h1 className="t-title-3 text-ink-1">Nexus</h1>
          <p className="t-caption mt-sp-2 text-ink-4">Sign in to the admin console.</p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-sp-5">
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
