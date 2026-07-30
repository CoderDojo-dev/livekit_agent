"""notification-service entrypoint (CDC section 4.10): outbound written confirmations."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from notification_service.channels import channel_status, verify_credentials
from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.service import NotificationService
from service_auth import require_internal_key

app = FastAPI(title="notification-service", dependencies=[Depends(require_internal_key)])
_service = NotificationService()


@app.get("/health")
async def health() -> dict:
    """Liveness probe with per-channel configuration status."""
    info: dict[str, object] = {"status": "ok"}
    info.update(channel_status())
    return info


@app.post("/notify", response_model=NotifyResponse)
async def notify(req: NotifyRequest) -> NotifyResponse:
    """Send one localized written confirmation."""
    return await _service.notify(req)


@app.get("/health/credentials", tags=["health"])
async def health_credentials() -> dict:
    """Live credential probe. Slow on purpose: never call it from a readiness probe."""
    return await verify_credentials()


@app.get("/sent")
async def sent() -> dict:
    """List confirmations sent so far (demo/inspection)."""
    return {"sent": _service.sent}


def run() -> None:
    """Console-script entrypoint: `notification-service` (see [project.scripts]). Serves on :8106."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8106)
