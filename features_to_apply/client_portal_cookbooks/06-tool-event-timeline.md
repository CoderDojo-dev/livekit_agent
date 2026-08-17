# COOKBOOK 6 — TOOL / EVENT TIMELINE EXPERIENCE

**Backend touched:** none. **New dependencies:** none. **Depends on:** Cookbook 5 (the LiveKit text-stream subscription).
**Goal:** the customer sees *“Checked your account securely”*, never `function_tools_executed: check_network_status`.

---

## 6.0 The exact wire contract (verified in `apps/agent-worker/src/frontend_events.py`)

Topic: **`telecom.tool-events`**. Payload, published once per completed tool call:

```json
{
  "version": 1,
  "kind": "tool",
  "id": "<function_call.call_id>",
  "name": "<tool_name>",
  "label": "<safe display label>",
  "status": "done" | "error",
  "created_at": <number>
}
```

Four properties of this channel decide the entire design, and three of them are usually got wrong:

1. **Arguments and outputs are never published.** The module docstring says so explicitly: they “can contain customer, authentication, billing, or account data”. There is no amount, no MSISDN, no ticket number on this channel — so the timeline can never show one. Do not try.
2. **The event is terminal, not a start signal.** It is emitted from `FunctionToolsExecutedEvent`, i.e. **after** the tool ran. A present-progressive label (“Reading invoice information”) arriving at completion time is slightly dishonest — the portal therefore renders **completed** wording and gets its “in flight” feeling from `agent.state === "thinking"`, which *is* a live signal.
3. **Publishing is best-effort.** `_send` swallows every exception at `logger.debug` level, and `_spawn` never awaits. Events can be missing. The UI must be additive-only: an absent event is normal, never an error state.
4. **The label is already sanitised.** `_safe_label` strips everything outside `[a-zA-Z0-9_ -]`, replaces `_` with spaces, truncates to 64 characters, and title-cases the rest, defaulting to “Service action”. So even an unknown tool cannot print a raw symbol — but it can print something machine-ish like “Check Network Status”, which is why the portal keeps its own map keyed on `name`.

The 15 mapped tool names (verified, complete): `knowledge_search`, `get_invoice_summary`, `get_balance_summary`, `get_plan_details`, `route_to_billing`, `route_to_technical`, `escalate_to_manager`, `verify_with_known_element`, `record_consent`, `change_plan`, `execute_payment`, `unblock_sim`, `replace_sim`, `create_ticket`, `schedule_callback`.

---

## 6.1 Files

| Action | Path |
|---|---|
| **add** | `src/lib/tool-events.ts` |
| **add** | `src/components/assistant/tool-event-row.tsx` |
| **add** | `src/components/assistant/working-indicator.tsx` |
| modify | `src/components/assistant/live-stream.tsx` (Cookbook 5) |
| modify | `src/lib/copy.ts` |

---

## 6.2 `src/lib/tool-events.ts` — parse, validate, translate

