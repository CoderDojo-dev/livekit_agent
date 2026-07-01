## 1. Phase 10: Frontend Integration
Successfully integrated the browser-based caller interface.

- **Token Service (`apps/token-service`)**: Deployed a FastAPI backend to mint LiveKit JWT tokens.
- **Client Widget (`apps/client-widget`)**: Deployed a React 19 + Vite frontend allowing users to "Start Call" directly from the browser.
- **Dependencies**: All Node.js and Python packages for these services have been installed.

---

## integration recap
## 2. Persistence P1: Postgres Foundation
The platform has transitioned from mock data to a real **PostgreSQL** data layer for CRM, Billing, and OCS.

### Key Accomplishments:
- **Patch Application**: Copied all core files including `packages/persistence`, `services/context-service`, and infrastructure deployment scripts.
- **Postgres Deployment**: Started the `telecom-postgres` container via Docker Compose.
    - **Note on Ports**: To avoid conflict with the existing LiveKit database (port 5432), the new platform database is exposed on **localhost:15432**.
- **Schema Migration**: Ran `alembic upgrade head` to initialize all 12 platform schemas and required extensions (UUID-ossp).
- **Seed Data Success**: 
    - Encountered an ORM relationship issue in the initial `seed_pilot.py` script.
    - **Fixed**: Patched the SQLAlchemy models in `billing.py` and `ocs.py` to include missing `customer` and `subscription` relationships.
    - **Result**: Successfully seeded the 3 canonical pilot users (Amine, Yousra, Karim) into the database.

---

## 3. How to Verify & Run

### A. Environment Setup
Set the database URL in your shell:
```powershell
# Windows PowerShell
$env:DATABASE_URL="postgresql+psycopg://telecom:telecom@localhost:15432/telecom"
```

### B. Run the Context Service
This service is now fully wired to use the real Postgres database:
```powershell
cd services/context-service
uvicorn context_service.main:app --port 8101
```

### C. Test Endpoints
In a separate terminal, you can now query real database records:
```bash
# Resolve MSISDN to Customer UUID
curl "http://localhost:8101/internal/context/resolve?msisdn=+21620155320"

# Fetch Customer 360 View (Amine)
curl "http://localhost:8101/context/+21620155320"
```

---

## Next Steps
- **Phase 11**: Begin work on Observability & Supervision (OTel, KPIs, and Audit-chain).
- **Persistence P2**: Migration of Ticketing and Decision tracking to the Postgres layer.
