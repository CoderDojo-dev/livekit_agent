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

/**
 * Tools that write to the customer's account. After a call that ran any of
 * these, the server-side writers have real records to show, so the portal
 * refetches activity shortly after the call ends.
 */
const WRITE_TOOLS = new Set<string>([
  "create_ticket",
  "schedule_callback",
  "execute_payment",
  "change_plan",
]);

export function isWriteTool(name: string): boolean {
  return WRITE_TOOLS.has(name);
}
