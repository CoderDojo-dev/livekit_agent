"""notification-service entrypoint (CDC section 4.10): outbound written confirmations."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi import Depends
from service_auth import require_internal_key

from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.service import NotificationService

app = FastAPI(title="notification-service", dependencies=[Depends(require_internal_key)])
_service = NotificationService()


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/notify", response_model=NotifyResponse)
async def notify(req: NotifyRequest) -> NotifyResponse:
    """Send one localized written confirmation."""
    return await _service.notify(req)


@app.get("/sent")
async def sent() -> dict:
    """List confirmations sent so far (demo/inspection)."""
    return {"sent": _service.sent}