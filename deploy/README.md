# Deployment notes

Operational invariants that are enforced by nothing and must therefore be held by hand.
Each one is a rule that is currently satisfied *by accident* of the local topology.

---

## D13 — `policy-service` and `business-api` MUST read the same `POLICY_*` values

### The rule

The deterministic policy engine (`services/policy-service`) is twelve-factor: it reads every
numeric threshold from `POLICY_*` environment variables and never from a table. The admin
dashboard's rule registry (`/policies`) does **not** re-read those numbers from
`reference.business_rules` — that table is the governance record only. Instead
`apps/business-api/src/business_api/policy_view.py` reads the *same* `POLICY_*` variables and
overlays the live enforced values onto each governed rule at read time.

This is deliberate, and it is documented in that module's docstring: it removes registry drift
by construction. But it only works if **both processes see identical values**.

> If `policy-service` and `business-api` are given different `POLICY_*` values, `/policies`
> will confidently display a threshold that is not the one being enforced on live calls.
> There is no error, no warning, and no log line. The dashboard simply lies.

### The variables

Defined in `services/policy-service/src/policy_service/config.py` (`PolicyThresholds`):

| Variable | Default | Mirrored in `policy_view.py`? |
| --- | --- | --- |
| `POLICY_PAYMENT_CAP_TND` | `200.0` | yes |
| `POLICY_DEFERRAL_MIN_AGE_DAYS` | `180` | yes |
| `POLICY_DEFERRAL_MAX_PER_YEAR` | `2` | yes |
| `POLICY_DEFERRAL_UNPAID_THRESHOLD_TND` | `150.0` | yes |
| `POLICY_TOPUP_DENOMINATIONS_TND` | `5,10,20,50` | **no** |
| `POLICY_PLAN_CODES` | *(empty)* | **no** |

The last two are enforced by the engine but are not surfaced in the governance registry at all.
A supervisor reviewing `/policies` cannot see them. Tracked as FEATURE_20 §6-E.

### Why it holds today

`infra/docker-compose/docker-compose.apps.yml` gives both services `env_file: [../../.env]`, and
neither service's `environment:` block overrides any `POLICY_*`. They agree because there is
exactly one file — not because anything verifies it.

### Where it breaks

| Topology | Risk |
| --- | --- |
| Compose, as shipped | Safe. One `.env`, two consumers. |
| Compose with a per-service `environment:` override | **Broken** the moment a `POLICY_*` is set on one service only. |
| Helm / Kubernetes (`deploy/helm`, `infra/helm`) | **Broken by default.** Each chart carries its own ConfigMap/Secret. Nothing makes two charts share a value. |
| Host dev (`make dev` / honcho) | Safe. Both processes inherit one shell environment. |

### The rule to apply

1. Source every `POLICY_*` value from **one** place — a single ConfigMap, a single secret, a
   single `.env` — and mount that same place into **both** `policy-service` and `business-api`.
2. Never set a `POLICY_*` in a per-service `environment:` block or a per-chart `values.yaml`.
3. When adding a threshold, add it in three places or none:
   `PolicyThresholds` (enforcer) → `policy_view._DEFAULTS` + `GOVERNED_BY` (registry) →
   `tests/test_policy_view.py` (the pin that stops the two drifting).

### Verifying it after a deploy

```bash
# The two must print identical values.
docker compose exec policy-service env | grep '^POLICY_' | sort
docker compose exec business-api   env | grep '^POLICY_' | sort
```

On Kubernetes, substitute `kubectl exec deploy/<name> -- env`.

If the two lists differ, `/policies` is misreporting enforced policy. Fix the deployment, not
the dashboard.
