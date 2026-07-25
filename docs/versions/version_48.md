# Version 48 — NMS & Provisioning Simulators, Live-only Connector Migration Complete

## What's new
- **New `nms-sim` container**: FastAPI service reading live incident data from `oss.outages` table (port 8110:8108)
- **New `provisioning-sim` container**: SIM lifecycle service (port 8111:8109)
- **NMS client** (`clients/nms_client.py`): typed HTTP client with trace context injection; returns `status='unavailable'` on transport failure (honest, never fabricated 'operational')
- **ProvisioningPort protocol** (`domain-core`): `activate_sim`, `deactivate_sim`, `replace_sim`, `change_plan`, `activate_roaming`
- **MockProvisioningAdapter + LiveProvisioningAdapter**: factory raises `AdapterConfigError` on `CONNECTOR_MODE=live` + missing URL
- **Execution service dispatches** CHANGE_PLAN, ACTIVATE_ROAMING, UNBLOCK_SIM, REPLACE_SIM, REACTIVATE_SIM through provisioning adapter
- **Live-only connector migration complete**: ALL legacy mock connectors replaced by Postgres simulators by default
