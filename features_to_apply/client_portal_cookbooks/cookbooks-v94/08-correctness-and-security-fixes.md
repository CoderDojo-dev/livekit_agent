# Cookbook 8 - Correctness and security fixes

**Target branch:** version_94 (cut from version_93 @ 192c969c35679cdf76f6145e4f0e1776a9abdf5c)
**Backend touched:** apps/token-service/src/token_service/main.py (guarded read of a field that already exists), apps/business-api/src/business_api/me_reads.py (one order_by)
**New dependencies:** none. **Migrations:** none. **Advisor projections widened:** none.
**Files modified:** 6. **Files added:** 0.

Every change below fixes something that landed in version_93. Order matters: 8.1 first, it is the only security item.

---

## 8.1 P0 - stop trusting a browser-supplied MSISDN at POST /token

### What is wrong now

Verified in `apps/token-service/src/token_service/main.py` on version_93:

- the route has no authentication of any kind
- `TokenRequest` now carries `caller_msisdn: str | None = None`
- the handler does `caller_msisdn = req.caller_msisdn or PILOT_MSISDN` and writes it to the room attribute `telecom.caller_msisdn`
- that attribute is how agent-worker decides **which customer it is serving**

Before version_93 the worst an anonymous caller could do was reach the pilot subscriber. Now they can name any MSISDN and the agent resolves that subscriber's plan, balance, invoices and tickets, and will run its write tools against it.

The portal is not the leak. `lib/api/voice.server.ts` is a server function behind `authedMiddleware`, derives room and identity from the signed session cookie, and reads the MSISDN from `fetchProfileDetail()`. The endpoint it calls is simply ungated, so that discipline is voluntary.

### The fix

Honour `caller_msisdn` **only** when the request carries the internal service key. Anything else falls back to `PILOT_MSISDN`, which is exactly today's behaviour for every existing caller.

Why this shape and not "require auth on /token": `apps/client-widget` calls `/token` with no key and must keep working unchanged. This closes the impersonation path without touching it.

### Constants block

Replace:

```python
PILOT_MSISDN = os.getenv("PILOT_MSISDN", "").strip()
CALLER_MSISDN_ATTRIBUTE = "telecom.caller_msisdn"
```

with:

```python
PILOT_MSISDN = os.getenv("PILOT_MSISDN", "").strip()
CALLER_MSISDN_ATTRIBUTE = "telecom.caller_msisdn"

# A caller-supplied MSISDN decides which subscriber the agent resolves, so it is
# only trusted from a caller that proves it is one of our own servers. The
# customer portal's voice.server.ts holds this key already (server-side only);
# apps/client-widget sends neither key nor MSISDN and is unaffected.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()
INTERNAL_KEY_HEADER = "x-internal-api-key"
```

### Handler

Replace the handler's opening:

```python
@app.post("/token", response_model=TokenResponse)
async def token(req: TokenRequest) -> TokenResponse:
    """Mint a 1-hour room-join token (reads LIVEKIT_API_KEY/SECRET from the environment)."""
    room_config = None
```

with:

```python
@app.post("/token", response_model=TokenResponse)
async def token(req: TokenRequest, request: Request) -> TokenResponse:
    """Mint a 15-minute room-join token (reads LIVEKIT_API_KEY/SECRET from the environment).

    caller_msisdn is honoured only for trusted internal callers: it selects the
    subscriber the agent will serve, so an anonymous browser must never choose
    it. Untrusted callers fall back to PILOT_MSISDN, which is the pre-existing
    behaviour for every current client.
    """
    room_config = None
```

and replace:

```python
    caller_msisdn = req.caller_msisdn or PILOT_MSISDN
```

with:

```python
    trusted = bool(INTERNAL_API_KEY) and (
        request.headers.get(INTERNAL_KEY_HEADER, "") == INTERNAL_API_KEY
    )
    if req.caller_msisdn and not trusted:
        logger.warning(
            "ignored caller_msisdn from untrusted caller identity=%s room=%s",
            req.identity,
            req.room,
        )
    caller_msisdn = (req.caller_msisdn if trusted else None) or PILOT_MSISDN
```

Add `Request` to the FastAPI import:

```python
from fastapi import FastAPI, Request
```

Allow the header through CORS, otherwise a browser preflight strips it (the portal calls server-side and does not need this, but a future same-origin caller would):

