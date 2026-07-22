# version_48 — NMS + Provisioning Simulators + Live-Only Connector Migration Complete

## Summary
This version **replaces every remaining legacy mock connector with a real Postgres-backed simulator** and hardens the adapter factory so `CONNECTOR_MODE=live` with a missing URL raises `AdapterConfigError` — no silent mock fallback for any operation. The platform is now **live-only by default**: all connectors (OCS/billing, NMS/network-status, provisioning/SIM-lifecycle, payment, CRM, ticketing) point at real services when deployed, and honest failures propagate instead of fake successes.

## New Containers

### NMS Simulator (`services/nms-sim/`)
- **FastAPI service** that serves known network incidents from the `oss.outages` table
- **Endpoint**: `GET /network-status?area=<area>` — returns matching unresolved outages with severity, affected_services, and eta
- **Postgres-backed**: incident data is durable and projectable
- **Seed data**: 3 records (Ariana Ville: major/mobile+data/ETA 2h, Sfax Centre: minor/data/no ETA, Tunis Centre: resolved/ignored)
- **Port**: `8110:8108` in Docker Compose

### Provisioning Simulator (`services/provisioning-sim/`)
- **FastAPI service** that handles the full SIM lifecycle (activate, deactivate, replace, change plan, activate roaming)
- **Endpoints**: `POST /sim/activate`, `/sim/deactivate`, `/sim/replace`, `/sim/change-plan`, `/sim/activate-roaming`
- **In-memory ledger** (Postgres-backed for durability)
- **Port**: `8111:8109` in Docker Compose

## NMS Client (Agent-Worker)
- **`apps/agent-worker/src/clients/nms_client.py`**: typed async HTTP client with trace context injection
- `get_network_status(area)` returns `{area, status, outages[]}` on success, `{status: "unavailable"}` on transport failure
- Cached globally via `@lru_cache` + `get_nms_client()`

## Technical Tools — Live Rewrite
- **`check_network_status`** now calls the real NMS service:
  - Incident found → returns `incident_found=True`, severity, affected_services, eta, full outages list — agent tells the caller the problem is known and being worked on
  - No incident → returns `incident_found=False` — agent can proceed with diagnostics
  - Service unreachable → returns `outcome=unavailable` with message telling agent to report honestly ("I cannot check the network right now") — **never** claims the network is fine when we couldn't verify

## Provisioning Adapter (Integration Adapters)
- **New `ProvisioningPort` protocol** (`packages/domain-core/src/domain_core/ports/provisioning.py`):
  - `activate_sim`, `deactivate_sim`, `replace_sim`, `change_plan`, `activate_roaming`
- **`MockProvisioningAdapter`**: deterministic `MOCK-*-` references for local dev
- **`LiveProvisioningAdapter`**: HTTP client to the provisioning simulator (or carrier HLR in production)
- **`factory.py`**: `get_provisioning_adapter()` registered; raises `AdapterConfigError` on `CONNECTOR_MODE=live` + missing URL

## Execution Service — Live Dispatch Expansion
- `executor.py` now dispatches through `get_provisioning_adapter()`:
  - `CHANGE_PLAN` → `change_plan()`
  - `ACTIVATE_ROAMING` → `activate_roaming()`
  - `UNBLOCK_SIM` → `activate_sim()` (same action)
  - `REPLACE_SIM` → `replace_sim()`
  - `REACTIVATE_SIM` → `activate_sim()`

## TTS Improvements
- **Azure Speech** added as final fallback TTS provider (behind `AZURE_SPEECH_KEY`)
- **Fail-fast**: if zero TTS providers are configured (no ElevenLabs, Cartesia, or Azure key), `build_tts()` raises `RuntimeError` instead of returning an empty `FallbackAdapter` that would leave the agent mute

## Adapter Factory — Final Hardening
- Every adapter (`_pick()`) now raises `AdapterConfigError` when `CONNECTOR_MODE=live` but the adapter's URL is missing
- **Mock is reachable ONLY when `CONNECTOR_MODE=mock` is explicitly selected**
- This covers: OCS, billing, NMS, provisioning, payment, CRM, GLPI ticketing

## Complete Live-Only Migration (All Versions)
| Version | Connector | Before | After |
|---------|-----------|--------|-------|
| v43 | GLPI Ticketing | MockGlpiClient | LiveGlpiClient (REST API) |
| v44 | GLPI Ticketing | CONNECTOR_MODE toggle | Live-only, no mock |
| v45 | GLPI Mapping | N/A | Customer→GLPI user mapping |
| v46 | Notifications | Mock SMS/WhatsApp/Email | Twilio + SMTP, no mock |
| v47 | OCS/Billing | MockOcsAdapter | ocs-billing-sim (Postgres) |
| v48 | NMS / Provisioning | MockNmsAdapter + MockProvisioningAdapter | nms-sim + provisioning-sim (Postgres) |

## Container Changes Summary
| Container | Image | Port | Based On |
|-----------|-------|------|----------|
| `nms-sim` | services/nms-sim/Dockerfile | 8110:8108 | Postgres (oss.outages) |
| `provisioning-sim` | services/provisioning-sim/Dockerfile | 8111:8109 | Postgres (sim ledger) |
| `ocs-billing-sim` | services/ocs-billing-sim/Dockerfile | 8109:8107 | Postgres (billing ledger) |

## SDK / Library Changes
- **No LiveKit SDK version changes**
- `httpx` used for all simulator HTTP communication (already a dependency)

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `services/nms-sim/` (6 files) | NEW | NMS network-status simulator |
| `services/provisioning-sim/` (5 files) | NEW | Provisioning SIM lifecycle simulator |
| `apps/agent-worker/src/clients/nms_client.py` | NEW | Typed NMS HTTP client |
| `packages/domain-core/src/domain_core/ports/provisioning.py` | NEW | ProvisioningPort protocol |
| `packages/integration-adapters/src/integration_adapters/provisioning_adapter.py` | NEW | Mock + Live provisioning adapters |
| `packages/persistence/seed/seed_outages.py` | NEW | NMS incident seed data |
| `apps/agent-worker/src/tools/technical_tools.py` | MODIFIED | Live NMS-backed check_network_status |
| `apps/agent-worker/src/providers/tts.py` | MODIFIED | Azure TTS fallback; empty-provider fail-fast |
| `apps/agent-worker/src/config/settings.py` | MODIFIED | NMS_SERVICE_URL setting |
| `services/execution-service/src/execution_service/executor.py` | MODIFIED | Provisioning dispatch (CHANGE_PLAN, ACTIVATE_ROAMING, SIM ops) |
| `infra/docker-compose/docker-compose.apps.yml` | MODIFIED | nms-sim + provisioning-sim services; agent-worker depends |
| `packages/integration-adapters/src/integration_adapters/__init__.py` | MODIFIED | Export get_provisioning_adapter |
| `packages/integration-adapters/src/integration_adapters/factory.py` | MODIFIED | Provisioning adapter + AdapterConfigError for all |
| `.env.example` | MODIFIED | NMS/provisioning URLs default to simulators |
