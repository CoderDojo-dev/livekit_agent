"""NMS/OSS simulator service (dev-only, but a REAL projection of oss.outages).

Implements the exact endpoint the LiveNmsAdapter calls, so the platform runs in
CONNECTOR_MODE=live against this service with no code change - and in production the same adapter
points at the carrier's NMS/OSS by swapping NMS_ADAPTER_URL. It never fabricates an incident: it
reports exactly what is in oss.outages, and 'operational' when there is nothing active.

Endpoint (adapter contract):
  GET /network-status?area=<area>  -> {"area","status","outages":[...]}
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI

from nms_sim import incidents
from persistence.engine import session_scope
from service_auth import require_internal_key

logger = logging.getLogger(__name__)
app = FastAPI(title="nms-sim", dependencies=[Depends(require_internal_key)])


@app.get("/health")
async def health() -> dict:
    """Liveness probe. Backed by oss.outages; no in-memory fallback."""
    return {"status": "ok", "service": "nms-sim", "backing": "postgres-oss-outages"}


@app.get("/network-status")
async def network_status(area: str = "") -> dict:
    """Known active incidents for an area. Empty list means genuinely operational."""
    with session_scope() as session:
        return incidents.get_network_status(session, area)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8108")))


if __name__ == "__main__":
    run()
