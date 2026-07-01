"""decision-service entrypoint (CDC section 4.5): candidate-action ranking + confidence."""
from __future__ import annotations

from fastapi import FastAPI

from decision_service.schemas import DecisionRequest, DecisionResponse
from decision_service.scorer import recommend

app = FastAPI(title="decision-service")


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/recommend", response_model=DecisionResponse)
async def recommend_action(req: DecisionRequest) -> DecisionResponse:
    """Return the best candidate action + confidence for the requested action."""
    decision = recommend(req.action_type, req.context)
    return DecisionResponse(action=decision.action, confidence=decision.confidence, rationale=decision.rationale)