```ts
import { copy } from "@/lib/copy";

/**
 * Mirror of the payload published by apps/agent-worker/src/frontend_events.py.
 * version and kind are part of the contract and are validated, not assumed.
 */
export type ToolEvent = {
  version: 1;
  kind: "tool";
  id: string;
  name: string;
  label: string;
  status: "done" | "error";
  created_at: number;
};

/**
 * Strict parse. Anything that is not exactly the documented shape is dropped:
 * an unrecognised message must never reach the screen, and must never throw.
 * Same validation the client-widget performs (verified in live-conversation.tsx).
 */
export function parseToolEvent(text: string): ToolEvent | null {
  try {
    const value = JSON.parse(text) as Partial<ToolEvent>;
    if (
      value.version !== 1 ||
      value.kind !== "tool" ||
      typeof value.id !== "string" ||
      typeof value.name !== "string" ||
      typeof value.label !== "string" ||
      (value.status !== "done" && value.status !== "error")
    ) {
      return null;
    }
    return value as ToolEvent;
  } catch {
    return null;
  }
}

/** LiveKit timestamps arrive in seconds or milliseconds. Verified helper. */
export function timestampMs(value: number | Date | undefined): number {
  if (value instanceof Date) return value.getTime();
  if (typeof value !== "number") return Date.now();
  return value < 10_000_000_000 ? value * 1000 : value;
}

/**
 * Customer-facing wording, keyed on the tool NAME (stable) rather than the
 * worker's label (display text that may be reworded upstream).
 *
 * Tense: the event is terminal, so every phrase is completed. The live "checking
 * now" feeling comes from agent.state === "thinking", which is a real-time
 * signal; faking it here would mean claiming work is in flight after it has
 * already finished.
 *
 * Never mention an amount, a number, or an identifier: this channel carries none.
 */
const DONE: Record<string, string> = {
  knowledge_search: "Looked up how this works",
  get_invoice_summary: "Checked your invoice",
  get_balance_summary: "Checked your balance",
  get_plan_details: "Checked your plan",
  route_to_billing: "Brought in billing support",
  route_to_technical: "Brought in technical support",
  escalate_to_manager: "Arranged a specialist for you",
  verify_with_known_element: "Confirmed it is really you",
  record_consent: "Saved your choice",
  change_plan: "Reviewed the plan change",
  execute_payment: "Handled your payment request",
  unblock_sim: "Checked your SIM",
  replace_sim: "Started your SIM replacement",
  create_ticket: "Opened a request for you",
  schedule_callback: "Scheduled a call back",
};

/**
 * Failure wording. Deliberately non-technical and non-alarming: the customer is
 * told what did not happen, never why. The reason is not on this channel, and
 * even if it were, a gateway or policy message is not customer copy.
 */
const FAILED: Record<string, string> = {
  knowledge_search: "Could not find that just now",
  get_invoice_summary: "Could not read your invoice just now",
  get_balance_summary: "Could not read your balance just now",
  get_plan_details: "Could not read your plan just now",
  route_to_billing: "Could not reach billing support",
  route_to_technical: "Could not reach technical support",
  escalate_to_manager: "Could not arrange a specialist yet",
  verify_with_known_element: "Could not confirm your identity",
  record_consent: "Could not save your choice",
  change_plan: "Could not complete the plan change",
  execute_payment: "Could not complete the payment",
  unblock_sim: "Could not unblock your SIM",
  replace_sim: "Could not start the SIM replacement",
  create_ticket: "Could not open the request",
  schedule_callback: "Could not schedule the call back",
};

/**
 * Resolution order:
 *   1. our own map, keyed on the stable tool name;
 *   2. the worker's own _safe_label, which is already sanitised;
 *   3. a neutral fallback.
 * A tool added upstream therefore degrades to acceptable wording instead of
 * either crashing or printing a symbol.
 */
export function toolEventText(event: ToolEvent): string {
  const table = event.status === "error" ? FAILED : DONE;
  const mapped = table[event.name];
  if (mapped) return mapped;
  if (event.label && event.label !== "Service action") return event.label;
  return event.status === "error"
    ? copy.assistant.tools.genericFailed
    : copy.assistant.tools.genericDone;
}

/**
 * Coarse grouping used only for the icon. No customer-visible string derives
 * from it, so an unknown tool simply gets the neutral icon.
 */
export type ToolKind = "account" | "billing" | "network" | "support" | "security" | "other";

export function toolKind(name: string): ToolKind {
  if (name.startsWith("get_invoice") || name === "execute_payment") return "billing";
  if (name === "get_balance_summary" || name === "get_plan_details" || name === "change_plan")
    return "account";
  if (name === "unblock_sim" || name === "replace_sim") return "network";
  if (
    name === "create_ticket" ||
    name === "schedule_callback" ||
    name.startsWith("route_to") ||
    name === "escalate_to_manager"
  )
    return "support";
  if (name === "verify_with_known_element" || name === "record_consent") return "security";
  return "other";
}
```

---

## 6.3 `tool-event-row.tsx`

