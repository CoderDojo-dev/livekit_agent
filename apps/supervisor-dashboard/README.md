# Supervisor & Admin Dashboard (Phase 11)

A thin read UI over the **business-api** (spec section 17) for Superviseur & Administrateur (CDC section 9).

## Views
- **KPIs** — containment rate, escalation rate, average peak frustration, totals (`/api/v1/kpis`).
- **Escalations** — the open escalation queue (`/api/v1/escalations?status=open`); "Inspect" jumps to the session.
- **Session inspector** — the headline acceptance test: it answers *"why did the system decide as it
  did?"* by showing the **policy verdicts with their justification** (`/api/v1/policy/verdicts`) next
  to the PII-masked transcript and sentiment (`/api/v1/sessions/{id}`).

## Run
```bash
cp .env.example .env     # set VITE_BUSINESS_API_URL (default http://localhost:8108) + VITE_API_ROLE
npm install
npm run dev              # http://localhost:5174
```
`VITE_API_ROLE` is sent as the `X-Role` header on every request (OIDC replaces this at integration).
Build/type-check: `npm run build` (runs `tsc` then `vite build`) or `npm run typecheck`.

If Vite/Rollup reports a missing `@rollup/rollup-linux-x64-gnu` package, the dependencies were installed for a different OS. From the repository root, run:
```bash
bash scripts/fix_frontend_deps.sh
```
