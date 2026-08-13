# Version 89 — P2-3 operational soundness, first pass (CI torch CPU path + prepaid profile row)

> **Base branch:** `version_88` (`cc27a69`)
> **Commits:** 1 (P2-3 Bundles K + M — code + cookbook spec)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none (head stays `0017_notification_failure_reason`)
> **Rebuild:** none required (K is workflow-only; M is frontend-only)
> **Frontend:** customer_portal `profile.tsx` (reference row hidden for prepaid)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| livekit-server        | `v1.8.4` (unchanged)                                          |
| Backend service code  | **No Python source touched** (K = workflow, M = frontend)     |
| Image rebuild         | **Not required** for any image                               |
| alembic head          | `0017_notification_failure_reason` (unchanged)                |
| Infra tier            | Left running (postgres/redis/qdrant/minio/otel all started)   |

---

## What's New in This Branch

This is the **first pass of the P2-3 operational-soundness cookbook**
(`features_to_apply/P2-3_operational_soundness.md`). It applies two of the four
bundles. Bundles J (restore `knowledge-service`, H-6) and L (the broken *local*
`.venv` — no repo change) are explicitly **out of scope for this branch**.

### Bundle K — CI truthfulness (closes P1-3's open facts)

`.github/workflows/ci.yml`, `test` job — after the `Install tooling` step, **before**
`Install services, MCP servers and apps`:

```yaml
- name: Install torch (CPU-only) before service deps
  run: pip install --retries 10 --timeout 120 torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

**Why it was needed:** the `test` job installed the services from the default PyPI
index. `services/knowledge-service/pyproject.toml` depends on
`sentence-transformers==3.3.1`, which depends on **torch**, so pip resolved the
**~2 GB CUDA build** (with `nvidia_*` wheels) on every push. The Dockerfile solves
that by installing the **CPU-only** wheel (~118 MB) first so pip satisfies the
dependency from the light wheel — but CI did not replicate that step.

**Properties:**
- Same pin (`2.2.2`) and same index (`download.pytorch.org/whl/cpu`) as the
  image → CI and the container resolve the identical torch build; `2.2.2` is
  load-bearing for the numpy 1.x ABI (`numpy>=1.26,<2` depends on it downstream).
- `--retries 10 --timeout 120` carries J2's transport fix (the hash-mismatch
  retry budget) into CI for free.
- `cache: pip` is already set on this job's `setup-python`, so the CPU wheel is
  cached across runs after the first.
- Deliberately **not** "fixed" by dropping `./services/knowledge-service` from the
  install list — `run_tests.py` target 9 runs that suite, and removing the install
  would recreate exactly the CI/`make test` drift P1-3 existed to end.

### Bundle M — the prepaid customer's empty reference row (M1, option 1)

`Frontend/customer_portal/src/routes/_portal/profile.tsx` — the `reference` row now
renders **only when `account_number` is present**:

```tsx
{me.account_number ? (
  <>
    <Divider />
    <FieldRow label={copy.profile.fields.reference} value={me.account_number} mono
      hint={copy.profile.locked} />
  </>
) : null}
```

**Context:** the backend is *correct* — `billing.accounts = 2 rows / 3 customers`
is domain-correct seeding (`seed_pilot.py`: Amine and Karim are postpaid with
`BA-000021`/`BA-000078`; Yousra is **prepaid**, carrying an OCS `BalanceAccount`
and correctly no billing account, so `/api/v1/me/profile/detail` returns
`account_number: null` for her and **that is permanently correct**). The genuine
defect was presentational: the profile page rendered a permanently-empty
"reference" row for prepaid customers.

Applied **option 1 (recommended)** — hide the row when `account_number` is null.
Smallest diff, no new copy string, no backend change, matches the design system's
conditional-row idiom. The field simply does not exist for prepaid customers —
which is the truth.

---

## Validation

- `ruff check apps/ services/ packages/` → **All checks passed!**
- `customer_portal` `bunx tsc --noEmit` → **exit 0 (clean)**
- `ci.yml` → **YAML VALID** (`yaml.safe_load`)
- Full chain `test_committed.ps1 -Ref version_89`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)
- Infra tier: postgres/redis/qdrant/minio/otel started (postgres healthy);
  policy_verdicts=5, audit_ledger append-only (intact)

### P2-3 grep gates (N2), all green

| Gate | Result |
|---|---|
| CPU index in Dockerfile **and** CI step | ✅ `services/knowledge-service/Dockerfile:17` + `.github/workflows/ci.yml:50` |
| No `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true` assignment in live config | ✅ only env-read in `retriever.py:422` (`== "true"`) + frozen historical docs |
| `torch` in `.github/` is only `2.2.2` CPU index | ✅ 3 hits, all the new step |

---

## Out of scope (this branch)

- **Bundle J** (restore `knowledge-service`, H-6): Dockerfile `--retries`/`--timeout`
  hardening + infra-tier restore + Qdrant bootstrap/outbox drain + cross-lingual J5
  proof — **not applied here**; the image exists locally (`docker-compose-knowledge-service`
  ~2.06 GB, built 7h ago) but `/health` on 8102 currently 000/503 pending the J pass.
- **Bundle L** (broken local `.venv`, untracked): no repo change; `make PYTHON=python3`
  is the documented workaround.
- **J4** when Gate = env kill-switch: only if J2's retry budget cannot retrieve the wheel.
- **K3** lint-job read: root `pyproject.toml:46` already has `ignore_missing_imports = true`
  → the `lint` job is fine as written.
- R12 (GLPI revert), R14 (persona 5 FAIL), R15 (lint ratchet), demo account
  `test-client-403@example.tn` from P2-2 proofs — as documented in §O of the spec.