```tsx
import { motion } from "motion/react";
import {
  Check,
  CircleAlert,
  CreditCard,
  Headset,
  Search,
  ShieldCheck,
  SignalHigh,
  UserRound,
} from "lucide-react";
import { toolKind, type ToolKind } from "@/lib/tool-events";
import { T_MICRO } from "@/components/portal/data";
import { cn } from "@/lib/utils";
import { copy } from "@/lib/copy";

const ICON: Record<ToolKind, typeof Search> = {
  account: UserRound,
  billing: CreditCard,
  network: SignalHigh,
  support: Headset,
  security: ShieldCheck,
  other: Search,
};

/**
 * One completed service action.
 *
 * Deliberately quieter than a transcript bubble: it is context, not speech.
 * A failure is marked with a neutral alert glyph and muted ink — there is no
 * red anywhere in the palette (13 greys), and inventing one would break the
 * identity.
 */
export function ToolEventRow({
  name,
  text,
  status,
}: {
  name: string;
  text: string;
  status: "done" | "error";
}) {
  const Icon = ICON[toolKind(name)];
  const failed = status === "error";

  return (
    <div className="flex items-center gap-sp-5">
      <span
        aria-hidden="true"
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-r-2 border",
          failed
            ? "border-dashed border-stroke-strong bg-surface-2 text-ink-4"
            : "border-stroke-subtle bg-surface-3 text-ink-3",
        )}
      >
        <Icon size={14} strokeWidth={1.5} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="t-micro-2 text-ink-5">{copy.assistant.tools.heading}</div>
        <p dir="auto" className={cn("t-ui mt-sp-1 truncate", failed ? "text-ink-3" : "text-ink-2")}>
          {text}
        </p>
      </div>

      <motion.span
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={T_MICRO}
        aria-label={failed ? copy.assistant.tools.failed : copy.assistant.tools.done}
        className={cn("shrink-0", failed ? "text-ink-4" : "text-ink-2")}
      >
        {failed ? <CircleAlert size={14} strokeWidth={1.5} /> : <Check size={14} strokeWidth={1.5} />}
      </motion.span>
    </div>
  );
}
```

---

## 6.4 `working-indicator.tsx` — the honest “assistant is checking…”

This is the piece that delivers the feeling you asked for, and it is driven by a **live** signal (`agent.state`), not by a completion event.

```tsx
import { AnimatePresence, motion } from "motion/react";
import { T_BASE } from "@/components/portal/data";
import { copy } from "@/lib/copy";

/**
 * Shown while agent.state === "thinking".
 *
 * The wording is intentionally generic ("Checking this for you…") because at
 * this moment the portal genuinely does not know which tool is running: tool
 * events only arrive once execution has finished. Naming a specific check here
 * would be a guess.
 *
 * Three dots on the existing shimmer rhythm; no spinner, which does not exist
 * anywhere in this design system.
 */
export function WorkingIndicator({ active }: { active: boolean }) {
  return (
    <AnimatePresence>
      {active ? (
        <motion.div
          key="working"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={T_BASE}
          className="flex items-center gap-sp-4 rounded-r-4 border border-stroke-subtle bg-surface-2 px-sp-6 py-sp-5"
          role="status"
        >
          <span className="flex items-center gap-sp-2" aria-hidden="true">
            {[0, 1, 2].map((index) => (
              <motion.span
                key={index}
                className="h-1 w-1 rounded-full bg-ink-3"
                animate={{ opacity: [0.25, 1, 0.25] }}
                transition={{
                  duration: 1.1,
                  ease: "easeInOut",
                  repeat: Infinity,
                  delay: index * 0.16,
                }}
              />
            ))}
          </span>
          <span className="t-ui text-ink-3">{copy.assistant.tools.working}</span>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
```

Mount it inside `LiveStream`, above the item stack:

```tsx
<WorkingIndicator active={agent.state === "thinking"} />
```

---

## 6.5 Persona / agent transitions

Two different sources, and only one of them is live:

| Signal | Availability | Use |
|---|---|---|
| `Turn.active_agent` | **persisted**, appears in the transcript projection from Cookbook 3 (`turns[].agent`) | persona label on `/activity` transcripts |
| `route_to_billing` / `route_to_technical` / `escalate_to_manager` tool events | **live** during the call | render the handoff as a service action, and let the wording carry the persona change |

There is **no dedicated persona-change channel** on `telecom.tool-events` — the only `kind` published is `"tool"` (verified). So a live “now speaking with Billing” banner cannot be derived from a first-class event; it is inferred from the routing tool events above. Say that in the code comment rather than inventing a channel.

For persona display names, map the worker’s internal agent identifiers to customer wording. **Read them first** — do not guess:

```sh
git grep -n "active_agent" -- apps/agent-worker/src | head -n 20
git grep -rn "agent_name\|Agent(" -- apps/agent-worker/src | head -n 30
```

Then fill the map with the values that actually appear (leave unknown keys to the fallback):

```ts
  personas: {
    // Keys are conversation.turns.active_agent values produced by the worker.
    // Confirm each one with the grep above before adding it here.
    fallback: "Assistant",
    // e.g. triage: "Assistant", billing: "Billing support",
    //      technical: "Technical support", supervisor: "Specialist",
  },
```

Render rule: `copy.personas[turn.agent ?? ""] ?? copy.personas.fallback`. A raw identifier such as `billing_agent_v2` must never reach the screen.

When the persona label changes between two consecutive agent turns, render a one-line divider inside the transcript instead of repeating the label on every bubble:

