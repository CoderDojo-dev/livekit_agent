# Version 83 — `deploy/README.md`: `POLICY_*` co-location invariant (FEATURE_20 C-3 / D13)

> **Base branch:** `version_82` (`b9f2b84`)
> **Files changed:** 1 (documentation)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none

---

## Containers & SDK

| Item               | Change                          |
|--------------------|---------------------------------|
| New containers     | None                            |
| livekit-agents SDK | `1.6.5` (unchanged)             |
| livekit-server     | `v1.8.4` (unchanged)            |
| Docker Compose     | Unchanged                       |
| Any image rebuild  | **Not required** — documentation only |

---

## What's New in This Branch

The one FEATURE_20 correction known as **C-3 / D13** was applied in the feature lot on
`version_82` ("write the `POLICY_*` invariant into a deployment doc") — the *document* itself
was delivered untracked on disk and is now committed here.

`deploy/README.md` (77 lines) sits directly beside `helm/` and `secrets/` — the two surfaces
that would break the invariant — and documents:

- **The rule**: `services/policy-service` reads every numeric threshold from `POLICY_*`
  environment variables (twelve-factor, never from a table), while the admin dashboard's
  rule registry does **not** re-read `reference.business_rules` — that table is the
  governance record only. `apps/business-api/src/business_api/policy_view.py` reads the
  *same* `POLICY_*` variables and overlays the live enforced values at read time, removing
  registry drift by construction.
- **The failure mode**: if `policy-service` and `business-api` are given different
  `POLICY_*` values, `/policies` silently displays a threshold that is **not** the one
  enforced on live calls — no error, no warning, no log line. "The dashboard simply lies."
- **The variables**: `POLICY_DEFERRAL_MAX_PER_YEAR`, `POLICY_DEFERRAL_MIN_AGE_DAYS`,
  `POLICY_DEFERRAL_UNPAID_THRESHOLD_TND`, `POLICY_PAYMENT_CAP_TND`, `POLICY_SERVICE_URL`,
  mirrored in `policy_view.py`.
- **The live verification**: run `env | grep '^POLICY_'` in both containers and compare.

---

## Validation

- **D13 live check (FEATURE_20 gate #30)**: `docker exec ... sh -c 'env | grep "^POLICY_"'` on
  `policy-service` and `business-api` → **identical output** in both containers (verified).
- Full chain `test_committed.ps1 -Ref version_83`: **140/140 PASS**
  (business-api 28, agent-worker 85, notification 10, policy 17)
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`
- `deploy/` is outside the standing diff gate (`git diff --stat -- services/ infra/ packages/`),
  not Python (ruff/pytest unaffected), no feedback into the running containers.

---

## Out of scope (unchanged)

- All items previously listed as out of scope in v79–v82.