# Version 55 — Enforced-threshold Overlay for Policy Rule Registry + Plan Code Normalization

> **Base branch:** `version_54`
> **Files changed:** 9 (+241 / -17)

---

## Containers & SDK

| Item                | Change |
|---------------------|--------|
| New containers      | None   |
| livekit-agents SDK  | No bump|

---

## What's New

### Policy Governance View (spec section 17)

The `reference.business_rules` table previously stored hardcoded numeric thresholds that could silently drift from what the policy engine actually enforces via `POLICY_*` env vars.

- **New `business_api.policy_view` module** — reads the SAME `POLICY_*` env vars the policy engine enforces and overlays live thresholds onto the registry rows at read time. Drift is eliminated by construction.
- **`GET /api/v1/reference/business-rules`** now returns:
  - `definition` = live enforced numbers (not stale DB literals)
  - `enforced=True/False` for each rule
  - `governed_by` = list of env var names
  - `source` = `"policy-engine (POLICY_* env)"`
- **Governed rules:** `RULE_BILLING_CAP` → `POLICY_PAYMENT_CAP_TND` (default 200.0); `RULE_DEFERRAL_ELIGIBILITY` → `POLICY_DEFERRAL_MIN_AGE_DAYS` (180), `POLICY_DEFERRAL_MAX_PER_YEAR` (2), `POLICY_DEFERRAL_UNPAID_THRESHOLD_TND` (150.0)
- **Defaults** match `policy_service.config.PolicyThresholds` exactly, pinned by new test

### Plan Code Normalization

Seed data and provisioning-sim now use canonical product codes instead of display names in the `plan_code` column — one vocabulary lives in the column, the caller still hears the friendly name.

- **`seed_pilot.py`** — plan codes updated: `Postpaid Flexi` → `FLEXI`, `Prepaid Mobile` → `TRANKIL`, `Fibre Fixe` → `FIBER`
- **`provisioning-sim`** — `_resolve_plan()` returns the catalog `product_code` (not name). `change_plan()` resolves legacy name-valued rows to codes before comparison, preventing false "already on this plan" errors
- **`context-service`** — new `CrmRepository._plan_display()` resolves display names from `reference.products` at read time, so `subscription_type` in Customer360 returns `"Postpaid Flexi"` while the column stores `"FLEXI"`

### Supervisor Dashboard

- **BusinessRuleRegistry** — new "Thresholds (enforced)" column showing live values from the policy engine; 6-column skeleton
- **`types.ts`** — `BusinessRule` gains `enforced`, `governed_by`, `source` fields

---

## Fixes Applied

| Before | After |
|--------|-------|
| Rule thresholds stored as DB literals; could drift from engine | Thresholds overlaid from `POLICY_*` env at read time — single source of truth |
| Plan codes stored as display names (`Postpaid Flexi`) | Codes stored as product codes (`FLEXI`); names resolved at read time |
| `change_plan()` could falsely reject when upgrading from legacy name-valued row | Resolves current code before comparison |
| Dashboard showed no threshold column | "Thresholds (enforced)" column with live env values |