```tsx
<div className="flex items-center gap-sp-4">
  <span className="t-micro-2 text-ink-5">{copy.assistant.tools.nowWith(personaLabel)}</span>
  <span className="h-px flex-1 bg-stroke-subtle" />
</div>
```

---

## 6.6 Ticket / payment / network / callback outcomes

You asked for these to be visible. Here is exactly how far `version_92` allows it, with no invention:

| Wanted | Available live? | Honest implementation |
|---|---|---|
| “Request opened” | yes — `create_ticket` tool event (name + status only) | “Opened a request for you” during the call; the **reference number** is not on the channel, so after the call refetch `qk.requests(cid, undefined, 10, 0)` and show the real ticket |
| “Payment taken” | partial — `execute_payment` event with `done`/`error` only | “Handled your payment request”; the amount and receipt come from `/me/billing` afterwards, never from the event |
| “Network status” | only if such a tool exists in the label map — it does **not**; `unblock_sim` / `replace_sim` are the SIM-side tools | do **not** invent “Verifying network status…”. If a network-check tool is added to the worker later, add its key to `DONE`/`FAILED` and it appears automatically |
| “Callback scheduled” | yes — `schedule_callback` | “Scheduled a call back”; the actual time comes from `/me/callbacks` afterwards |

**Post-call reconciliation** (the piece that makes the timeline trustworthy). On `session.connectionState === "disconnected"` after a call that emitted at least one of `create_ticket`, `schedule_callback`, `execute_payment`, `change_plan`:

```ts
useEffect(() => {
  if (session.connectionState !== "disconnected" || !hadWriteTools) return;
  // The worker's writers commit after the call; give them a moment, then let
  // the server be the source of truth for anything that changed.
  const timer = window.setTimeout(() => {
    void queryClient.invalidateQueries({ queryKey: ["me", customerId] });
  }, 4000);
  return () => window.clearTimeout(timer);
}, [session.connectionState, hadWriteTools, queryClient, customerId]);
```

This is why the summary card links to `/activity` and `/requests` instead of asserting outcomes itself.

---

## 6.7 Copy

```ts
  assistant: {
    // …
    tools: {
      heading: "SERVICE ACTION",
      working: "Checking this for you…",
      done: "Completed",
      failed: "Did not complete",
      genericDone: "Checked something for you",
      genericFailed: "Could not finish that just now",
      nowWith: (persona: string) => `Now with ${persona}`,
    },
  },
```

Banned strings, enforced by grep in Cookbook 7: `function_tools_executed`, `tool_call`, `call_id`, `knowledge_search`, `get_invoice_summary`, `get_balance_summary`, `get_plan_details`, `route_to_`, `escalate_to_manager`, `verify_with_known_element`, `record_consent`, `change_plan`, `execute_payment`, `unblock_sim`, `replace_sim`, `create_ticket`, `schedule_callback` — outside `src/lib/tool-events.ts`, where they are map keys and never rendered.

---

## 6.8 Acceptance

| # | Check | Expected |
|---|---|---|
| 1 | Ask the assistant a question that triggers `knowledge_search` | “Looked up how this works” with a tick, within ~1 s of completion |
| 2 | Ask for the balance | “Checked your balance” — **no amount** in the row |
| 3 | Force a tool failure (stop the dependent service) | “Could not read your balance just now”, alert glyph, no reason, no red |
| 4 | Ask for a specialist | “Arranged a specialist for you”, then the persona divider on the next agent turn |
| 5 | While the agent works | `WorkingIndicator` visible for the whole `thinking` state and gone the instant it ends |
| 6 | Publish a malformed event (`version: 2`) on the topic | silently ignored; nothing renders; no console error |
| 7 | Add an unmapped tool upstream | the worker’s `_safe_label` text is shown, never a raw symbol |
| 8 | Ask the assistant to open a request | live row during the call; after ~4 s `/requests` shows the real ticket with its reference |
| 9 | Grep the built client for banned strings | `grep -rE "function_tools_executed\|call_id" dist/client` → nothing |
| 10 | Read the row aloud with a screen reader | the label plus “Completed” / “Did not complete”, no glyph noise |
| 11 | Twelve tool events in one call | only the last three items remain in the stack (Cookbook 5 `MAX_VISIBLE_ITEMS`); no scrollbar, no overlap |

### Rollback

Three new files plus one copy block. Reverting them leaves Cookbook 5’s transcript working with the client-widget’s original neutral tool row.
