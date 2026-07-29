# Version 67 — AccountServicesAgent: Routing Override Clarification + Knowledge Abstention Cleanup

> **Base branch:** `version_66`
> **Files changed:** 1 (+6 / -5)
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

### AccountServicesAgent Prompt Fixes

Two corrections to the AccountServicesAgent instruction block that were missed in the version_66 merge:

1. **Routing override clarification** — The balance/invoice instruction now explicitly overrides the routing mandate: read-only queries are answered directly with `get_balance_summary` / `get_invoice_summary` without transferring the caller. Only payments and deferrals require `route_to_billing`. This prevents the routing mandate from incorrectly sending a simple balance check to the billing specialist.

2. **Knowledge abstention cleanup** — Removed the manual `KNOWLEDGE_ABSTENTION_RULE` concatenation (which duplicated the rule since `build_persona_instructions` already injects it automatically when `knowledge_search` is in the capability set). The corresponding import from `agents.base_agent` was also removed.
