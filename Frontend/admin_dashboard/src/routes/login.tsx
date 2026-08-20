import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Button, Card, TextField } from "@/components/nexus/primitives";
import { BrandMark } from "@/components/nexus/brand-mark";
import { login } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";
import { BRAND, pageTitle } from "@/lib/nexus/brand";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: pageTitle("Sign in") },
      { name: "description", content: `Authenticate to ${BRAND.name}.` },
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
          {/* The product mark, not a generic login glyph — the sign-in screen is the first place
           * the identity is seen, so it shows the same mark the sidebar does. */}
          <BrandMark className="mb-sp-6 size-[40px] rounded-r-3 [&>svg]:size-[20px]" />
          <h1 className="t-title-3 text-ink-1">{BRAND.name}</h1>
          <p className="t-caption mt-sp-2 text-ink-4">Sign in to continue.</p>
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
