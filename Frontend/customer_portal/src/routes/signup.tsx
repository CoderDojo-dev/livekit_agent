import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { Button, Card } from "@/components/portal/primitives";
import { signup } from "@/lib/api/auth.server";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create your sign-in — Nexus Customer Portal" },
      { name: "description", content: "Secure your self-service access with a portal password." },
    ],
  }),
  component: SignupPage,
});

function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [cin, setCin] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await signup({
        data: {
          email,
          password,
          cin,
          ...(phone ? { phone } : {}),
        },
      });
      await router.invalidate();
      await router.navigate({ to: "/assistant" });
    } catch (caught) {
      setError(caught);
      setPending(false);
    }
  }

  const inputClass =
    "focus-ring t-ui-regular inline-flex h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5";

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8 py-sp-10">
      <Card className="w-full max-w-[420px]">
        <div className="mb-sp-7 text-center">
          <h1 className="t-title-3 text-ink-1">Create your sign-in</h1>
          <p className="t-caption mt-sp-2 text-ink-4">
            A password keeps your data out of other people's hands.
          </p>
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
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">CIN number</span>
            <input
              type="text"
              value={cin}
              onChange={(event) => setCin(event.target.value)}
              autoComplete="off"
              required
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Password (min. 8 characters)</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Confirm password</span>
            <input
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Phone (optional)</span>
            <input
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              autoComplete="tel"
              className={inputClass}
            />
          </label>

          {error ? (
            <p role="alert" className="t-caption text-ink-1">
              {errorMessage(error)}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="mt-sp-2 w-full" disabled={pending}>
            {pending ? "Creating your sign-in…" : "Create my sign-in"}
          </Button>
        </form>

        <div className="mt-sp-7 border-t border-stroke-subtle pt-sp-6 text-center">
          <Link to="/login" className="t-caption text-ink-3 hover:text-ink-1">
            Already have a sign-in? Use it here.
          </Link>
        </div>
      </Card>
    </div>
  );
}
