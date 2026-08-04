# Version 81 — Escalation timestamp rendering consolidation + C13 `created_at` sign-off

> **Base branch:** `version_80` (`8d7322d`)
> **Files changed:** 3 (2 frontend, 1 backend)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                          |
|--------------------|---------------------------------|
| New containers     | None                            |
| livekit-agents SDK | `1.6.5` (unchanged)             |
| livekit-server     | `v1.8.4` (unchanged)            |
| Docker Compose     | Unchanged                       |
| Agent-worker image | **No rebuild required** (no agent-worker code change in this branch) |

---

## What's New in This Branch

### 1. Timestamp rendering consolidation (frontend)

- **`escalation-view.ts`**: removed the duplicated `createdLabel()` helper (a local
  locale-specific relative/instant formatter). The C13 follow-up approved in the audit
  replaces it with the shared `formatInstant()` from `audit-view.ts`, so the escalation
  dossier "Raised" row and the audit entries now render timestamps under **one contract**.
- **`escalations.tsx`**: uses `formatInstant(current.created_at)` with a `—` fallback when
  `created_at` is null; the Batch 1 / C13 dossier layout is unchanged.

### 2. C13 `created_at`/`customer_id` sign-off (backend, comment-only)

- **`repositories.py`**: records the **APPROVED** sign-off (2026-08-04) on the JSON-additive,
  nullable-safe `created_at`/`customer_id` keys — Cookbook 13 §8.1/§8.3 had deferred both
  pending review. Purely additive, zero behavioural change.

---

## Validation

- `bunx tsc --noEmit` on `Frontend/admin_dashboard` → **CLEAN** (exit 0)
- business-api suite: **24/24 PASS**
- Full chain `test_committed.ps1 -Ref version_81`: **136/136 PASS**
  (business-api 24, agent-worker 85, notification 10, policy 17)
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`
