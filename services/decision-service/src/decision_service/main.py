"""decision-service entrypoint (CDC section 4.5): candidate-action ranking + confidence."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from decision_service.schemas import DecisionRequest, DecisionResponse
from decision_service.scorer import recommend
from service_auth import require_internal_key

app = FastAPI(title="decision-service", dependencies=[Depends(require_internal_key)])


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/recommend", response_model=DecisionResponse)
async def recommend_action(req: DecisionRequest) -> DecisionResponse:
    """Return the best candidate action + confidence for the requested action."""
    decision = recommend(req.action_type, req.context)
    return DecisionResponse(action=decision.action, confidence=decision.confidence, rationale=decision.rationale)


def run() -> None:
    """Console-script entrypoint: `decision-service` (see [project.scripts]). Serves on :8103."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8103)
