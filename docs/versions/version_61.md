# Version 61 — Ticketing v61: Duplicate Guard, Ownership Enforcement, Triage Read-only

> **Base branch:** `version_60`
> **Files changed:** 5 (+947 / -40) — 3 modified + 2 new
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### Duplicate Ticket Guard

**Problem:** The agent could open multiple tickets for the same problem — nothing prevented it from calling `create_support_ticket` multiple times for the same caller with the same subject.

**Fix:** `create_support_ticket` now runs a **pre-flight duplicate check** before calling MCP. It calls `_list_tickets()` (shared read entry point) and compares against open tickets using `_same_problem()`:

- **Category match**: if the new ticket's category matches an existing open ticket's category, it's a duplicate
- **Keyword match**: if ≥2 significant keywords (>3 chars, non-stop-words) are shared between subjects, it's a duplicate

When a duplicate is found, returns `duplicate_candidate` with matching tickets listed. The agent must ask the caller whether to follow the existing ticket or open a separate one. Only if the caller says yes, call `create_support_ticket` again with `confirm_new=True`.

**Non-regression guarantee:** if `_list_tickets()` fails (ticketing unreachable), the guard is skipped and the ticket is created as before.

### Ownership Enforcement

**Problem:** Any agent could read/modify any ticket by reference, including tickets belonging to other customers — a confidentiality and data-integrity risk.

**Fix:** Every ticket mutation tool now calls `_owned(context, ticket_id)` which cross-references the `ticket_id` against the current caller's own tickets (from `lookup_tickets`). Three outcomes:
- `True` → proceed
- `False` → return `refused` with a **secure message** that discloses nothing about the foreign ticket
- `None` → ticketing unreachable, return `unavailable`

Affected tools: `get_ticket_state`, `mark_ticket_resolved`, `update_support_ticket`, `delete_support_ticket`.

### `mark_ticket_resolved` — Optional Ticket ID

**Problem:** When a caller says "my problem is solved", the agent didn't know which reference to use — and asking for it is unnatural.

**Fix:** `ticket_id` is now optional (default `""`). When empty:
- 0 open tickets → `nothing_to_resolve` (acknowledge the fix, no ticket needed)
- 1 open ticket → auto-resolve it
- 2+ open tickets → `needs_selection` (list subjects, ask which one)

When `ticket_id` is provided, ownership is checked as above.

### `delete_support_ticket` — New Tool

**Purpose:** Withdraw a ticket opened by mistake (caller's own, still-open tickets only).

**Behavior:**
1. Checks ownership via `_owned()` — refuses foreign tickets
2. Checks ticket status via `get_ticket_status` — refuses resolved/closed tickets (they stay in history)
3. Calls MCP `delete_ticket`
4. Returns `deleted` on success, `refused` for non-open/foreign, `failed` if MCP returns no deletion confirmation

### Shared Read Entry Point (`_list_tickets`)

All ticket reads now go through `_list_tickets(context)` which:
1. Resolves the customer from session context
2. Calls `lookup_tickets` MCP tool
3. Returns `(tickets, failure)` tuple

This guarantees every tool sees exactly the same ticket scope — the caller's own tickets.

**`check_customer_tickets`** refactored to use `_list_tickets`, results capped at `_MAX_LISTED` (10) to avoid overwhelming the LLM context.

### TriageAgent — Read-only Ticket Access

**Before:** Triage had no ticket tools at all — if a caller asked "what's the status of my ticket?" at the greeting, Triage couldn't answer and had to route sight-unseen.

**After:** TriageAgent now has `check_customer_tickets` and `get_ticket_state` for **read-only** access. Its instructions say:
- If caller asks about an existing ticket → use these tools and tell them where it stands
- If caller says problem is solved or wants update/withdraw → `route_to_technical` (only TechnicalAgent can write)

Triage does **NOT** have `create_support_ticket`, `mark_ticket_resolved`, `update_support_ticket`, or `delete_support_ticket`.

### TechnicalAgent Instruction Rewrite

The ticketing instructions block was completely rewritten:
- **MANDATORY** (not "may be used"): when relevant, ticketing is required
- First step when a problem is not solved: `check_customer_tickets` BEFORE anything else about tickets
- `mark_ticket_resolved`: leave `ticket_id` empty when caller says solved; handle `needs_selection`/`nothing_to_resolve`
- `create_support_ticket`: handle `duplicate_candidate` outcome; call again with `confirm_new=true` only if caller asks for separate ticket
- `delete_support_ticket`: for mistaken tickets; if refused because resolved/closed, explain it stays in history
- Security rule: if any tool returns `refused`, never argue and never reveal details — ask caller to confirm their own reference

### Validation Bench

| File | Purpose |
|------|---------|
| `scripts/ticket_logic.py` | Shared test doubles: `FakeContext`, `FakeCustomer`, `FakeToolResult`, sample tickets |
| `scripts/ticketing_v61_checks.py` | 47 checks across P0 (vocabulary), P1 (tools), P2 (TechAgent structure), P3 (Triage structure), scenarios 5.6/5.7 |

Run with: `cd scripts && python3 ticketing_v61_checks.py` — exit 0 means all pass.