```python
    allow_headers=["Content-Type", INTERNAL_KEY_HEADER],
```

### Send the key from the portal

In `Frontend/customer_portal/src/lib/api/voice.server.ts`, inside `createVoiceGrant`, replace:

```ts
        headers: { "content-type": "application/json" },
```

with:

```ts
        headers: {
          "content-type": "application/json",
          // Proves this /token call comes from the portal server, which is the
          // only reason token-service will trust caller_msisdn. Never reaches
          // the browser: this handler runs server-side only.
          ...(serverConfig.internalApiKey()
            ? { "x-internal-api-key": serverConfig.internalApiKey() }
            : {}),
        },
```

Add the accessor to `Frontend/customer_portal/src/lib/api/config.ts`, next to `tokenServiceUrl()`, following the pattern already used there for server-only values:

```ts
  /** Server-only. Empty string means "not configured", which downgrades the
   *  grant to PILOT_MSISDN rather than failing the call. */
  internalApiKey: () => (process.env.INTERNAL_API_KEY ?? "").trim(),
```

And document it in `Frontend/customer_portal/.env.example`:

```
# Shared with apps/token-service. Required for the assistant to resolve the
# signed-in customer instead of the pilot subscriber. Server-side only - never
# prefix with VITE_.
INTERNAL_API_KEY=
```

### Degradation is safe, not silent

If `INTERNAL_API_KEY` is unset on either side the call still connects and the agent resolves `PILOT_MSISDN`. That is a wrong-customer experience, so it must be loud where an operator looks: the warning above fires on every ignored MSISDN, and CB11 11.6.3 makes "the agent greets the right customer" an explicit runtime check.

---

## 8.2 CI must actually run the guard it ships

`Frontend/customer_portal/package.json` defines `"verify": "bash scripts/verify-portal.sh"`, the script is committed, and it has never executed anywhere (broken WSL bash locally; the CI job does not call it). A guard enforced nowhere is decoration.

In `.github/workflows/ci.yml`, in the `customer-portal-test` job, insert one step between `Lint` and `Test`:

```yaml
      - name: Lint
        run: npm run lint
      # The 12-check guard has never run on a developer machine (no working
      # bash). Ubuntu runners have one, so this is the first and only place it
      # is actually enforced. Before the build so a banned string or a deleted
      # fixture fails fast.
      - name: Guard (verify-portal.sh)
        run: npm run verify
      - name: Test
        run: npm test
```

Expect the first run to fail here. That is the point: it is the first honest execution of those checks. Read the failing check name, fix the code it names, never weaken the script.

---

## 8.3 A failed balance request must not look like an empty balance

Verified in `routes/_portal/services.tsx`: the error branch is nested inside `dataBalances.length > 0`. When `/me/balance` fails, `balances` is `[]`, the guard is false, and the section plus its `ErrorState` never render. The customer is told nothing.

CB10 rebuilds this screen on `DataSection`. This is the minimal interim fix so the branch is never shipped with an unreachable error state - apply it even if CB10 lands in the same commit, because it is the assertion the acceptance check tests.

Replace:

```tsx
      {dataBalances.length > 0 && (
        <PageSection label={copy.services.balances}>
          {balanceQuery.isError ? (
```

with:

```tsx
      {(dataBalances.length > 0 || balanceQuery.isError) && (
        <PageSection label={copy.services.balances}>
          {balanceQuery.isError ? (
```

---

## 8.4 Transcript turns must be ordered chronologically

Verified in `me_reads.conversation_detail()`:

```python
        .order_by(Turn.turn_index.asc(), Turn.speaker.asc())
```

`speaker` as a tiebreaker sorts alphabetically, so `agent` precedes `caller` inside the same `turn_index` regardless of who actually spoke first. `Turn.created_at` is already selected. Replace with:

```python
        .order_by(Turn.turn_index.asc(), Turn.created_at.asc())
```

This is the only line of `me_reads.py` that CB8 touches.

---

## 8.5 Post-call refresh must not depend on write tools, and the summary must stop guessing

### What is wrong now

Verified in `routes/_portal/assistant.tsx`:

```tsx
    if (session.connectionState !== "disconnected" || !hadWriteTools) return;
```

and

```tsx
            <MetricPair label={copy.assistant.summary.turns} value={copy.assistant.summary.turnsPending} />
```

So after an informational call (no write tool) the conversation list is never invalidated and the call the customer just finished is missing from Activity until a manual reload; and the turn count is a permanent placeholder even though `me_reads.conversations()` returns a real per-session `turns` count.

### The fix

Always refresh the conversation list on disconnect. Keep the write-tool gate only for the broad `["me", customerId]` sweep, because that is the expensive one and only a write can change billing, requests or balances.

```tsx
  // Post-call reconciliation, in two tiers.
  //  - Every call, write tools or not, produced a session row: the conversation
  //    list must show it, otherwise Activity silently lags behind reality.
  //  - Only a write tool can have changed billing, requests or balances, so the
  //    broad sweep stays gated on that.
  // The worker commits after the call ends, hence the delay.
  const customerId = portalSession?.customerId;
  useEffect(() => {
    if (session.connectionState !== "disconnected" || !startedAt || !customerId) return;
    const timer = window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ["me", customerId, "conversations"] });
      if (hadWriteTools) void queryClient.invalidateQueries({ queryKey: ["me", customerId] });
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [session.connectionState, startedAt, hadWriteTools, queryClient, customerId]);
```

Note `startedAt` in the guard: without it the effect fires once on mount, before any call, and invalidates for nothing.

### Real duration and real turn count

Add next to the other hooks in `AssistantStage`:

```tsx
  // After the call the server is the only honest source for how many turns it
  // contained: the browser never sees the persisted turn rows. Enabled only
  // once a call has finished, so an idle Assistant tab issues no requests.
  const recap = useQuery({
    queryKey: qk.conversations(customerId ?? "unknown", 1, 0),
    queryFn: () => fetchConversations({ data: { limit: 1, offset: 0 } }),
    enabled: Boolean(customerId) && !inCall && startedAt !== null,
    staleTime: 0,
    refetchInterval: (query) => (query.state.data?.items.length ? false : 2000),
  });
  const lastCall = recap.data?.items[0];
```

with these imports added to the existing block:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchConversations } from "@/lib/api/activity.server";
import { qk } from "@/lib/query-keys";
```

Then the summary body:

```tsx
          <div className="mt-sp-5 grid grid-cols-2 gap-sp-6">
            <MetricPair
              label={copy.assistant.summary.duration}
              value={
                lastCall?.duration_seconds != null
                  ? duration(lastCall.duration_seconds)
                  : duration((Date.now() - startedAt) / 1000)
              }
            />
            <MetricPair
              label={copy.assistant.summary.turns}
              value={lastCall ? String(lastCall.turns) : copy.assistant.summary.turnsPending}
            />
          </div>
```

The locally measured duration stays as the first paint so the card is never empty, and is replaced by the server's `duration_seconds` the moment the row lands. `turnsPending` stays in `copy.ts` and becomes what it always should have been: a transient state, not a permanent answer.

---

## 8.6 Four defects inside components/portal/data.tsx

All four are in the file CB4 introduced, and all four contradict rules CB4 itself set.

### 8.6.1 AnimatedTabs shares one layoutId across every instance

```tsx
              <motion.span layoutId="tab-underline"
```

A hardcoded literal means two tab groups on one page share one animated element: the underline flies across the screen between them. Parameterise it.

```tsx
export function AnimatedTabs<T extends string>({
  tabs,
  value,
  onChange,
  /** Distinct per tab group on a page: a shared layoutId makes the underline
   *  fly between unrelated groups. Defaults to a stable per-mount id. */
  groupId,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (next: T) => void;
  groupId?: string;
}) {
  const autoId = useId();
  const underlineId = `tab-underline-${groupId ?? autoId}`;
```

```tsx
              <motion.span
                layoutId={underlineId}
```

Add `useId` to the React import at the top of the file:

```tsx
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
```

### 8.6.2 DataSection dims the list on every background refetch

```tsx
            animate={{ opacity: isFetching ? 0.55 : 1 }}
```

Queries use `staleTime: 30_000`, so a window refocus or a routine refetch greys the whole list for no user-initiated reason. Dim only when the visible page is being replaced.

```tsx
  state: { isPending: boolean; isFetching: boolean; isPlaceholderData?: boolean; error: unknown };
```

```tsx
          <motion.div
            // Dim only when the rows on screen are about to be replaced by a
            // different page. A background refresh of the same page must not
            // flash: nothing the customer asked for is changing.
            initial={{ opacity: 0 }}
            animate={{ opacity: state.isPlaceholderData ? 0.55 : 1 }}
            transition={T_BASE}
          >
```

```tsx
  const { isPending, error } = state;
```

Callers that page should pass `placeholderData: keepPreviousData` so `isPlaceholderData` is meaningful; callers that do not simply never dim, which is the correct fallback.

### 8.6.3 Panel claims aria-modal without behaving like one

The comment concedes it: focus is not trapped, the page behind still scrolls, focus is not returned on close. An `aria-modal` surface that leaks focus is worse than a non-modal one, because assistive tech announces a boundary that does not exist.

Replace the `useEffect` inside `Panel` with:

```tsx
  useEffect(() => {
    if (!open) return;

    // Remember where focus came from so Escape returns the customer to the row
    // they opened, not to the top of the page.
    const opener = document.activeElement as HTMLElement | null;

    // Lock the page behind the sheet. Without this, a mobile bottom sheet
    // scrolls the list underneath it.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      // Minimal, dependency-free focus cycle across the sheet's own tabbables.
      const root = sheetRef.current;
      if (!root) return;
      const focusable = root.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    closeRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      opener?.focus?.();
    };
  }, [open, onClose]);
```

Add the ref beside `closeRef`:

```tsx
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
```

and attach it:

```tsx
          <motion.aside
            ref={sheetRef}
            role="dialog"
```

### 8.6.4 TopProgress is a 1px bar described as 2px

The comment says "A 2px line pinned under the sticky topbar"; both wrapper and bar are `h-px`. On a high-DPI display the indicator is effectively invisible, defeating its only purpose.

```tsx
          className="pointer-events-none fixed inset-x-0 top-16 z-30 h-0.5 overflow-hidden"
```

```tsx
            className="h-0.5 w-1/3 bg-ink-3"
```

No token change: `h-0.5` is 2px in the existing scale and `bg-ink-3` is unchanged.

---

## 8.7 Acceptance checks

| # | Check | Command or action | Pass condition |
|---|---|---|---|
| 1 | Untrusted MSISDN ignored | `curl -s -X POST localhost:8107/token -H 'content-type: application/json' -d '{"room":"r","identity":"i","caller_msisdn":"+21690000000"}'` then read the log | log shows `ignored caller_msisdn from untrusted caller`; token carries `PILOT_MSISDN` |
| 2 | Trusted MSISDN honoured | same call plus `-H "x-internal-api-key: $INTERNAL_API_KEY"` | no warning; attribute equals the supplied MSISDN |
| 3 | client-widget unaffected | start a call from apps/client-widget | connects as on version_93; agent resolves PILOT_MSISDN |
| 4 | Key never reaches the browser | `npm run build` then `grep -R "INTERNAL_API_KEY\|x-internal-api-key" .output/public/assets` | zero hits |
| 5 | CI runs the guard | push version_94 | `customer-portal-test` shows an executed `Guard (verify-portal.sh)` step |
| 6 | Balance failure visible | stop business-api, open /services | Balances section renders an inline error with a working Try again |
| 7 | Turn order chronological | open a conversation with a multi-speaker turn | rows in `created_at` order within one turn index |
| 8 | Informational call refreshes | ask only a question, end, wait 5s, open /activity | the call is listed without a reload |
| 9 | Summary resolves | end any call, stay on /assistant | turns becomes a number within ~6s; duration matches the server |
| 10 | No underline flight | two AnimatedTabs on one page | each animates its own underline |
| 11 | No refetch flash | open /activity, switch browser tabs and back | list does not grey out |
| 12 | Panel is a real modal | open a panel, Tab repeatedly, then Escape | focus stays inside; page behind does not scroll; focus returns to the opening row |
| 13 | Progress bar visible | trigger a route change | a 2px line under the topbar |
| 14 | Nothing else moved | `git diff version_93..version_94 --stat` | exactly the 6 files named at the top; `repositories.py` absent |

### Rollback

| Change | Revert | Consequence |
|---|---|---|
| 8.1 token gate | restore `caller_msisdn = req.caller_msisdn or PILOT_MSISDN` | impersonation path reopens |
| 8.2 CI step | delete the step | guard stops running; nothing else breaks |
| 8.3-8.6 | revert per hunk | each is independent; no shared state |
