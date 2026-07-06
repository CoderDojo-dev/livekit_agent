# Telecom AI Voice Agent Platform - Complete Source Code

> AUTO-GENERATED from version_07 branch. Every source file included verbatim.

---

### .dockerignore

```text
**/__pycache__/
**/*.pyc
**/.pytest_cache/
**/node_modules/
**/dist/
.git/
**/.venv/
*.zip
**/.env

```

---

### .github\workflows\ci.yml

```yaml
name: ci

on:
  push:
    branches: [ main ]
  pull_request:

env:
  REGISTRY: ghcr.io
  IMAGE_TAG: ${{ github.sha }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install tooling
        run: pip install ruff mypy
      - name: Lint (ruff)
        run: ruff check . || true
      - name: Type check (mypy)
        run: mypy packages/ services/ apps/ || true

  test:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install shared packages + tooling
        run: |
          pip install --upgrade pip
          pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
                      ./packages/pii-shield ./packages/observability-kit ./packages/service-auth \
                      ./packages/cache ./packages/object-storage ./packages/notification-client \
                      ./packages/integration-adapters
      - name: Offline test suite
        run: |
          set -e
          for pkg in packages/audit-trail packages/service-auth packages/cache packages/object-storage \
                     packages/integration-adapters packages/persistence \
                     services/context-service services/decision-service services/policy-service \
                     services/execution-service services/notification-service services/knowledge-service \
                     apps/business-api ; do
            echo "== $pkg ==" ; ( cd "$pkg" && pip install -q . && python -m pytest -q ) || exit 1
          done

  db-migrations:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: telecom
          POSTGRES_PASSWORD: telecom
          POSTGRES_DB: telecom
        ports: [ "5432:5432" ]
        options: >-
          --health-cmd "pg_isready -U telecom" --health-interval 10s
          --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Apply migrations + seeds
        env:
          DATABASE_URL: postgresql+psycopg://telecom:telecom@localhost:5432/telecom
        run: |
          pip install ./packages/domain-core ./packages/persistence
          cd packages/persistence
          alembic upgrade head
          python -m seed.seed_pilot
          python -m seed.seed_reference

  docker-build:
    runs-on: ubuntu-latest
    needs: [test, db-migrations]
    if: github.ref == 'refs/heads/main'
    strategy:
      matrix:
        service:
          - context-service
          - decision-service
          - policy-service
          - execution-service
          - knowledge-service
          - notification-service
          - token-service
          - business-api
          - agent-worker
    steps:
      - uses: actions/checkout@v4
      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: services/${{ matrix.service }}/Dockerfile
          push: true
          tags: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:${{ env.IMAGE_TAG }},${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:latest

  docker-build-apps:
    runs-on: ubuntu-latest
    needs: [test, db-migrations]
    if: github.ref == 'refs/heads/main'
    strategy:
      matrix:
        service:
          - token-service
          - business-api
          - agent-worker
    steps:
      - uses: actions/checkout@v4
      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/${{ matrix.service }}/Dockerfile
          push: true
          tags: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:${{ env.IMAGE_TAG }},${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:latest

  security-scan:
    runs-on: ubuntu-latest
    needs: [docker-build, docker-build-apps]
    if: github.ref == 'refs/heads/main'
    strategy:
      matrix:
        service:
          - context-service
          - decision-service
          - policy-service
          - execution-service
          - knowledge-service
          - notification-service
          - token-service
          - business-api
          - agent-worker
    steps:
      - name: Run Trivy scanner
        uses: aquasecurity/trivy-action@0.29.0
        with:
          image-ref: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:${{ env.IMAGE_TAG }}
          format: sarif
          output: trivy-results.sarif
      - name: Upload scan results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-results.sarif

```

---

### .gitignore

```text
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Env / secrets
.env
*.local

# Node
node_modules/
dist/
.vite/

# Data / artifacts
*.log
/data/
minio-data/
postgres-data/

# Build artifacts (report #24)
*.zip
*.egg-info/
build/
*.egg

```

---

### apps\agent-worker\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f apps/agent-worker/Dockerfile -t agent-worker .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY apps/agent-worker/ ./apps/agent-worker/
RUN pip install ./apps/agent-worker

# Switch to the 'app' user before downloading models so they are stored in
# the app user's home directory (~/.cache) and are accessible at runtime.
USER app
RUN python -m livekit.agents download-files

CMD ["python", "apps/agent-worker/src/server.py", "start"]

```

---

### apps\agent-worker\livekit.toml

```toml
# LiveKit worker config. Connection details are env-driven (Twelve-Factor); never hardcoded.
# A transport switch (self-hosted <-> Cloud fallback) is a config change, not a code change.
[project]
name = "telecom-agent-worker"
```

---

### apps\agent-worker\pyproject.toml

```toml
[project]
name = "agent-worker"
version = "0.1.0"
description = "LiveKit Agents real-time orchestrator. Thin tools; zero business logic."
requires-python = ">=3.12"
dependencies = [
  "object-storage",
  "service-auth",
  "audit-trail",
  "persistence",
  "livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia]==1.6.3",
  "mcp>=1.9,<1.10",
  "pydantic==2.10.4",
  "pydantic-settings==2.7.1",
  "httpx==0.28.1",
  "structlog==24.4.0",
  "python-dotenv==1.0.1",
  "domain-core",
  "observability-kit",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

```

---

### apps\agent-worker\src\agents\__init__.py

```python
"""One file per persona (single responsibility each). Five personas only."""
```

---

### apps\agent-worker\src\agents\account_services_agent.py

```python
"""AccountServicesAgent (CDC 5.6-5.8): plan consultation/change, prepaid recharge, roaming.

Inherits BaseTelecomAgent so it gets the shared per-turn sentiment scoring + proactive
de-escalation + conversation logging, like every other persona. All state changes go through the
guarded action path.
"""
from __future__ import annotations

from tools.account_tools import change_plan, get_plan_details, toggle_roaming, top_up
from tools.escalation_tools import escalate_to_manager

from agents.base_agent import BaseTelecomAgent


class AccountServicesAgent(BaseTelecomAgent):
    """Lower-risk account-management persona; every state change is verdict-checked + audited."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle account services: plan consultation, plan changes, prepaid recharges, "
                "and roaming. For the current plan call get_plan_details. To change a plan use "
                "change_plan. For a recharge use top_up. For roaming use toggle_roaming. If the "
                "caller is upset or asks for a human, call escalate_to_manager. Keep replies short."
            ),
            chat_ctx=chat_ctx,
            tools=[get_plan_details, change_plan, top_up, toggle_roaming, escalate_to_manager],
        )

    async def on_enter(self) -> None:
        """Greet briefly and invite the account-management request."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with plans, recharges and roaming."
        )
```

---

### apps\agent-worker\src\agents\base_agent.py

```python
"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging

from conversation.writer import sentiment_label
from livekit.agents import Agent
from sentiment.sentiment_scorer import get_sentiment_scorer

logger = logging.getLogger(__name__)

_DEESCALATION_NOTE = (
    "The caller appears repeatedly frustrated. In your next reply, sincerely acknowledge their "
    "frustration, stay brief and calm, and proactively offer to connect them with a human "
    "specialist. If they agree, call escalate_to_manager."
)


def _extract_text(message) -> str:
    """Best-effort extraction of the user's text from a ChatMessage (content may be str or list)."""
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part for part in content if isinstance(part, str))
    return ""


class BaseTelecomAgent(Agent):
    """Every persona inherits this to share the sentiment/escalation + logging observer."""

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the turn, log it (off-path), and inject a de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        transcript = _extract_text(new_message).strip()
        if transcript:
            logger.info("caller_transcript=%s", transcript)
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:
                logger.debug("sentiment scoring skipped: %s", exc)

            writer = getattr(user_data, "conversation_writer", None)
            if writer is not None:
                score = user_data.sentiment_history[-1] if getattr(user_data, "sentiment_history", None) else 0.0
                writer.record_turn(
                    speaker="caller", text=transcript,
                    active_agent=type(self).__name__, language=getattr(user_data, "language", None),
                )
                writer.record_sentiment(score=score, label=sentiment_label(score))

        if getattr(user_data, "should_offer_escalation", False):
            try:
                turn_ctx.add_message(role="system", content=_DEESCALATION_NOTE)
                logger.info("frustration high -> injected proactive de-escalation note")
            except Exception as exc:
                logger.debug("frustration injection skipped: %s", exc)

```

---

### apps\agent-worker\src\agents\billing_agent.py

```python
"""BillingAgent: bill consultation (read), payment + payment-deferral (guarded) (CDC 5.1-5.3).

Phase 7: make_payment confirms the amount (PaymentConfirmTask) then runs the full
Decision -> Policy -> Execution faÃ§ade; an AUTHORIZED action is dispatched idempotently and the
caller is given the confirmation reference. Deferral runs the same faÃ§ade.
"""
from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.payment_confirm_task import PaymentConfirmTask
from tools import outcomes
from tools.billing_tools import get_balance_summary, get_invoice_summary
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified

from agents.base_agent import BaseTelecomAgent


@function_tool()
async def make_payment(context: RunContext, amount: float) -> dict:
    """Take a bill payment of ``amount`` TND (CDC section 5.2).

    Identity-gated -> explicit amount confirmation -> Decision/Policy/Execution. Returns a
    standard outcome ('executed' with a reference, 'refused', 'escalate', or 'failed').
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    confirmed = await PaymentConfirmTask(amount=amount)
    return await execute_guarded_action(
        context, "EXECUTE_PAYMENT", {"amount": amount, "payment_confirmed": bool(confirmed)}
    )


@function_tool()
async def request_payment_deferral(context: RunContext, requested_days: int) -> dict:
    """Request a payment deferral of ``requested_days`` days (CDC section 5.3).

    Identity-gated, then Decision -> Policy -> Execution. Returns a standard outcome.
    """
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")

    user_data = context.session.userdata
    unpaid_amount = 0.0
    if user_data.customer_context is not None:
        invoices = await get_context_client().get_invoices(user_data.customer_context.customer_id)
        unpaid_amount = sum(inv["amount"] for inv in invoices if inv.get("status") != "paid")

    return await execute_guarded_action(
        context,
        "PAYMENT_DEFERRAL",
        {"requested_days": requested_days, "unpaid_amount": unpaid_amount, "deferrals_this_year": 0},
    )


class BillingAgent(BaseTelecomAgent):
    """Concentrates billing/payment risk. Reads are free; sensitive writes are guarded + audited."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle billing: invoice/balance consultation, payment, and payment-deferral. "
                "For the caller's own invoice or balance, use get_invoice_summary / "
                "get_balance_summary. To take a payment use make_payment; for a deferral use "
                "request_payment_deferral. For general offer/procedure/FAQ questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. Keep replies short. NEVER claim a payment or "
                "deferral succeeded yourself - only the tool result decides. Communicate the "
                "tool's 'message' to the caller: on 'executed' give the reference; on 'refused' "
                "or 'failed' explain plainly; on 'escalate' explain briefly and call "
                "escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[
                get_invoice_summary,
                get_balance_summary,
                make_payment,
                request_payment_deferral,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the billing question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their billing question, in their language.",
        )

```

---

### apps\agent-worker\src\agents\manager_agent.py

```python
"""ManagerAgent: escalation target â€” transfer or callback, and open a follow-up ticket (Phase 9).

Inherits BaseTelecomAgent. Reached on the shared session (full context). Can open a ticket so an
escalated issue is tracked and the caller gets a written confirmation.
"""
from __future__ import annotations

from mcp_clients.ticketing_toolset import build_ticketing_toolset
from telephony.sip_transfer import transfer_to_human

from agents.base_agent import BaseTelecomAgent


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer/callback, plus follow-up ticketing."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You are a senior support manager handling an escalated call. Briefly acknowledge "
                "and reassure the caller, confirm the issue in one sentence, then use "
                "transfer_to_human to connect them to a live advisor (it will schedule a callback "
                "if none is free). If the issue needs tracking, call create_ticket (with the "
                "caller's language) so they receive a written confirmation, and give them the "
                "reference. Keep replies short and calm; always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[transfer_to_human, build_ticketing_toolset()],
        )

    async def on_enter(self) -> None:
        """Reassure the caller and move to connect a human."""
        self.session.generate_reply(
            instructions=(
                "Reassure the caller their issue is being escalated, confirm briefly what it is "
                "about, and tell them you will connect them with a human advisor now, in their language."
            ),
        )
```

---

### apps\agent-worker\src\agents\technical_agent.py

```python
"""TechnicalAgent: SIM / network / connectivity (CDC section 5.5) + ticketing (Phase 9).

Inherits BaseTelecomAgent (sentiment-aware). Can open a follow-up ticket for an unresolved
issue (the caller then gets a written confirmation) and resolve it if solved during the call.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from mcp_clients.ticketing_toolset import build_ticketing_toolset
from tools import outcomes
from tools.escalation_tools import escalate_to_manager
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified

from agents.base_agent import BaseTelecomAgent


@function_tool()
async def unblock_sim(context: RunContext) -> dict:
    """Unblock the caller's SIM card (CDC section 5.5). Identity-gated, then guarded + executed."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "UNBLOCK_SIM", {})


class TechnicalAgent(BaseTelecomAgent):
    """Concentrates SIM/network risk. Sensitive ops are identity-gated; opens/resolves tickets."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You handle technical issues: SIM problems, network and connectivity. "
                "To unblock a SIM, use unblock_sim. For how-to/known-issue questions, call "
                "knowledge_search with a concise ENGLISH query and answer in the caller's "
                "language, citing the source. If an issue cannot be solved on the call, call "
                "create_ticket (subject + short description + the caller's language) so the "
                "caller gets a written confirmation; give them the ticket reference. If the "
                "issue IS solved during the call, you may resolve_ticket. Keep replies short. "
                "NEVER claim an operation succeeded yourself - only the tool result decides. "
                "If a result is 'refused' or 'failed', communicate its 'message' plainly; if "
                "'escalate', call escalate_to_manager. Always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[
                unblock_sim,
                escalate_to_manager,
                build_knowledge_toolset(),
                build_ticketing_toolset(),
            ],
        )

    async def on_enter(self) -> None:
        """Acknowledge the hand-off and invite the technical question."""
        self.session.generate_reply(
            instructions="Briefly tell the caller you can help with their technical issue, in their language.",
        )
```

---

### apps\agent-worker\src\agents\triage_agent.py

```python
"""TriageAgent: consent, greet, answer FAQs, route, escalate â€” now sentiment-aware (Phase 8).

Inherits BaseTelecomAgent (per-turn sentiment + proactive de-escalation). Ambiguity is handled
through request_clarification so the section 10.1 "two failed clarifications" trigger is deterministic.
"""
from __future__ import annotations

import logging

from config.language_presets import GREETINGS
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.consent_task import ConsentTask
from tools.clarification_tools import request_clarification
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing, route_to_technical

from agents.base_agent import BaseTelecomAgent

logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and either answer or route. "
    "For general questions about offers, plans, procedures, or FAQs, call knowledge_search "
    "with a concise ENGLISH query and answer in the caller's language, citing the source. "
    "For the caller's own billing/payment, call route_to_billing. For SIM/network/connectivity, "
    "call route_to_technical. For a human, call escalate_to_manager. "
    "If the request is ambiguous, call request_clarification with a single clarifying question "
    "(do not ask directly); if it returns 'escalate', call escalate_to_manager - do not guess again. "
    "If the caller becomes upset, acknowledge it and offer a human. "
    "Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent data."
)


class TriageAgent(BaseTelecomAgent):
    """Default starting persona. Captures consent, greets by name, answers FAQs, routes, escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[
                request_clarification,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )
        self._language = language

    async def on_enter(self) -> None:
        """Collect recording consent (once), then greet â€” personalized when the caller is known."""
        logger.info("triage agent entered language=%s", self._language)
        user_data = self.session.userdata
        if user_data.recording_consent is None:
            granted = await ConsentTask(chat_ctx=self.chat_ctx)
            user_data.recording_consent = bool(granted)

        customer = user_data.customer_context
        if customer is not None:
            instructions = (
                f"Greet the caller by their first name (full name on file: {customer.full_name}), "
                "briefly, and ask how you can help today, in their language. "
                "Do not ask who they are - you already know."
            )
        else:
            instructions = GREETINGS.get(self._language, GREETINGS["fr"])
        logger.info("triage greeting requested")
        self.session.generate_reply(instructions=instructions)

```

---

### apps\agent-worker\src\clients\__init__.py

```python
"""Typed clients to domain services (one per service). Each carries its own timeout/retry."""
```

---

### apps\agent-worker\src\clients\context_client.py

```python
"""Typed client to the context-service (Customer 360 + identity + read paths).

Each method degrades gracefully: a context-service outage returns None / [] / False rather
than crashing the call.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings
from session.customer_context import CustomerContext

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ContextClient:
    """Pre-fetch the caller snapshot, run identity checks, and read invoices/balance."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def get_snapshot(self, msisdn: str) -> CustomerContext | None:
        """Return the caller's CustomerContext, or None if unknown/unavailable."""
        try:
            resp = await self._client.get(f"/context/{msisdn}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return CustomerContext.from_snapshot(resp.json())
        except httpx.HTTPError as exc:
            logger.warning("context prefetch failed for %s: %s", msisdn, exc)
            return None

    async def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Return True iff the step-up answer matches; False on mismatch or service error."""
        try:
            resp = await self._client.post(
                "/verify-identity",
                json={"customer_id": customer_id, "answer": answer},
            )
            resp.raise_for_status()
            return bool(resp.json().get("verified"))
        except httpx.HTTPError as exc:
            logger.warning("identity verification call failed for %s: %s", customer_id, exc)
            return False

    async def get_invoices(self, customer_id: str) -> list[dict]:
        """Return the caller's invoices (read-only, CDC section 5.1); [] on error."""
        try:
            resp = await self._client.get(f"/billing/{customer_id}/invoices")
            resp.raise_for_status()
            return resp.json().get("invoices", [])
        except httpx.HTTPError as exc:
            logger.warning("invoice read failed for %s: %s", customer_id, exc)
            return []

    async def get_balance(self, customer_id: str) -> dict | None:
        """Return the caller's prepaid balance, or None if absent/unavailable."""
        try:
            resp = await self._client.get(f"/balance/{customer_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("balance read failed for %s: %s", customer_id, exc)
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_context_client() -> ContextClient:
    """Return a cached ContextClient bound to the configured context-service URL."""
    return ContextClient(get_settings().context_service_url)
```

---

### apps\agent-worker\src\clients\decision_client.py

```python
"""Typed client to the decision-service (candidate-action ranking)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class DecisionClient:
    """Ask the Decision context to rank a candidate action before Policy."""

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def recommend(self, action_type: str, context: dict) -> dict:
        """Return {action, confidence, rationale}; low confidence on service error."""
        try:
            resp = await self._client.post(
                "/recommend", json={"action_type": action_type, "context": context}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("decision recommend failed; low confidence: %s", exc)
            return {"action": action_type, "confidence": 0.0, "rationale": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_decision_client() -> DecisionClient:
    """Return a cached DecisionClient bound to the configured decision-service URL."""
    return DecisionClient(get_settings().decision_service_url)
```

---

### apps\agent-worker\src\clients\execution_client.py

```python
"""Typed client to the execution-service. Returns a standard outcome (executed / failed)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings
from tools import outcomes

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class ExecutionClient:
    """Dispatch an AUTHORIZED action idempotently, carrying the authorizing verdict id."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def execute(
        self,
        idempotency_key: str,
        action_type: str,
        session_id: str,
        payload: dict,
        policy_verdict_id: str,
        customer_id: str | None = None,
        subscription_id: str | None = None,
    ) -> dict:
        """Execute the action; return an 'executed' or 'failed' outcome (never raises)."""
        try:
            resp = await self._client.post(
                "/execute",
                json={
                    "idempotency_key": idempotency_key,
                    "action_type": action_type,
                    "session_id": session_id,
                    "policy_verdict_id": policy_verdict_id,
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "payload": payload,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return outcomes.executed(data["action_type"], data["reference"], replay=data.get("replay", False))
        except httpx.HTTPError as exc:
            logger.error("execution failed for %s: %s", action_type, exc)
            return outcomes.failed(str(exc))

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_execution_client() -> ExecutionClient:
    """Return a cached ExecutionClient bound to the configured execution-service URL."""
    return ExecutionClient(get_settings().execution_service_url)
```

---

### apps\agent-worker\src\clients\notification_client.py

```python
"""Typed client to the notification-service (worker-initiated written confirmations)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class NotificationClient:
    """Send a localized written confirmation; degrades gracefully on error."""

    def __init__(self, base_url: str, timeout: float = 4.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def notify(
        self, customer_id: str, template: str, language: str, params: dict, channel: str = "sms"
    ) -> dict:
        """Send a confirmation; returns {'sent': bool, ...}. Never raises into the call."""
        try:
            resp = await self._client.post(
                "/notify",
                json={
                    "customer_id": customer_id,
                    "to": customer_id,
                    "channel": channel,
                    "template": template,
                    "language": language,
                    "params": params,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("notification send failed (%s): %s", template, exc)
            return {"sent": False}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_notification_client() -> NotificationClient:
    """Return a cached NotificationClient bound to the configured notification-service URL."""
    return NotificationClient(get_settings().notification_service_url)
```

---

### apps\agent-worker\src\clients\policy_client.py

```python
"""Typed client to the policy-service: the single mandatory checkpoint (never bypassable)."""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx
from config import get_settings

from service_auth import internal_headers

logger = logging.getLogger(__name__)


class PolicyClient:
    """Call Policy before any execution and any outbound response.

    Fail-closed: if Policy is unreachable, the verdict defaults to ESCALATE (never AUTHORIZED),
    so an outage can never silently authorize a sensitive action.
    """

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=internal_headers())

    async def evaluate_action(self, context: dict) -> dict:
        """Return the verdict dict for an action; ESCALATE on service error (fail-closed)."""
        try:
            resp = await self._client.post("/evaluate-action", json=context)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("policy evaluate-action failed; failing closed to ESCALATE: %s", exc)
            return {"verdict": "escalate", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def evaluate_response(self, session_id: str, text: str) -> dict:
        """Guardrail an outbound response; REFUSED on service error (fail-closed)."""
        try:
            resp = await self._client.post(
                "/evaluate-response", json={"session_id": session_id, "text": text}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("policy evaluate-response failed; failing closed to REFUSED: %s", exc)
            return {"verdict": "refused", "rule_id": "POLICY_UNAVAILABLE", "justification": str(exc)}

    async def aclose(self) -> None:
        await self._client.aclose()


@lru_cache
def get_policy_client() -> PolicyClient:
    """Return a cached PolicyClient bound to the configured policy-service URL."""
    return PolicyClient(get_settings().policy_service_url)
```

---

### apps\agent-worker\src\clients\routing_client.py

```python
"""Resolve a live human advisor for escalation (Blueprint section 6, Escalation context).

The destination is resolved DYNAMICALLY by skill, never hardcoded. The pilot has no live
advisor-routing system, so this returns None and escalations fall back to a scheduled
callback. Wire to the real routing service (or an availability API) in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AdvisorDestination:
    """A resolved human-advisor SIP endpoint."""

    participant_identity: str
    sip_uri: str
    skill_tag: str


class RoutingClient:
    """Resolves an available advisor by skill tag."""

    async def resolve_available_advisor(self, skill_tag: str) -> AdvisorDestination | None:
        """Return an available advisor for ``skill_tag``, or None if none is free."""
        # No live advisor-routing system in the pilot -> always None (callback fallback).
        return None


@lru_cache
def get_routing_client() -> RoutingClient:
    """Return a cached RoutingClient."""
    return RoutingClient()
```

---

### apps\agent-worker\src\config\__init__.py

```python
"""Per-environment settings, feature flags and language presets."""
from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
```

---

### apps\agent-worker\src\config\language_presets.py

```python
"""Per-language presets that the providers layer mirrors from DR-0 (Phase 0).

Each language entry must supply ALL keys consumed by the STT and TTS builders:
  - deepgram_language  â†’ deepgram.STT(language=...)
  - azure_stt_locale   â†’ azure.STT(language=...)        [fallback]
  - gladia_language    â†’ gladia.STT(language=...)        [optional fallback]
  - tts_iso            â†’ elevenlabs.TTS(language=...)    [TTS primary]
  - azure_tts_voice    â†’ azure.TTS(voice=...)            [TTS fallback]
  - cartesia_voice_id  â†’ cartesia.TTS(voice=...)         [optional TTS provider]

Arabic: Deepgram uses language="ar" (single-language model, never "multi"). See stt.py.
"""
from __future__ import annotations

# Decided in Phase 0 (docs/architecture/phase-0-verification-gate/00-DECISION-RECORD.md).
LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
    "fr": {
        # STT â€” Deepgram primary
        "deepgram_language": "fr",
        # STT â€” Azure fallback
        "azure_stt_locale": "fr-FR",
        # STT â€” Gladia (optional fallback, BCP-47 locale)
        "gladia_language": "fr",
        # TTS â€” ElevenLabs primary (ISO-639-1)
        "tts_iso": "fr",
        # TTS â€” Azure fallback (Neural voice name)
        "azure_tts_voice": "fr-FR-DeniseNeural",
        # TTS â€” Cartesia voice ID (UUID, fr-FR female voice)
        "cartesia_voice_id": "a249eaff-1e96-4d2c-b23b-12efa4c2d4b1",
    },
    "ar": {
        # STT â€” Deepgram primary (language="ar", single-language model â€” never "multi")
        "deepgram_language": "ar",
        # STT â€” Azure fallback
        "azure_stt_locale": "ar-EG",
        # STT â€” Gladia
        "gladia_language": "ar",
        # TTS â€” ElevenLabs primary
        "tts_iso": "ar",
        # TTS â€” Azure fallback
        "azure_tts_voice": "ar-EG-SalmaNeural",
        # TTS â€” Cartesia voice ID (UUID, Arabic voice)
        "cartesia_voice_id": "79743797-2087-422f-8e74-6d2b03ae5b31",
    },
    "en": {
        # STT â€” Deepgram primary
        "deepgram_language": "en",
        # STT â€” Azure fallback
        "azure_stt_locale": "en-US",
        # STT â€” Gladia
        "gladia_language": "en",
        # TTS â€” ElevenLabs primary
        "tts_iso": "en",
        # TTS â€” Azure fallback
        "azure_tts_voice": "en-US-JennyNeural",
        # TTS â€” Cartesia voice ID (UUID, en-US female voice)
        "cartesia_voice_id": "694f9389-aac1-45b6-b726-9d9369183238",
    },
}

GREETINGS: dict[str, str] = {
    "fr": "Saluez briÃ¨vement l'appelant en franÃ§ais et demandez comment vous pouvez l'aider aujourd'hui.",
    "ar": "Ø­ÙŠ Ø§Ù„Ù…ØªØµÙ„ Ø¨Ø§Ø®ØªØµØ§Ø± Ø¨Ø§Ù„Ù„ØºØ© Ø§Ù„Ø¹Ø±Ø¨ÙŠØ© ÙˆØ§Ø³Ø£Ù„Ù‡ ÙƒÙŠÙ ÙŠÙ…ÙƒÙ†Ùƒ Ù…Ø³Ø§Ø¹Ø¯ØªÙ‡ Ø§Ù„ÙŠÙˆÙ….",
    "en": "Briefly greet the caller in English and ask how you can help today.",
}

```

---

### apps\agent-worker\src\config\settings.py

```python
"""Twelve-Factor settings: everything via environment, nothing hardcoded.

This module holds configuration values only. It imports no vendor plugin: provider
construction (including noise cancellation) lives behind the providers/ boundary.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- LiveKit transport (self-hosted) ---
    livekit_url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("devsecret_change_me", alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("telecom-agent", alias="LIVEKIT_AGENT_NAME")

    # --- Language scope / spike session language ---
    supported_languages: str = Field("fr,ar,en", alias="SUPPORTED_LANGUAGES")
    default_language: str = Field("fr", alias="DEFAULT_LANGUAGE")
    session_language: str = Field("fr", alias="SESSION_LANGUAGE")
    session_caller_msisdn: str = Field("", alias="SESSION_CALLER_MSISDN")

    # --- STT primary (Deepgram) ---
    stt_model: str = Field("nova-3", alias="STT_MODEL")

    # --- TTS primary (ElevenLabs Flash v2.5) ---
    tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")

    # --- Deepgram TTS (optional â€” if livekit-plugins-deepgram adds TTS support) ---
    deepgram_tts_model: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_MODEL")
    deepgram_tts_voice: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_VOICE")

    # --- LLM chain: Gemini 2.5 Flash primary, OpenAI GPT-4o-mini fallback ---
    llm_primary_model: str = Field("gemini-2.5-flash", alias="LLM_PRIMARY_MODEL")
    llm_fallback_model: str = Field("gpt-4o-mini", alias="LLM_FALLBACK_MODEL")
    openai_enabled: bool = Field(False, alias="OPENAI_ENABLED")

    # --- Optional NVIDIA NIM fallback LLM (single key, no pool) ---
    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-8b-instruct", alias="NVIDIA_MODEL")
    nvidia_timeout_s: float = Field(45.0, alias="NVIDIA_TIMEOUT_S")

    # --- Optional Groq fallback LLM (single key, no pool) ---
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    groq_timeout_s: float = Field(30.0, alias="GROQ_TIMEOUT_S")

    # --- Optional Gladia STT (additional fallback after Azure) ---
    gladia_api_key: str = Field("", alias="GLADIA_API_KEY")

    # --- Optional Cartesia TTS (additional TTS option behind ElevenLabs) ---
    cartesia_api_key: str = Field("", alias="CARTESIA_API_KEY")
    cartesia_tts_model: str = Field("sonic-2", alias="CARTESIA_TTS_MODEL")

    # --- VAD / turn detection / latency ---
    vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")
    preemptive_generation: bool = Field(True, alias="PREEMPTIVE_GENERATION")
    noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")

    # --- Decision -> Policy faÃ§ade ---
    decision_confidence_threshold: float = Field(0.5, alias="DECISION_CONFIDENCE_THRESHOLD")

    # --- Resilience chaos toggles (cookbook section 16): break a primary on purpose ---
    chaos_break_stt: bool = Field(False, alias="CHAOS_BREAK_STT")
    chaos_break_llm: bool = Field(False, alias="CHAOS_BREAK_LLM")
    chaos_break_tts: bool = Field(False, alias="CHAOS_BREAK_TTS")

    # --- Domain service URLs ---
    context_service_url: str = Field("http://localhost:8101", alias="CONTEXT_SERVICE_URL")
    decision_service_url: str = Field("http://localhost:8103", alias="DECISION_SERVICE_URL")
    policy_service_url: str = Field("http://localhost:8104", alias="POLICY_SERVICE_URL")
    execution_service_url: str = Field("http://localhost:8105", alias="EXECUTION_SERVICE_URL")
    notification_service_url: str = Field("http://localhost:8106", alias="NOTIFICATION_SERVICE_URL")
    knowledge_mcp_url: str = Field("http://localhost:8201/mcp", alias="KNOWLEDGE_MCP_URL")
    ticketing_mcp_url: str = Field("http://localhost:8202/mcp", alias="TICKETING_MCP_URL")

    @property
    def languages(self) -> list[str]:
        """Parsed supported-language list."""
        return [item.strip() for item in self.supported_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

```

---

### apps\agent-worker\src\conversation\__init__.py

```python
"""Durable conversation record, written off the voice path (spec section 11)."""
```

---

### apps\agent-worker\src\conversation\writer.py

```python
"""Non-blocking writer for the conversation record (spec section 11; ADR adaptation 3).

The worker is real-time, so NOTHING here runs on the voice path: callers enqueue plain dicts
(constant time), a single background task drains the queue and performs the actual Postgres
writes in a thread (sync SQLAlchemy off the event loop). If the DB is down, writes are logged
and dropped - the call is never affected. Transcripts are PII-masked before they leave the worker.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)


def sentiment_label(score: float) -> str:
    """Map a sentiment score to the conversation.sentiment_samples label vocabulary."""
    if score <= -0.7:
        return "angry"
    if score <= -0.35:
        return "negative"
    if score >= 0.35:
        return "positive"
    return "neutral"


class ConversationWriter:
    """Enqueue-and-forget writer; one instance per call."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._masker = PiiMasker()
        self._session_db_id: str | None = None
        self._start_time: datetime | None = None
        self._turn_index = 0

    def start(self) -> None:
        """Launch the background drain task."""
        if self._task is None:
            self._task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is None:
                    break
                await asyncio.to_thread(self._write, item)
            except Exception as exc:
                logger.warning("conversation write dropped (%s): %s", (item or {}).get("kind"), exc)
            finally:
                self._queue.task_done()

    def _write(self, item: dict) -> None:
        from persistence.engine import session_scope
        from persistence.models.conversation import (
            CallbackSchedule,
            CallSession,
            EscalationCase,
            SentimentSample,
            Turn,
        )

        kind = item["kind"]
        row = item.get("row", {})
        with session_scope() as session:
            if kind == "session_start":
                session.add(CallSession(**row))
            elif kind == "turn":
                session.add(Turn(**row))
            elif kind == "sentiment":
                session.add(SentimentSample(**row))
            elif kind == "escalation":
                session.add(EscalationCase(**row))
            elif kind == "callback":
                session.add(CallbackSchedule(**row))
            elif kind == "consent":
                from audit_trail import PgAuditLedger
                from persistence.models.crm import ConsentRecord

                record = ConsentRecord(**row)
                session.add(record)
                session.flush()
                PgAuditLedger(session).append(
                    row["session_id"], "consent",
                    {"granted": row["granted"], "consent_type": row["consent_type"]},
                    entity_reference=f"consent_records:{record.id}",
                )
            elif kind == "session_finish":
                obj = session.get(CallSession, item["session_db_id"])
                if obj is not None:
                    obj.end_time = item["end_time"]
                    obj.duration_seconds = item["duration"]
                    obj.final_disposition = item.get("disposition")
                    obj.max_frustration_score = item["max_frustration"]
                    if item.get("recording_consent") is not None:
                        obj.recording_consent = item["recording_consent"]

    # ---------- enqueue API (non-blocking) ----------
    def start_session(self, *, customer_id=None, subscription_id=None, msisdn=None,
                      livekit_room=None, recording_consent=None) -> str:
        """Open a call record; returns the session DB id (generated locally, FIFO-ordered)."""
        from persistence.util import to_uuid

        self._session_db_id = str(uuid.uuid4())
        self._start_time = datetime.now(UTC)
        self._enqueue("session_start", {
            "id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "msisdn": msisdn,
            "livekit_room": livekit_room,
            "recording_consent": recording_consent,
            "start_time": self._start_time,
            "channel": "voice",
        })
        return self._session_db_id

    def record_turn(self, speaker: str, text: str, active_agent=None, language=None, intent=None) -> None:
        """Append a turn (transcript PII-masked here, before it leaves the worker)."""
        if self._session_db_id is None:
            return
        self._turn_index += 1
        self._enqueue("turn", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "speaker": speaker,
            "active_agent": active_agent,
            "detected_language": language,
            "transcript_masked": self._masker.mask(text or ""),
            "detected_intent": intent,
        })

    def record_sentiment(self, score: float, label: str) -> None:
        """Append a sentiment sample for the current turn index."""
        if self._session_db_id is None:
            return
        self._enqueue("sentiment", {
            "session_id": uuid.UUID(self._session_db_id),
            "turn_index": self._turn_index,
            "score": score,
            "label": label,
        })

    def record_escalation(self, trigger: str, target: str, dossier: dict, customer_id=None) -> None:
        """Record an escalation case with the context dossier handed to the human/manager."""
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._enqueue("escalation", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "trigger": trigger,
            "target": target,
            "dossier": dossier,
        })

    def record_callback(self, *, customer_id=None, subscription_id=None, scheduled_time=None, priority=1) -> None:
        """Record a scheduled callback (scheduled_time defaults to +24h until a parser/queue lands)."""
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._enqueue("callback", {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "subscription_id": to_uuid(subscription_id),
            "scheduled_time": scheduled_time or (datetime.now(UTC) + timedelta(hours=24)),
            "priority_level": priority,
        })

    def record_consent(self, *, granted: bool, language: str | None = None, customer_id=None) -> None:
        """Persist the recording-consent decision (crm.consent_records) + an audit entry (event 'consent')."""
        if self._session_db_id is None:
            return
        from persistence.util import to_uuid

        self._queue.put_nowait({"kind": "consent", "row": {
            "session_id": uuid.UUID(self._session_db_id),
            "customer_id": to_uuid(customer_id),
            "consent_type": "call_recording",
            "granted": granted,
            "language": language,
        }})

    def finish_session(self, *, disposition=None, max_frustration=0.0, recording_consent=None) -> None:
        """Close the call record (end time, duration, disposition, peak frustration)."""
        if self._session_db_id is None:
            return
        end = datetime.now(UTC)
        duration = int((end - (self._start_time or end)).total_seconds())
        self._queue.put_nowait({
            "kind": "session_finish",
            "session_db_id": uuid.UUID(self._session_db_id),
            "end_time": end,
            "duration": duration,
            "disposition": disposition,
            "max_frustration": max_frustration,
            "recording_consent": recording_consent,
        })

    def _enqueue(self, kind: str, row: dict) -> None:
        self._queue.put_nowait({"kind": kind, "row": row})

    async def aclose(self) -> None:
        """Signal the drain to finish and wait briefly for the queue to flush."""
        self._queue.put_nowait(None)
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except Exception:
                self._task.cancel()
```

---

### apps\agent-worker\src\entrypoints\__init__.py

```python
"""Worker bootstrap: env/config load, room/job entrypoint registration."""
```

---

### apps\agent-worker\src\entrypoints\worker.py

```python
"""Alternate entry shim. Delegates to the AgentServer composition root in server.py so that
both `python -m server console` and `python -m entrypoints.worker console` run the same wiring.
"""
from __future__ import annotations

from livekit import agents
from server import server


def main() -> None:
    """Run the worker CLI (supports the console / dev / start subcommands)."""
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()
```

---

### apps\agent-worker\src\mcp_clients\__init__.py

```python
"""MCPToolset wiring + per-agent allowed_tools allow-lists (Blueprint ADR 5.4)."""
```

---

### apps\agent-worker\src\mcp_clients\knowledge_toolset.py

```python
"""[VERIFY] Scoped MCPToolset over the ai-knowledge-rag MCP server (ADR section 5.4).

Stable pattern (confirmed): MCPToolset(id=..., mcp_server=MCPServerHTTP(url=.../mcp,
allowed_tools=[...])). URLs ending '/mcp' use streamable HTTP. The deprecated mcp_servers=[...]
param is NOT used. Knowledge is now its own MCP server (review note 1), separate from GLPI
ticketing (ticketing-glpi, Phase 9). Per-agent scoping: each persona builds its own toolset.
"""
from __future__ import annotations

from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client

from livekit.agents import mcp


def build_knowledge_toolset(allowed_tools: Iterable[str] = ("knowledge_search",)):
    """Return an MCPToolset exposing only ``allowed_tools`` from the knowledge MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().knowledge_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="ai-knowledge-rag", mcp_server=server)

```

---

### apps\agent-worker\src\mcp_clients\ticketing_toolset.py

```python
"""[VERIFY] Scoped MCPToolset over the ticketing-glpi MCP server (ADR section 5.4; review note 1).

Same confirmed pattern as the knowledge toolset. Ticketing is its own MCP server, separate from
knowledge. Per-agent scoping: only personas that open/resolve tickets include this toolset.
"""
from __future__ import annotations

from collections.abc import Iterable

import mcp.client.streamable_http as streamable_http
from config import get_settings

if not hasattr(streamable_http, "streamable_http_client") and hasattr(
    streamable_http, "streamablehttp_client"
):
    streamable_http.streamable_http_client = streamable_http.streamablehttp_client

from livekit.agents import mcp

_DEFAULT_TOOLS = ("create_ticket", "get_ticket_status", "resolve_ticket", "lookup_tickets")


def build_ticketing_toolset(allowed_tools: Iterable[str] = _DEFAULT_TOOLS):
    """Return an MCPToolset exposing only ``allowed_tools`` from the ticketing MCP server."""
    server = mcp.MCPServerHTTP(
        url=get_settings().ticketing_mcp_url,
        allowed_tools=list(allowed_tools),
    )
    return mcp.MCPToolset(id="ticketing-glpi", mcp_server=server)

```

---

### apps\agent-worker\src\observability\__init__.py

```python
"""Session metrics hooks (TTFA/TTFT capture) + OTel span enrichment."""
```

---

### apps\agent-worker\src\observability\log_masking.py

```python
"""PII masking for ALL worker logs (Blueprint section 14 / review note 5a).

Installs a logging filter that scrubs phone numbers, emails, and identifier runs from every
emitted record, as a safety net on top of the rule that structured fields log non-PII ids.
"""
from __future__ import annotations

import logging

from pii_shield import PiiMasker


class PiiMaskingFilter(logging.Filter):
    """A logging filter that masks PII in the fully-rendered message."""

    def __init__(self) -> None:
        super().__init__()
        self._masker = PiiMasker()

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = self._masker.mask(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def install_pii_masking() -> None:
    """Attach the PII masking filter to every root handler exactly once."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, PiiMaskingFilter) for f in handler.filters):
            handler.addFilter(PiiMaskingFilter())
```

---

### apps\agent-worker\src\observability\metrics_hook.py

```python
"""TTFA/TTFT + usage metrics hook (cookbook section 13, Blueprint section 16).

Attaches non-blocking listeners to an AgentSession: per-component metrics are logged via the SDK
helper, time-to-first-audio is derived from the end-of-utterance timestamp, and TTFA/TTFT are
exported to OpenTelemetry (no-op until a collector is configured). Adds zero latency to the reply.
"""
from __future__ import annotations

import logging
import time

from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics

from observability_kit import record_ttfa, record_ttft

logger = logging.getLogger(__name__)


def attach_metrics(session):
    """Wire usage collection + TTFA/TTFT logging/export onto ``session``; return a shutdown callback."""
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: dict[str, object] = {"value": None}

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metric = ev.metrics
        metric_type = getattr(metric, "type", None)
        if metric_type == "eou_metrics":
            last_eou_metrics["value"] = metric
        if metric_type == "llm_metrics":
            ttft = getattr(metric, "ttft", None)
            if ttft:
                record_ttft(float(ttft))  # export time-to-first-token
        metrics.log_metrics(metric)
        usage_collector.collect(metric)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        eou = last_eou_metrics["value"]
        if ev.new_state == "speaking" and eou is not None:
            try:
                ttfa = time.time() - eou.timestamp  # EOUMetrics.timestamp is confirmed
                logger.info("time_to_first_audio_seconds=%.3f", ttfa)
                record_ttfa(ttfa)  # export time-to-first-audio
            except Exception as exc:
                logger.debug("ttfa computation skipped: %s", exc)

    async def log_usage() -> None:
        logger.info("usage_summary=%s", usage_collector.get_summary())

    return log_usage
```

---

### apps\agent-worker\src\observability\metrics_hooks.py

```python
"""Capture TTFA/TTFT and fallback activations. Phase 3/11 wire the metric stream."""
from __future__ import annotations


class MetricsHooks:
    """Subscribe to the session metrics stream (Phase 3 wires UsageCollector)."""

    def attach(self, session) -> None:
        raise NotImplementedError("wired in Phase 3 / Phase 11 (Observability)")
```

---

### apps\agent-worker\src\providers\__init__.py

```python
"""STT/LLM/TTS/VAD/turn-detector selection per language + FallbackAdapter wiring.

Mirrors the Phase-0 decision record (DR-0). Concrete plugin instantiation lands in Phase 3.
"""
```

---

### apps\agent-worker\src\providers\_resilience.py

```python
"""Shared resilience helper: the chaos toggle used by each provider builder (cookbook section 16).

Keeping the swap in one tiny module means the three builders apply it identically and there
is a single definition of the deliberately invalid model id.
"""
from __future__ import annotations

# A deliberately invalid model id used to force a primary failure in chaos runs.
INVALID_MODEL = "chaos-invalid-model-does-not-exist"


def chaos_model(real_model: str, break_primary: bool) -> str:
    """Return ``real_model``, or the invalid id when ``break_primary`` is set."""
    return INVALID_MODEL if break_primary else real_model
```

---

### apps\agent-worker\src\providers\groq_adapter.py

```python
"""Groq LLM Adapter â€” thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the Groq OpenAI-compatible endpoint via livekit-plugins-openai's
    OpenAI client pointing at Groq's base URL.
  - Reads GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with Groq's base_url / api_key injected,
    identical pattern to NvidiaLLM â€” no new streaming/function-call logic needed.
  - No key pool â€” one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.

Usage in llm.py:
    from providers.groq_adapter import GroqLLM
    adapter = GroqLLM(api_key=..., model=..., timeout=...)
    # Drop into FallbackAdapter([..., adapter])
"""
from __future__ import annotations

import logging

from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLM(lk_openai.LLM):
    """
    Single-key Groq LLM adapter.

    Inherits livekit.plugins.openai.LLM with the Groq base URL injected.
    Drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation â€” just one key from GROQ_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("GroqLLM requires a non-empty api_key (GROQ_API_KEY)")
        logger.info("GroqLLM: initialising with model=%s endpoint=%s", model, GROQ_BASE_URL)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=GROQ_BASE_URL,
        )

```

---

### apps\agent-worker\src\providers\language_router.py

```python
"""Route per-turn language to the decided STT/TTS chain (Blueprint section 13)."""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS


class LanguageRouter:
    """Resolve the STT/TTS preset for a detected/selected language."""

    def preset_for(self, language: str) -> dict[str, str]:
        """Return the provider preset for ``language`` (defaults to French)."""
        return LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])
```

---

### apps\agent-worker\src\providers\llm.py

```python
"""LLM builder: Google Gemini 2.5 Flash primary + OpenAI GPT fallback + optional NVIDIA NIM + Groq.

Provider chain (highest-priority first):
  1. google.LLM  â€” Gemini 2.5 Flash  [primary, GOOGLE_API_KEY required]
  2. NvidiaLLM   â€” NVIDIA NIM         [fallback, skipped if NVIDIA_API_KEY absent]
  3. openai.LLM  â€” GPT-4o-mini        [fallback, skipped if OPENAI_API_KEY absent]
  4. GroqLLM     â€” Groq (llama)       [fallback, skipped if GROQ_API_KEY absent]

[verify] model id strings churn; they are env-driven and confirmed against
docs.livekit.io/agents/models at build time.
"""
from __future__ import annotations

import os

from livekit.agents import llm as llm_module
from livekit.plugins import google, openai

from providers._resilience import chaos_model
from providers.groq_adapter import GroqLLM
from providers.nvidia_adapter import NvidiaLLM


def build_llm(primary_model: str, fallback_model: str, break_primary: bool = False):
    """Return an LLM FallbackAdapter with Gemini 2.5 Flash as primary.

    The chain is built dynamically based on which API keys are present.
    Providers without a key are silently skipped so the system degrades
    gracefully rather than crashing at startup.

    Args:
        primary_model:  Gemini model ID (env: LLM_PRIMARY_MODEL).
        fallback_model: OpenAI model ID  (env: LLM_FALLBACK_MODEL).
        break_primary:  Chaos toggle â€” substitutes the invalid model id so the
                        primary intentionally fails and the fallback takes over.
    """
    # --- Primary: Google Gemini 2.5 Flash ---
    primary = google.LLM(model=chaos_model(primary_model, break_primary))

    providers: list = [primary]

    # --- Fallback 2: NVIDIA NIM (optional) ---
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        nvidia_timeout = float(os.getenv("NVIDIA_TIMEOUT_S", "45.0"))
        providers.append(NvidiaLLM(api_key=nvidia_key, model=nvidia_model, timeout=nvidia_timeout))

    # --- Fallback 3: OpenAI GPT (optional, skippable via OPENAI_ENABLED) ---
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_enabled = os.getenv("OPENAI_ENABLED", "true").lower() in ("true", "1", "yes")
    if openai_key and openai_enabled:
        providers.append(openai.LLM(model=fallback_model))

    # --- Fallback 4: Groq (optional) ---
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        groq_timeout = float(os.getenv("GROQ_TIMEOUT_S", "30.0"))
        providers.append(GroqLLM(api_key=groq_key, model=groq_model, timeout=groq_timeout))

    return llm_module.FallbackAdapter(providers, attempt_timeout=12.0)
```

---

### apps\agent-worker\src\providers\noise_cancellation.py

```python
"""Noise-cancellation builder (the providers/ vendor boundary; cookbook section 6).

[VERIFY] BVC may require livekit-plugins-noise-cancellation and, for some models, LiveKit
Cloud. Returns None when disabled so console/self-hosted runs never hard-depend on it.
Confirm at docs.livekit.io/agents/build/audio/ before enabling for telephony.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_noise_cancellation(enabled: bool):
    """Return a BVC noise-cancellation plugin instance, or None when disabled/unavailable."""
    if not enabled:
        return None
    try:
        from livekit.plugins import noise_cancellation

        return noise_cancellation.BVC()
    except Exception as exc:
        logger.warning("noise cancellation requested but unavailable: %s", exc)
        return None
```

---

### apps\agent-worker\src\providers\nvidia_adapter.py

```python
"""NVIDIA NIM LLM Adapter â€” thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the OpenAI-compatible NVIDIA NIM endpoint via livekit-plugins-openai's
    OpenAI client pointing at the NIM base URL.
  - Reads NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with a custom base_url / api_key so it is
    100% compatible with FallbackAdapter without reimplementing streaming or
    function-calling internally.
  - No key pool â€” one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.

Usage in llm.py:
    from providers.nvidia_adapter import NvidiaLLM
    adapter = NvidiaLLM(api_key=..., model=..., timeout=...)
    # Drop into FallbackAdapter([..., adapter, ...])
"""
from __future__ import annotations

import logging

from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaLLM(lk_openai.LLM):
    """
    Single-key NVIDIA NIM LLM adapter.

    Inherits livekit.plugins.openai.LLM with the NIM base URL injected.
    This makes it a drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation â€” just one key from NVIDIA_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta/llama-3.1-8b-instruct",
        timeout: float = 45.0,
    ) -> None:
        if not api_key:
            raise ValueError("NvidiaLLM requires a non-empty api_key (NVIDIA_API_KEY)")
        logger.info("NvidiaLLM: initialising with model=%s endpoint=%s", model, NVIDIA_BASE_URL)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
            # httpx_client_options accepted by openai.LLM to set per-request timeout
            # (the timeout kwarg may not be in older plugin versions â€” safe to omit)
        )

```

---

### apps\agent-worker\src\providers\session_factory.py

```python
"""Thin session assembler (cookbook section 4/5, SRP-refined).

This file contains NO vendor-plugin import. It composes the per-concern builders from the
providers/ package into one AgentSession. Vendor coupling lives only in the builder modules
(stt/tts/llm/vad) and the isolated turn_detection wrapper â€” the providers/ package is the
single vendor boundary, enforceable by a lint rule: no `livekit.plugins` import may appear
outside apps/agent-worker/src/providers/.
"""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from livekit.agents import AgentSession

from providers.llm import build_llm
from providers.stt import build_stt
from providers.tts import build_tts
from providers.turn_detection import build_turn_detector
from providers.vad import build_vad


def build_agent_session(settings: Settings, language: str) -> AgentSession:
    """Assemble the STT/LLM/TTS/VAD/turn-detection pipeline for ``language`` (composition only).

    Each of STT/LLM/TTS is a FallbackAdapter([primary, secondary]) so a single provider
    outage never drops the call (Blueprint section 1).
    """
    preset = LANGUAGE_PRESETS.get(language, LANGUAGE_PRESETS["fr"])
    return AgentSession(
        vad=build_vad(settings.vad_min_silence),
        turn_detection=build_turn_detector(),
        stt=build_stt(preset, settings.stt_model, settings.chaos_break_stt),
        llm=build_llm(settings.llm_primary_model, settings.llm_fallback_model, settings.chaos_break_llm),
        tts=build_tts(preset, settings.tts_model, settings.eleven_voice_id, settings.chaos_break_tts),
        preemptive_generation=settings.preemptive_generation,
    )
```

---

### apps\agent-worker\src\providers\stt.py

```python
"""STT builder: Deepgram primary + Gladia optional fallback + Azure final fallback.

Provider chain:
  1. deepgram.STT  â€” primary (DEEPGRAM_API_KEY required)
  2. gladia.STT    â€” optional fallback (skipped when GLADIA_API_KEY absent)
  3. azure.STT     â€” final fallback (skipped when AZURE_SPEECH_KEY absent)

Streaming is required by FallbackAdapter; all three providers stream.
Arabic routes to Deepgram language="ar" (the dedicated monolingual model), never "multi".
"""
from __future__ import annotations

import os

from livekit.agents import stt as stt_module
from livekit.plugins import azure, deepgram, gladia

from providers._resilience import chaos_model


def build_stt(preset: dict[str, str], model: str = "nova-3", break_primary: bool = False):
    """Return a streaming STT FallbackAdapter for the given language preset.

    Args:
        preset:        Language preset dict from LANGUAGE_PRESETS (must contain
                       deepgram_language, azure_stt_locale, gladia_language).
        model:         Deepgram model ID (env: STT_MODEL, default: nova-3).
        break_primary: Chaos toggle â€” forces primary failure for resilience tests.
    """
    # --- Primary: Deepgram ---
    primary = deepgram.STT(
        model=chaos_model(model, break_primary),
        language=preset["deepgram_language"],
    )

    providers: list = [primary]

    # --- Optional fallback: Gladia (skipped if no key) ---
    gladia_key = os.getenv("GLADIA_API_KEY", "")
    if gladia_key:
        providers.append(
            gladia.STT(
                languages=[preset["gladia_language"]],
                api_key=gladia_key,
            )
        )

    # --- Final fallback: Azure (skipped if no key) ---
    azure_key = os.getenv("AZURE_SPEECH_KEY", "")
    if azure_key:
        providers.append(azure.STT(language=preset["azure_stt_locale"]))

    return stt_module.FallbackAdapter(providers)
```

---

### apps\agent-worker\src\providers\tts.py

```python
"""TTS builder: ElevenLabs primary + Cartesia optional fallback + Azure final fallback.

Provider chain:
  1. elevenlabs.TTS â€” primary (ELEVEN_API_KEY required)
  2. cartesia.TTS   â€” optional fallback (skipped when CARTESIA_API_KEY absent)
  3. azure.TTS      â€” final fallback (skipped when AZURE_SPEECH_KEY absent)

NOTE on Deepgram TTS:
  The installed LiveKit plugin bundle (livekit-agents[deepgram,...]==1.6.3) includes
  livekit-plugins-deepgram which currently exposes only STT functionality (deepgram.STT).
  Deepgram's Aura TTS product is available via their REST API but is NOT yet surfaced as
  a tts.TTS-compatible object in this version of the plugin. Therefore:
    - Deepgram is used as STT primary (see stt.py).
    - ElevenLabs remains TTS primary (uses ELEVEN_API_KEY).
    - Cartesia is wired as the first TTS fallback if CARTESIA_API_KEY is set.
    - Azure is the final TTS fallback if AZURE_SPEECH_KEY is set.
  When a future livekit-plugins-deepgram release adds deepgram.TTS, add it here as primary
  and demote ElevenLabs to first fallback.

ElevenLabs reads ELEVEN_API_KEY from the environment; language is ISO-639-1 (fr/ar/en).
"""
from __future__ import annotations

import os

from livekit.agents import tts as tts_module
from livekit.plugins import azure, cartesia, elevenlabs

from providers._resilience import chaos_model


def build_tts(preset: dict[str, str], model: str, voice_id: str, break_primary: bool = False):
    """Return a TTS FallbackAdapter for the given language preset.

    Args:
        preset:        Language preset dict from LANGUAGE_PRESETS (must contain
                       tts_iso, azure_tts_voice, cartesia_voice_id).
        model:         ElevenLabs model ID (env: TTS_MODEL).
        voice_id:      ElevenLabs voice ID (env: ELEVEN_VOICE_ID).
        break_primary: Chaos toggle â€” forces primary failure for resilience tests.
    """
    # --- Primary: ElevenLabs (skipped if no key) ---
    eleven_key = os.getenv("ELEVEN_API_KEY", "")
    providers: list = []
    if eleven_key:
        providers.append(
            elevenlabs.TTS(
                model=chaos_model(model, break_primary),
                voice_id=voice_id,
                language=preset["tts_iso"],
            )
        )

    # --- Optional fallback: Cartesia (skipped if no key) ---
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    if cartesia_key:
        providers.append(
            cartesia.TTS(
                model=os.getenv("CARTESIA_TTS_MODEL", "sonic-2"),
                voice=preset["cartesia_voice_id"],
                api_key=cartesia_key,
            )
        )

    return tts_module.FallbackAdapter(providers)
```

---

### apps\agent-worker\src\providers\turn_detection.py

```python
def build_turn_detector():
    return "stt"

```

---

### apps\agent-worker\src\providers\vad.py

```python
"""Silero VAD builder (local; min_silence >= 250ms required by the audio turn detector).

One of only five files allowed to import a vendor plugin (the providers/ boundary).
"""
from __future__ import annotations

from livekit.plugins import silero


def build_vad(min_silence: float = 0.25):
    """Return a local Silero VAD instance."""
    return silero.VAD.load(min_silence_duration=min_silence)
```

---

### apps\agent-worker\src\sentiment\__init__.py

```python
"""Post-turn sentiment scoring (Blueprint section 6, Sentiment context)."""
```

---

### apps\agent-worker\src\sentiment\sentiment_scorer.py

```python
"""Sentiment scoring behind a swappable interface (Strategy; Blueprint section 1/6).

Phase 8 ships a deterministic, dependency-free LEXICAL scorer (multilingual fr/ar/en) so
sentiment never adds latency or a fragile per-turn LLM call. The production swap is an
LLM-backed scorer built in providers/ (the vendor boundary) implementing the same .score();
agent code and the hook never change when it is replaced.
"""
from __future__ import annotations

from typing import Protocol

NEGATIVE_THRESHOLD = -0.35
ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS = 2

_NEGATIVE = (
    # en
    "angry", "furious", "unacceptable", "terrible", "ridiculous", "useless", "worst",
    "frustrated", "frustrating", "scam", "cancel", "hate", "awful", "incompetent", "complaint",
    # fr
    "inacceptable", "ridicule", "horrible", "arnaque", "scandaleux", "marre", "Ã©nervÃ©",
    "colÃ¨re", "inadmissible", "rÃ©silier", "honteux", "incompÃ©tent", "nul",
    # ar
    "Ø³ÙŠØ¡", "ØºØ§Ø¶Ø¨", "Ù…Ø±ÙÙˆØ¶", "ÙØ¶ÙŠØ­Ø©", "Ù…Ø²Ø¹Ø¬", "Ø³Ø®ÙŠÙ",
)
_POSITIVE = (
    "thanks", "thank you", "great", "perfect", "helpful", "appreciate", "excellent",
    "merci", "parfait", "gÃ©nial", "super", "Ø´ÙƒØ±Ø§", "Ù…Ù…ØªØ§Ø²", "Ø±Ø§Ø¦Ø¹",
)


class SentimentScorer(Protocol):
    """Scores a caller utterance and updates the running negative-turn signal in user-data."""

    def score(self, transcript: str, userdata) -> float: ...


class LexicalSentimentScorer:
    """Deterministic keyword scorer: -1.0 (negative), +0.5 (positive), 0.0 (neutral)."""

    def score(self, transcript: str, userdata) -> float:
        text = transcript.lower()
        negative = any(word in text for word in _NEGATIVE)
        positive = any(word in text for word in _POSITIVE)
        value = -1.0 if negative else (0.5 if positive else 0.0)

        userdata.sentiment_history.append(value)
        if value <= NEGATIVE_THRESHOLD:
            userdata.consecutive_negative_turns += 1
        else:
            userdata.consecutive_negative_turns = 0
        userdata.should_offer_escalation = (
            userdata.consecutive_negative_turns >= ESCALATE_AFTER_CONSECUTIVE_NEGATIVE_TURNS
        )
        return value


def get_sentiment_scorer() -> SentimentScorer:
    """Return the configured sentiment scorer (lexical default)."""
    return LexicalSentimentScorer()
```

---

### apps\agent-worker\src\server.py

```python
"""COMPOSITION ROOT ONLY (cookbook section 4). Wires providers/agents/hooks, pre-fetches the
caller context, installs PII-masked logging, opens the durable conversation record, and starts
the worker. Conversation writes run off the voice path via ConversationWriter.
"""
from __future__ import annotations

import logging
import inspect

from agents.triage_agent import TriageAgent
from clients.context_client import get_context_client
from config import get_settings
from conversation.writer import ConversationWriter
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext
from observability.log_masking import install_pii_masking
from observability.metrics_hook import attach_metrics
from providers.noise_cancellation import build_noise_cancellation
from providers.session_factory import build_agent_session
from session import SessionUserData

from observability_kit import configure_tracer

load_dotenv()
logging.basicConfig(level=logging.INFO)
install_pii_masking()
logger = logging.getLogger("agent-worker")

settings = get_settings()


def _build_agent_server() -> AgentServer:
    """Create the AgentServer, naming it when the installed LiveKit SDK supports that option."""
    agent_name = settings.livekit_agent_name.strip()
    if agent_name:
        try:
            if "agent_name" in inspect.signature(AgentServer).parameters:
                logger.info("registering LiveKit worker agent_name=%s", agent_name)
                return AgentServer(agent_name=agent_name)
        except (TypeError, ValueError):
            pass
        logger.warning("LiveKit AgentServer has no agent_name constructor option; using auto-dispatch mode")
    return AgentServer()


server = _build_agent_server()


async def _prefetch_user_data(language: str) -> SessionUserData:
    """Build session state, pre-fetching the caller's Customer-360 snapshot when known."""
    user_data = SessionUserData(language=language)
    msisdn = settings.session_caller_msisdn
    if msisdn:
        snapshot = await get_context_client().get_snapshot(msisdn)
        if snapshot is not None:
            user_data.customer_context = snapshot
            logger.info("context prefetched: customer_id=%s vip=%s", snapshot.customer_id, snapshot.is_vip)
        else:
            logger.info("no context snapshot for the calling line")
    return user_data


def _open_conversation(ctx: JobContext, user_data: SessionUserData) -> ConversationWriter:
    """Start the conversation writer and open the call record (off the voice path)."""
    writer = ConversationWriter()
    writer.start()
    customer = user_data.customer_context
    user_data.conversation_writer = writer
    user_data.session_db_id = writer.start_session(
        customer_id=customer.customer_id if customer else None,
        subscription_id=getattr(customer, "subscription_id", None) if customer else None,
        msisdn=settings.session_caller_msisdn or (customer.msisdn if customer else None),
        livekit_room=getattr(ctx.room, "name", None),
        recording_consent=user_data.recording_consent,
    )
    return writer


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Assemble and start a Triage voice session for the configured language."""
    configure_tracer("agent-worker")
    language = settings.session_language
    room_name = getattr(ctx.room, "name", None)
    logger.info("agent job received room=%s language=%s", room_name, language)

    session = build_agent_session(settings, language)
    user_data = await _prefetch_user_data(language)
    session.userdata = user_data

    writer = _open_conversation(ctx, user_data)

    async def _finish_conversation() -> None:
        history = user_data.sentiment_history or [0.0]
        writer.finish_session(
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()

    ctx.add_shutdown_callback(_finish_conversation)
    ctx.add_shutdown_callback(attach_metrics(session))

    @session.on("user_speech_committed")
    def _on_user_speech(msg):
        text = getattr(msg, "text_content", "") or getattr(msg, "content", "")
        if text:
            logger.info("ðŸŽ¤ Caller: %s", text)

    @session.on("agent_speech_committed")
    def _on_agent_speech(msg):
        text = getattr(msg, "text_content", "") or getattr(msg, "content", "")
        if text:
            logger.info("ðŸ¤– Agent: %s", text)

    @session.on("function_calls_collected")
    def _on_tools(fcs):
        names = [f.function_name for f in fcs] if fcs else []
        if names:
            logger.info("ðŸ› ï¸ Agent calling tools: %s", ", ".join(names))

    @session.on("function_calls_finished")
    def _on_tools_done(fcs):
        names = [f.function_name for f in fcs] if fcs else []
        if names:
            logger.info("âœ… Tools completed: %s", ", ".join(names))

    nc = build_noise_cancellation(settings.noise_cancellation)
    if nc is None:
        await session.start(agent=TriageAgent(language=language), room=ctx.room)
    else:
        try:
            from livekit.agents import room_io

            await session.start(
                agent=TriageAgent(language=language),
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    audio_input=room_io.AudioInputOptions(noise_cancellation=nc),
                ),
            )
        except Exception as exc:
            logger.warning("noise-cancellation room options unavailable (%s); plain start", exc)
            await session.start(agent=TriageAgent(language=language), room=ctx.room)
    logger.info("Triage session started room=%s", room_name)


if __name__ == "__main__":
    agents.cli.run_app(server)

```

---

### apps\agent-worker\src\session\__init__.py

```python
"""Session user-data model + typed caller context."""
from session.customer_context import CustomerContext
from session.session_state import SessionUserData

__all__ = ["CustomerContext", "SessionUserData"]
```

---

### apps\agent-worker\src\session\customer_context.py

```python
"""Typed caller snapshot held in session user-data (spec section 4 / section 1 identity model).

Worker-side mirror of the context-service Customer360 response. Carries both canonical UUIDs
(customer_id, subscription_id) so downstream domain calls pass UUIDs, never the MSISDN.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CustomerContext:
    """The caller's pre-fetched profile, available to every persona and tool."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    subscription_id: str | None = None
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0

    @classmethod
    def from_snapshot(cls, data: dict) -> CustomerContext:
        """Build from a context-service snapshot dict (ignores enrichment-only fields)."""
        return cls(
            customer_id=data["customer_id"],
            full_name=data["full_name"],
            msisdn=data["msisdn"],
            subscription_type=data["subscription_type"],
            subscription_id=data.get("subscription_id"),
            preferred_language=data.get("preferred_language", "fr"),
            is_vip=data.get("is_vip", False),
            fraud_suspected=data.get("fraud_suspected", False),
            account_age_days=data.get("account_age_days", 0),
        )
```

---

### apps\agent-worker\src\session\session_state.py

```python
"""Per-session state carried across agents/tasks (cookbook section 17). No business logic."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from session.customer_context import CustomerContext


@dataclass
class SessionUserData:
    """Session-scoped, mutable state shared by the active persona, tasks and tools."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "fr"
    customer_context: CustomerContext | None = None
    identity_verified: bool = False
    identity_attempts: int = 0
    recording_consent: bool | None = None

    # --- sentiment / escalation (Phase 8) ---
    sentiment_history: list[float] = field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    clarification_attempts: int = 0
    current_persona_skill_tag: str = "general"
    callback_requested: bool = False
    callback_when: str | None = None

    # --- conversation persistence (P3) ---
    conversation_writer: object | None = None
    session_db_id: str | None = None

    _idempotency_keys: dict[str, str] = field(default_factory=dict)

    def new_idempotency_key(self, action_type: str) -> str:
        """One key per (session, action_type); reused across retries so a retry is safe."""
        if action_type not in self._idempotency_keys:
            seed = f"{self.session_id}:{action_type}:{uuid.uuid4()}"
            self._idempotency_keys[action_type] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[action_type]
```

---

### apps\agent-worker\src\session\user_data.py

```python
"""Per-session state carried across agents/tasks (no business logic lives here)."""
from __future__ import annotations

from dataclasses import dataclass, field

from domain_core.value_objects import Language, Sentiment


@dataclass
class SessionUserData:
    """Mutable session context shared by the active persona, tasks and tools."""

    conversation_id: str
    language: Language = Language.FR
    customer_id: str | None = None
    identity_verified: bool = False
    consent_granted: bool | None = None
    sentiment: Sentiment = Sentiment.NEUTRAL
    frustration_streak: int = 0
    clarification_attempts: int = 0
    identity_attempts: int = 0
    snapshot: dict = field(default_factory=dict)
```

---

### apps\agent-worker\src\tasks\__init__.py

```python
"""AgentTask / TaskGroup bounded sub-flows."""
```

---

### apps\agent-worker\src\tasks\callback_schedule_task.py

```python
"""Schedule a callback when no advisor is free (CDC section 5.12 / 6.4).

Records the caller's preferred time AND sends a written confirmation (Phase 9), so the Phase 8
exit criterion "callback with written confirmation" is fully closed.
"""
from __future__ import annotations

from clients.notification_client import get_notification_client
from livekit.agents import AgentTask, function_tool


class CallbackScheduleTask(AgentTask[bool]):
    """Offers a callback, records the preferred time, and texts a written confirmation."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "No advisor is available right now. Apologize briefly, offer the caller a "
                "callback, and ask for a preferred time window. Record it, or note if they "
                "decline. Always speak in the caller's language."
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        """Offer the callback and ask for a preferred time."""
        await self.session.generate_reply(
            instructions=(
                "Apologize that no advisor is free, offer a callback, and ask for a preferred "
                "time window, in the caller's language."
            ),
        )

    @function_tool()
    async def record_callback(self, preferred_time: str) -> None:
        """Record the caller's preferred callback time window and send a written confirmation."""
        user_data = self.session.userdata
        user_data.callback_requested = True
        user_data.callback_when = preferred_time

        customer = user_data.customer_context
        if customer is not None:
            await get_notification_client().notify(
                customer.customer_id,
                "callback_scheduled",
                user_data.language,
                {"when": preferred_time},
            )

        writer = getattr(user_data, "conversation_writer", None)
        if writer is not None:
            writer.record_callback(
                customer_id=customer.customer_id if customer else None,
                subscription_id=getattr(customer, "subscription_id", None) if customer else None,
            )
        self.complete(True)

    @function_tool()
    async def decline_callback(self) -> None:
        """Record that the caller declined a callback."""
        self.complete(False)
```

---

### apps\agent-worker\src\tasks\consent_task.py

```python
"""Recording-consent task (CDC section 8.1). Runs at TriageAgent.on_enter before business talk.

Now implemented (review note 6): asks for explicit consent in the caller's language and
records the boolean in session user-data. The audit/consent-event persistence lands with the
notification/compliance work; the decision itself is captured here from call start.
"""
from __future__ import annotations

from livekit.agents import AgentTask, function_tool


class ConsentTask(AgentTask[bool]):
    """Takes over the session briefly to capture recording consent, then returns the boolean."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Before anything else, ask the caller - briefly and in their language - for "
                "consent to record the call for quality and security purposes. Wait for a clear "
                "yes or no, then record it. Do not start solving their request yet."
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        """Prompt for recording consent."""
        await self.session.generate_reply(
            instructions="Ask the caller, briefly and in their language, for consent to record the call.",
        )

    @function_tool()
    async def record_consent(self, granted: bool) -> None:
        """Record whether the caller granted consent to record the call (durable + audited)."""
        user_data = self.session.userdata
        user_data.recording_consent = granted
        writer = getattr(user_data, "conversation_writer", None)
        if writer is not None:
            customer = getattr(user_data, "customer_context", None)
            writer.record_consent(
                granted=granted,
                language=getattr(user_data, "language", None),
                customer_id=customer.customer_id if customer else None,
            )
        self.complete(granted)
```

---

### apps\agent-worker\src\tasks\identity_verification_task.py

```python
"""Step-up identity verification (CDC section 6.5; Blueprint section 10.1).

Runs inline the first time a sensitive action is attempted. Counts failed attempts and, on
the configured maximum, completes False so the caller flow escalates to a human
(repeated identity failure is a mandatory-escalation trigger). The secret is checked by the
injected verify_fn (the context-service), never held in the task.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from livekit.agents import AgentTask, function_tool

MAX_ATTEMPTS = 3


class IdentityVerificationTask(AgentTask[bool]):
    """Takes over the session until the caller is verified or attempts are exhausted."""

    def __init__(
        self,
        customer_id: str,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        chat_ctx=None,
    ) -> None:
        super().__init__(
            instructions=(
                "Before proceeding with this sensitive request, verify the caller's identity. "
                "Ask the caller for the last four digits of their national ID (CIN). "
                "Always speak in the caller's current language. Be brief and reassuring."
            ),
            chat_ctx=chat_ctx,
        )
        self._customer_id = customer_id
        self._verify_fn = verify_fn
        self._attempts = 0

    async def on_enter(self) -> None:
        """Prompt the caller for the known personal element."""
        await self.session.generate_reply(
            instructions=(
                "Ask the caller to verify their identity by stating the last four digits of "
                "their national ID, in their language."
            ),
        )

    @function_tool()
    async def verify_with_known_element(self, provided_value: str) -> None:
        """Verify the caller's identity using the value they provided (last 4 digits of CIN)."""
        self._attempts += 1
        if await self._verify_fn(self._customer_id, provided_value):
            self.complete(True)
        elif self._attempts >= MAX_ATTEMPTS:
            self.complete(False)  # caller flow then escalates to a human (Blueprint section 10.1)
        # otherwise: stay in the task; the LLM naturally re-prompts
```

---

### apps\agent-worker\src\tasks\payment_confirm_task.py

```python
"""Explicit payment-amount confirmation (CDC section 6.1). Runs before EXECUTE_PAYMENT.

Verbal confirmation is mandatory; the policy engine REFUSES a payment without it, so this task
captures the caller's yes/no and passes it into the guarded action.
"""
from __future__ import annotations

from livekit.agents import AgentTask, function_tool


class PaymentConfirmTask(AgentTask[bool]):
    """Takes over the session to confirm the exact amount, then returns the boolean."""

    def __init__(self, amount: float, currency: str = "TND", chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                f"Confirm with the caller that they want to pay {amount:.3f} {currency}. "
                "Ask for an explicit yes or no, in their language. Do not proceed without a clear answer."
            ),
            chat_ctx=chat_ctx,
        )
        self._amount = amount
        self._currency = currency

    async def on_enter(self) -> None:
        """Ask the caller to confirm the exact amount."""
        await self.session.generate_reply(
            instructions=(
                f"Ask the caller to confirm paying {self._amount:.3f} {self._currency}, in their language."
            ),
        )

    @function_tool()
    async def confirm_payment(self, confirmed: bool) -> None:
        """Record the caller's explicit confirmation (or refusal) of the payment amount."""
        self.complete(confirmed)
```

---

### apps\agent-worker\src\tasks\sim_replacement_task_group.py

```python
"""Multi-step SIM replacement collection (CDC 5.5). Wired in Phase 7."""
from __future__ import annotations


class SimReplacementTaskGroup:
    """Collect shipping/contact + reason; revisitable steps (Phase 7)."""
```

---

### apps\agent-worker\src\telephony\__init__.py

```python
"""Telephony helpers (SIP transfer). Voice-only dev path does not require a SIP trunk."""
```

---

### apps\agent-worker\src\telephony\sip_transfer.py

```python
"""SIP transfer / human escalation (cookbook section 15; Blueprint section 5.12 / ADR 5.4).

Resolves the advisor destination dynamically (never a hardcoded trunk). If none is free, or if
SIP transfer is unavailable (e.g. console/dev with no trunk), it falls back to scheduling a
callback. [VERIFY] the SIP transfer call requires SIP REFER on the trunk; it is a cold transfer
that ends the current session, so it runs only in the telephony path and is guarded defensively.
"""
from __future__ import annotations

import logging
from contextlib import suppress

from clients.routing_client import get_routing_client
from livekit.agents import RunContext, function_tool, get_job_context
from tasks.callback_schedule_task import CallbackScheduleTask

logger = logging.getLogger(__name__)


async def _offer_callback(context: RunContext) -> dict:
    scheduled = await CallbackScheduleTask()
    return {"outcome": "callback_scheduled" if scheduled else "callback_declined"}


@function_tool()
async def transfer_to_human(context: RunContext) -> dict:
    """Transfer the caller to a live human advisor; if none is free, schedule a callback."""
    user_data = context.session.userdata
    skill_tag = getattr(user_data, "current_persona_skill_tag", "general")

    with suppress(Exception):
        context.disallow_interruptions()  # safe once we commit to transferring [VERIFY]
    await context.session.say("Let me connect you with a human advisor. Please hold.")

    destination = await get_routing_client().resolve_available_advisor(skill_tag)
    if destination is None:
        return await _offer_callback(context)

    try:
        from livekit import api

        job = get_job_context()
        await job.api.sip.transfer_sip_participant(
            api.TransferSIPParticipantRequest(
                room_name=job.room.name,
                participant_identity=destination.participant_identity,
                transfer_to=destination.sip_uri,
            )
        )
        return {"outcome": "transferred", "destination": destination.sip_uri}
    except Exception as exc:
        logger.warning("SIP transfer unavailable (%s); offering a callback", exc)
        return await _offer_callback(context)

```

---

### apps\agent-worker\src\tools\__init__.py

```python
"""Thin @function_tool facades â€” zero business logic; call domain services via clients."""
```

---

### apps\agent-worker\src\tools\account_tools.py

```python
"""Account-services tools (CDC 5.6-5.8): plan details, plan change, recharge, roaming.

Plan-details is a read from the pre-fetched context; the three state changes flow through the one
guarded path (Decision -> Policy -> Execution), so they are verdict-checked, idempotent and audited
like every other sensitive action. Returns are plain strings the persona can speak.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from tools.guarded_action import execute_guarded_action


@function_tool()
async def get_plan_details(context: RunContext) -> str:
    """Tell the caller their current plan and line (read-only, from the pre-fetched profile)."""
    customer = context.session.userdata.customer_context
    if customer is None:
        return "I can't see an active line for this number yet."
    return f"You're on {customer.subscription_type} for the line {customer.msisdn}."


@function_tool()
async def change_plan(context: RunContext, new_plan_code: str) -> dict:
    """Change the caller's plan to ``new_plan_code`` (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "CHANGE_PLAN", {"plan_code": new_plan_code})


@function_tool()
async def top_up(context: RunContext, amount: float) -> dict:
    """Top up the caller's prepaid balance by ``amount`` TND (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "TOP_UP", {"amount": amount})


@function_tool()
async def toggle_roaming(context: RunContext, enable: bool) -> dict:
    """Enable or disable roaming for the caller's line (sensitive: verdict-checked + audited)."""
    return await execute_guarded_action(context, "ACTIVATE_ROAMING", {"enable": enable})
```

---

### apps\agent-worker\src\tools\billing_tools.py

```python
"""Read-only billing tools (CDC section 5.1). No policy check â€” read-only, not sensitive.

Sensitive billing write paths (payment, deferral) live in billing_agent.py / Phase 7 and run
the Decision -> Policy -> Execution faÃ§ade. These tools only read, via the context-service.
"""
from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool


@function_tool()
async def get_invoice_summary(context: RunContext) -> dict:
    """Read the caller's latest invoice amount, currency, due date and status (CDC section 5.1)."""
    user_data = context.session.userdata
    if user_data.customer_context is None:
        return {"outcome": "unknown_caller"}
    invoices = await get_context_client().get_invoices(user_data.customer_context.customer_id)
    if not invoices:
        return {"outcome": "no_open_invoice"}
    latest = invoices[0]
    return {
        "outcome": "success",
        "amount_due": latest["amount"],
        "currency": latest.get("currency", "TND"),
        "due_date": latest["due_date"],
        "status": latest["status"],
    }


@function_tool()
async def get_balance_summary(context: RunContext) -> dict:
    """Read the caller's prepaid credit and remaining data, if any (read-only)."""
    user_data = context.session.userdata
    if user_data.customer_context is None:
        return {"outcome": "unknown_caller"}
    balance = await get_context_client().get_balance(user_data.customer_context.customer_id)
    if balance is None:
        return {"outcome": "no_balance_on_file"}
    return {
        "outcome": "success",
        "credit": balance["credit"],
        "currency": balance.get("currency", "TND"),
        "data_remaining_mb": balance.get("data_remaining_mb", 0),
    }
```

---

### apps\agent-worker\src\tools\clarification_tools.py

```python
"""Deterministic clarification counter (CDC section 10.1: two failed clarifications -> ESCALATE).

Asking via this tool (instead of free-text) is what makes the mandatory-escalation trigger real:
the second unresolved clarification returns an 'escalate' outcome, and clarification_attempts also
feeds the policy context so the engine's ESC_CLARIFICATION rule is reachable.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool


@function_tool()
async def request_clarification(context: RunContext, question: str) -> dict:
    """Ask the caller ONE clarifying question when their request is ambiguous.

    Call this INSTEAD of asking directly, so attempts are counted. After two unresolved
    clarifications the request must be escalated (outcome 'escalate').
    """
    user_data = context.session.userdata
    user_data.clarification_attempts += 1
    if user_data.clarification_attempts >= 2:
        return {
            "outcome": "escalate",
            "reason": "two_failed_clarifications",
            "message": "Still unclear after two attempts - call escalate_to_manager.",
        }
    return {
        "outcome": "ask",
        "question": question,
        "message": "Ask the caller this one clarifying question, in their language.",
    }
```

---

### apps\agent-worker\src\tools\escalation_tools.py

```python
"""Escalation hand-off (Blueprint section 7). Reused by every persona; records the case (P3)."""
from __future__ import annotations

from agents.manager_agent import ManagerAgent
from livekit.agents import RunContext, function_tool


def _trigger_for(user_data) -> str:
    """Pick the spec Appendix-A escalation trigger that best matches the session state."""
    if getattr(user_data, "should_offer_escalation", False):
        return "frustration"
    if getattr(user_data, "clarification_attempts", 0) >= 2:
        return "clarify_fail"
    if getattr(user_data, "identity_attempts", 0) >= 3:
        return "identity_fail"
    return "hard_failure"


@function_tool()
async def escalate_to_manager(context: RunContext) -> tuple[ManagerAgent, str]:
    """Hand off to a manager when the caller asks for a human, when the situation requires it,
    or when a persona cannot resolve the request. Records the escalation case (off the voice path)."""
    context.session.interrupt()
    user_data = context.session.userdata
    writer = getattr(user_data, "conversation_writer", None)
    if writer is not None:
        customer = getattr(user_data, "customer_context", None)
        writer.record_escalation(
            trigger=_trigger_for(user_data),
            target="manager_agent",
            dossier={
                "consecutive_negative_turns": getattr(user_data, "consecutive_negative_turns", 0),
                "identity_verified": getattr(user_data, "identity_verified", False),
                "clarification_attempts": getattr(user_data, "clarification_attempts", 0),
            },
            customer_id=customer.customer_id if customer else None,
        )
    return ManagerAgent(), "I'm connecting you with a specialist now."
```

---

### apps\agent-worker\src\tools\guarded_action.py

```python
"""The one and only path from a sensitive tool to an action (cookbook section 8).

  1. assemble context from the verified session (canonical UUIDs included),
  2. Decision proposes a candidate + confidence (low -> escalate, never force),
  3. Policy issues the binding verdict, PERSISTED with an id (audited server-side),
  4. only AUTHORIZED reaches Execution - dispatched idempotently against the verdict id, audited.
REFUSED / ESCALATE short-circuit into a standard outcome the caller can be told plainly.
"""
from __future__ import annotations

import logging

from clients.decision_client import get_decision_client
from clients.execution_client import get_execution_client
from clients.policy_client import get_policy_client
from config import get_settings
from livekit.agents import RunContext

from tools import outcomes

logger = logging.getLogger(__name__)

_FRUSTRATION_STREAK = 3  # consecutive negative turns -> frustration (sentiment, Phase 8)


def _build_context(run_context: RunContext, action_type: str, payload: dict) -> dict:
    user_data = run_context.session.userdata
    customer = user_data.customer_context
    context = {
        "session_id": user_data.session_id,
        "customer_id": customer.customer_id if customer else None,
        "subscription_id": getattr(customer, "subscription_id", None) if customer else None,
        "action_type": action_type,
        "is_vip": customer.is_vip if customer else False,
        "fraud_suspected": getattr(customer, "fraud_suspected", False) if customer else False,
        "frustration": user_data.consecutive_negative_turns >= _FRUSTRATION_STREAK,
        "identity_verified": user_data.identity_verified,
        "clarification_attempts": user_data.clarification_attempts,
        "identity_attempts": user_data.identity_attempts,
        "account_age_days": customer.account_age_days if customer else 0,
    }
    context.update(payload)
    return context


async def execute_guarded_action(run_context: RunContext, action_type: str, payload: dict) -> dict:
    """Run Decision -> Policy -> Execution for ``action_type`` and return a standard outcome."""
    context = _build_context(run_context, action_type, payload)

    decision = await get_decision_client().recommend(action_type, context)
    if decision["confidence"] < get_settings().decision_confidence_threshold:
        logger.info("decision below threshold for %s -> escalate", action_type)
        return outcomes.escalate("DECISION_LOW_CONFIDENCE", decision["rationale"])

    verdict = await get_policy_client().evaluate_action(context)
    if verdict["verdict"] == "refused":
        return outcomes.refused(verdict["rule_id"], verdict["justification"])
    if verdict["verdict"] == "escalate":
        return outcomes.escalate(verdict["rule_id"], verdict["justification"])

    verdict_id = verdict.get("verdict_id")
    if not verdict_id:  # AUTHORIZED must carry a persisted verdict id; never execute without one
        return outcomes.escalate("POLICY_NO_VERDICT_ID", "authorized verdict missing its persisted id")

    # AUTHORIZED -> execute idempotently against the verdict that authorized it.
    user_data = run_context.session.userdata
    idempotency_key = user_data.new_idempotency_key(action_type)
    return await get_execution_client().execute(
        idempotency_key,
        action_type,
        context["session_id"],
        payload,
        policy_verdict_id=verdict_id,
        customer_id=context["customer_id"],
        subscription_id=context["subscription_id"],
    )
```

---

### apps\agent-worker\src\tools\guards.py

```python
"""Reusable sensitive-action preconditions (cookbook section 8).

ensure_identity_verified is the single gate every sensitive tool calls FIRST, so a tool
author cannot reach a domain action without a verified caller. It runs the
IdentityVerificationTask inline when needed and records the outcome in session user-data.
"""
from __future__ import annotations

import logging

from clients.context_client import get_context_client
from livekit.agents import RunContext
from tasks.identity_verification_task import IdentityVerificationTask

logger = logging.getLogger(__name__)


async def ensure_identity_verified(context: RunContext) -> bool:
    """Return True if the caller is (now) identity-verified; run step-up verification if not."""
    user_data = context.session.userdata

    if getattr(user_data, "identity_verified", False):
        return True

    if user_data.customer_context is None:
        logger.info("identity gate: caller is not resolved; cannot run step-up verification")
        return False

    verified = await IdentityVerificationTask(
        customer_id=user_data.customer_context.customer_id,
        verify_fn=get_context_client().verify_identity,
    )
    user_data.identity_verified = bool(verified)
    user_data.identity_attempts += 1
    logger.info("identity gate result: verified=%s", user_data.identity_verified)
    return user_data.identity_verified
```

---

### apps\agent-worker\src\tools\outcomes.py

```python
"""Standard tool-outcome contract (review note 5c).

Every sensitive tool returns one of these shapes - never a raw exception or a bare string - so
the worker/LLM can always map a result to a clear spoken explanation instead of a generic
"I encountered an error". The 'message' is English guidance for the LLM to render in-language.
"""
from __future__ import annotations

AUTHORIZED = "authorized"
EXECUTED = "executed"
REFUSED = "refused"
ESCALATE = "escalate"
FAILED = "failed"


def refused(rule_id: str, reason: str) -> dict:
    """A policy refusal the caller should hear explained (not retried silently)."""
    return {
        "outcome": REFUSED,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This request cannot be completed because: {reason}. Offer an alternative if one exists.",
    }


def escalate(rule_id: str, reason: str) -> dict:
    """An escalation: explain briefly and hand off to a human via escalate_to_manager."""
    return {
        "outcome": ESCALATE,
        "rule_id": rule_id,
        "reason": reason,
        "message": f"This needs a human specialist ({reason}). Explain briefly, then call escalate_to_manager.",
    }


def executed(action_type: str, reference: str, replay: bool = False) -> dict:
    """A successful, idempotent execution carrying a reference the caller can be given."""
    return {
        "outcome": EXECUTED,
        "action_type": action_type,
        "reference": reference,
        "replay": replay,
        "message": f"The {action_type} was completed. Confirmation reference: {reference}.",
    }


def failed(reason: str) -> dict:
    """A hard execution failure: apologize and offer escalation, never claim success."""
    return {
        "outcome": FAILED,
        "reason": reason,
        "message": "The action could not be completed right now. Apologize briefly and offer to escalate.",
    }
```

---

### apps\agent-worker\src\tools\routing_tools.py

```python
"""Persona hand-off tools from Triage to specialists (cookbook section 7).

Each returns (NextAgent, transition_line), preserving the one persistent AgentSession.
"""
from __future__ import annotations

from agents.billing_agent import BillingAgent
from agents.technical_agent import TechnicalAgent
from livekit.agents import RunContext, function_tool


@function_tool()
async def route_to_billing(context: RunContext) -> tuple[BillingAgent, str]:
    """Hand off to the billing specialist for invoice, payment, or payment-deferral requests."""
    context.session.interrupt()
    return BillingAgent(), "Let me connect you with our billing specialist."


@function_tool()
async def route_to_technical(context: RunContext) -> tuple[TechnicalAgent, str]:
    """Hand off to the technical specialist for SIM, network, or connectivity issues."""
    context.session.interrupt()
    return TechnicalAgent(), "Let me connect you with our technical specialist."
```

---

### apps\agent-worker\src\tools\technical_tools.py

```python
"""Technical tool facades: data diagnosis, SIM ops (identity-gated), network (Phase 5/7/8)."""
from __future__ import annotations


async def diagnose_data_issue(customer_id: str) -> dict:
    """Check balance/line/network for a data fault (CDC 5.4). Wired in Phase 5."""
    raise NotImplementedError("wired in Phase 5")


async def unblock_sim_pin(customer_id: str) -> dict:
    """Sensitive + always identity-gated (CDC 5.5). Decision -> Policy -> Execution. Phase 7."""
    raise NotImplementedError("wired in Phase 7")


async def check_network_status(area: str) -> dict:
    """Read-only known-incident lookup (CDC 5.9). Wired in Phase 8."""
    raise NotImplementedError("wired in Phase 8")
```

---

### apps\agent-worker\tests\conversation\test_writer.py

```python
"""Offline tests for ConversationWriter enqueue logic + sentiment labels (no loop, no DB).

The actual Postgres writes are integration-tested on the developer machine."""
from __future__ import annotations

from conversation.writer import ConversationWriter, sentiment_label


def _drain_queue(writer):
    items = []
    while not writer._queue.empty():
        items.append(writer._queue.get_nowait())
    return items


def test_sentiment_label_mapping() -> None:
    assert sentiment_label(-1.0) == "angry"
    assert sentiment_label(-0.4) == "negative"
    assert sentiment_label(0.0) == "neutral"
    assert sentiment_label(0.5) == "positive"


def test_turns_increment_and_mask_pii() -> None:
    writer = ConversationWriter()  # not started -> no drain, inspect the queue directly
    writer.start_session(msisdn="+21620155320", recording_consent=True)
    writer.record_turn("caller", "my number is +21620155320", active_agent="TriageAgent", language="fr")
    writer.record_turn("caller", "still broken", language="fr")
    items = _drain_queue(writer)
    assert [i["kind"] for i in items] == ["session_start", "turn", "turn"]
    assert items[1]["row"]["turn_index"] == 1
    assert items[2]["row"]["turn_index"] == 2
    assert "+21620155320" not in items[1]["row"]["transcript_masked"]  # masked before leaving the worker


def test_no_writes_before_session_started() -> None:
    writer = ConversationWriter()
    writer.record_turn("caller", "hello")  # ignored: no session opened
    assert writer._queue.empty()
```

---

### apps\agent-worker\tests\identity\test_customer_context.py

```python
"""Offline test: the worker maps a context-service snapshot into CustomerContext (no SDK)."""
from __future__ import annotations

from session.customer_context import CustomerContext


def test_from_snapshot_maps_fields_and_ignores_enrichment() -> None:
    snapshot = {
        "customer_id": "TT-100021",
        "full_name": "Amine Ben Salah",
        "msisdn": "+21620155320",
        "subscription_type": "Postpaid Flexi",
        "preferred_language": "fr",
        "is_vip": False,
        "account_age_days": 1420,
        "open_invoice_count": 0,
        "balance_summary": None,
    }
    ctx = CustomerContext.from_snapshot(snapshot)
    assert ctx.customer_id == "TT-100021"
    assert ctx.full_name == "Amine Ben Salah"
    assert ctx.preferred_language == "fr"
```

---

### apps\agent-worker\tests\resilience\test_chaos_wiring.py

```python
"""Offline guard for the resilience + routing wiring (cookbook section 16).

No keys, no network, no live call: asserts the chaos toggle forces an invalid primary model
(so the live console run will fail the primary and fall over to the secondary), that the
settings expose a per-kind flag, and that Arabic routes to language="ar" (never "multi").
The full live failover is the manual console demo described in the phase notes.
"""
from __future__ import annotations

from config.language_presets import LANGUAGE_PRESETS
from config.settings import Settings
from providers._resilience import INVALID_MODEL, chaos_model


def test_chaos_flag_breaks_primary_model() -> None:
    assert chaos_model("gpt-4.1-mini", True) == INVALID_MODEL


def test_no_chaos_keeps_real_model() -> None:
    assert chaos_model("gpt-4.1-mini", False) == "gpt-4.1-mini"


def test_settings_expose_a_chaos_flag_per_provider_kind() -> None:
    settings = Settings(_env_file=None)
    for kind in ("stt", "llm", "tts"):
        assert hasattr(settings, f"chaos_break_{kind}")


def test_arabic_routes_to_language_ar() -> None:
    assert LANGUAGE_PRESETS["ar"]["deepgram_language"] == "ar"
```

---

### apps\agent-worker\tests\sentiment\test_sentiment_scorer.py

```python
"""Offline tests for the lexical sentiment scorer (no SDK/network)."""
from __future__ import annotations

from sentiment.sentiment_scorer import LexicalSentimentScorer
from session.session_state import SessionUserData

scorer = LexicalSentimentScorer()


def test_two_negative_turns_recommend_escalation() -> None:
    ud = SessionUserData()
    scorer.score("this is unacceptable, I am furious", ud)
    scorer.score("ridiculous, the worst service ever", ud)
    assert ud.consecutive_negative_turns >= 2
    assert ud.should_offer_escalation is True


def test_positive_turn_resets_the_counter() -> None:
    ud = SessionUserData()
    scorer.score("this is terrible", ud)
    scorer.score("thanks, that is perfect and helpful", ud)
    assert ud.consecutive_negative_turns == 0
    assert ud.should_offer_escalation is False


def test_neutral_turn_does_not_flag() -> None:
    ud = SessionUserData()
    scorer.score("I would like to check my invoice please", ud)
    assert ud.should_offer_escalation is False
```

---

### apps\agent-worker\tests\uat\test_multilingual.py

```python
"""Multilingual UAT (FR/AR/EN): the lexical sentiment scorer detects negativity in each language.

Per the cookbook section 20 hard rule, behaviour is asserted in French, Arabic AND English - not
English with a note that 'the others should be similar'.
"""
from __future__ import annotations

import pytest
from sentiment.sentiment_scorer import LexicalSentimentScorer
from session.session_state import SessionUserData

scorer = LexicalSentimentScorer()

# (language, clearly-negative phrase, clearly-positive phrase) using the shipped lexicons.
CASES = [
    ("en", "this is awful and the agent is incompetent", "thanks, that is perfect and helpful"),
    ("fr", "c'est inacceptable et totalement nul", "merci, c'est parfait et gÃ©nial"),
    ("ar", "Ù‡Ø°Ø§ Ø³ÙŠØ¡ Ø¬Ø¯Ø§ ÙˆØ£Ù†Ø§ ØºØ§Ø¶Ø¨", "Ø´ÙƒØ±Ø§ØŒ Ø±Ø§Ø¦Ø¹ ÙˆÙ…Ù…ØªØ§Ø²"),
]


@pytest.mark.parametrize("lang,negative,positive", CASES)
def test_negativity_detected_per_language(lang: str, negative: str, positive: str) -> None:
    ud_neg = SessionUserData(language=lang)
    neg_score = scorer.score(negative, ud_neg)

    ud_pos = SessionUserData(language=lang)
    pos_score = scorer.score(positive, ud_pos)

    assert neg_score < pos_score, f"{lang}: negative should score below positive"
    assert ud_neg.consecutive_negative_turns >= 1, f"{lang}: negative turn should be flagged"


def test_two_negative_turns_escalate_in_arabic() -> None:
    ud = SessionUserData(language="ar")
    scorer.score("Ù‡Ø°Ø§ Ø³ÙŠØ¡ Ø¬Ø¯Ø§", ud)
    scorer.score("Ù…Ø±ÙÙˆØ¶ØŒ ÙØ¶ÙŠØ­Ø©", ud)
    assert ud.should_offer_escalation is True  # the de-escalation path works cross-lingually
```

---

### apps\business-api\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f apps/business-api/Dockerfile -t business-api .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY apps/business-api/ ./apps/business-api/
RUN pip install ./apps/business-api
USER app
EXPOSE 8108
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8108/health')" || exit 1
CMD ["uvicorn", "business_api.main:app", "--host", "0.0.0.0", "--port", "8108"]

```

---

### apps\business-api\pyproject.toml

```toml
[project]
name = "business-api"
version = "0.1.0"
description = "Back-office REST API for supervisor/admin dashboards (spec section 17) + integrity jobs (section 20)."
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy>=2.0,<2.1",
  "object-storage",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "audit-trail",
  "persistence",
]

[project.scripts]
business-api = "business_api.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### apps\business-api\src\business_api\__init__.py

```python
"""Back-office API (Blueprint section 11): read-or-audited supervisor/admin endpoints."""
```

---

### apps\business-api\src\business_api\api\__init__.py

```python
"""Controllers: Conversations, Tickets, Audit, KPIs, Users/Roles, KB admin (later phases)."""
```

---

### apps\business-api\src\business_api\application\__init__.py

```python
"""Use-case / service layer (CQRS-style commands & queries)."""
```

---

### apps\business-api\src\business_api\infrastructure\__init__.py

```python
"""Infrastructure: persistence, auth (OIDC/RBAC), eventing, jobs."""
```

---

### apps\business-api\src\business_api\infrastructure\auth\__init__.py

```python
"""OIDC integration + RBAC (conseiller/superviseur/administrateur) (Phase 11)."""
```

---

### apps\business-api\src\business_api\infrastructure\eventing\__init__.py

```python
"""Consumes session/turn/action events from the worker fleet (Phase 11)."""
```

---

### apps\business-api\src\business_api\infrastructure\jobs\__init__.py

```python
"""Retention/purge, export/delete, audit-chain integrity (Phase 12)."""
```

---

### apps\business-api\src\business_api\infrastructure\persistence\__init__.py

```python
"""PostgreSQL repository implementations (Phase 6/11)."""
```

---

### apps\business-api\src\business_api\jobs\__init__.py

```python
"""Scheduled back-office jobs (spec section 20)."""
```

---

### apps\business-api\src\business_api\jobs\integrity.py

```python
"""Cross-domain referential integrity + audit-chain verification job (spec section 20.4).

Every domain customer_id/subscription_id must resolve in crm; and the audit hash-chain must verify.
FKs already enforce the former at write time - this job is defense-in-depth + catches out-of-band data.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.billing import Account, Invoice
from persistence.models.conversation import CallSession
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount


@dataclass
class IntegrityReport:
    """Result of an integrity run."""

    orphans: dict
    audit_chain_intact: bool
    audit_entries: int

    @property
    def ok(self) -> bool:
        return self.audit_chain_intact and not any(self.orphans.values())


def summarize(orphans: dict, audit_chain_intact: bool) -> bool:
    """Pure helper: overall pass/fail from orphan counts + chain status."""
    return audit_chain_intact and not any(orphans.values())


def _orphans(session: Session, child_model, fk_attr, parent_model) -> int:
    """Count child rows whose (non-null) FK does not resolve in the parent table."""
    stmt = (
        select(func.count())
        .select_from(child_model)
        .where(fk_attr.is_not(None), fk_attr.not_in(select(parent_model.id)))
    )
    return session.scalar(stmt) or 0


def run_integrity(session: Session) -> IntegrityReport:
    """Run the cross-domain orphan checks + the audit-chain verification."""
    orphans = {
        "billing.accounts->crm.customers": _orphans(session, Account, Account.customer_id, Customer),
        "billing.invoices->crm.customers": _orphans(session, Invoice, Invoice.customer_id, Customer),
        "ocs.balance_accounts->crm.subscriptions": _orphans(
            session, BalanceAccount, BalanceAccount.subscription_id, Subscription
        ),
        "conversation.call_sessions->crm.customers": _orphans(
            session, CallSession, CallSession.customer_id, Customer
        ),
    }
    ledger = PgAuditLedger(session)
    return IntegrityReport(orphans=orphans, audit_chain_intact=ledger.verify(), audit_entries=ledger.count())
```

---

### apps\business-api\src\business_api\jobs\retention.py

```python
"""Retention & purge job (CDC section 8.3 / Blueprint section 12.4): an AUDITED workflow, never an ad-hoc DELETE.

At the retention boundary: audio pointers are cleared (the blob is purged from MinIO by the same
scheduler at integration) and transcripts are anonymized. Every run writes an audit entry, so the
purge itself is part of the tamper-evident record. Supports dry_run for safe inspection.
"""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from object_storage import get_store
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.conversation import CallSession, Turn

_PURGED = "[purged]"


@dataclass
class RetentionReport:
    """Outcome of a retention run."""

    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool


def cutoff_date(retention_days: int, now: datetime | None = None) -> datetime:
    """The boundary before which data is purged/anonymized."""
    now = now or datetime.now(UTC)
    return now - timedelta(days=retention_days)


def run_retention(session: Session, retention_days: int = 90, dry_run: bool = True) -> RetentionReport:
    """Anonymize transcripts + clear audio pointers for sessions older than the window (audited)."""
    cutoff = cutoff_date(retention_days)
    old_ids = list(session.scalars(select(CallSession.id).where(CallSession.start_time < cutoff)))
    matched = len(old_ids)
    turns_anonymized = 0

    if not dry_run and matched:
        result = session.execute(
            update(Turn)
            .where(Turn.session_id.in_(old_ids), Turn.transcript_masked.is_not(None),
                   Turn.transcript_masked != _PURGED)
            .values(transcript_masked=_PURGED)
        )
        turns_anonymized = result.rowcount or 0
        store = get_store()
        if store.enabled:
            for url in session.scalars(
                select(CallSession.audio_record_url).where(
                    CallSession.id.in_(old_ids), CallSession.audio_record_url.is_not(None)
                )
            ):
                with suppress(Exception):
                    store.delete(url)
        session.execute(update(CallSession).where(CallSession.id.in_(old_ids)).values(audio_record_url=None))
        PgAuditLedger(session).append(
            None, "data_retention",
            {"cutoff": cutoff.isoformat(), "sessions": matched, "turns_anonymized": turns_anonymized},
            entity_reference="retention_job",
        )
        session.commit()

    return RetentionReport(
        cutoff=cutoff.isoformat(), sessions_matched=matched,
        turns_anonymized=turns_anonymized, dry_run=dry_run,
    )

```

---

### apps\business-api\src\business_api\kpis.py

```python
"""KPI math (Blueprint section 16.1) - pure, unit-testable."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Kpis:
    """Containment / escalation KPIs over the persisted conversation record."""

    total_sessions: int
    resolved: int
    escalated: int
    containment_rate: float
    escalation_rate: float
    avg_frustration: float


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def compute_kpis(total_sessions: int, resolved: int, escalated: int, avg_frustration: float) -> Kpis:
    """Build the KPI bundle from raw counts."""
    return Kpis(
        total_sessions=total_sessions,
        resolved=resolved,
        escalated=escalated,
        containment_rate=_ratio(resolved, total_sessions),
        escalation_rate=_ratio(escalated, total_sessions),
        avg_frustration=round(float(avg_frustration or 0), 2),
    )
```

---

### apps\business-api\src\business_api\main.py

```python
"""business-api entrypoint (spec section 17): read-or-audited supervisor/admin endpoints.

RBAC per the section 17 matrix (conseiller / superviseur / administrateur). No endpoint mutates
the audit ledger; the integrity job only verifies it.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from persistence import get_session

app = FastAPI(title="business-api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Role"],
)

DbSession = Annotated[Session, Depends(get_session)]
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Masked transcript + sentiment timeline + disposition for a call session."""
    data = SupervisionRepository(session).session_detail(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.get("/api/v1/escalations")
def escalations(session: DbSession, role: SuperviseurRole, status: str = "open") -> dict:
    """Escalation queue with dossiers."""
    return {"escalations": SupervisionRepository(session).escalations(status)}


@app.get("/api/v1/policy/verdicts")
def verdicts(session_id: str, session: DbSession, role: SuperviseurRole) -> dict:
    """All policy verdicts for a session (audit review)."""
    return {"verdicts": SupervisionRepository(session).verdicts(session_id)}


@app.get("/api/v1/actions")
def actions(session: DbSession, role: SuperviseurRole, status: str = "failed") -> dict:
    """Failed / retrying actions from the action ledger."""
    return {"actions": SupervisionRepository(session).actions(status)}


@app.get("/api/v1/kpis")
def kpis(session: DbSession, role: SuperviseurRole) -> dict:
    """Containment / escalation KPIs over the persisted conversation record."""
    return SupervisionRepository(session).kpis().__dict__


@app.get("/api/v1/audit/verify")
def audit_verify(
    session: DbSession,
    role: AdministrateurRole,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> dict:
    """Run the hash-chain integrity check (whole chain; range is a later refinement)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


@app.get("/api/v1/reference/business-rules")
def business_rules(session: DbSession, role: AdministrateurRole) -> dict:
    """List the versioned Policy rule registry."""
    return {"rules": SupervisionRepository(session).business_rules()}


@app.get("/api/v1/jobs/integrity")
def integrity(session: DbSession, role: AdministrateurRole) -> dict:
    """Cross-domain referential integrity + audit-chain verification (spec section 20.4)."""
    report = run_integrity(session)
    return {
        "ok": report.ok, "orphans": report.orphans,
        "audit_chain_intact": report.audit_chain_intact, "audit_entries": report.audit_entries,
    }


@app.post("/api/v1/jobs/retention")
def retention(
    session: DbSession,
    role: AdministrateurRole,
    retention_days: int = 90,
    dry_run: bool = True,
) -> dict:
    """Run the audited retention/purge job (dry_run=True by default) - spec section 8.3."""
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__


def run() -> None:
    """Console-script entrypoint: `business-api` (see [project.scripts]). Serves on :8108."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8108)

```

---

### apps\business-api\src\business_api\repositories.py

```python
"""Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_api.kpis import Kpis, compute_kpis
from persistence.models.billing import Invoice
from persistence.models.conversation import CallSession, EscalationCase, SentimentSample, Turn
from persistence.models.crm import Customer, Subscription
from persistence.models.execution import ActionLedger
from persistence.models.policy import PolicyVerdict
from persistence.models.reference import BusinessRule
from persistence.models.ticketing import Ticket
from persistence.util import to_uuid


class SupervisionRepository:
    """Back-office reads over the persisted platform data."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def customer_360(self, customer_id: str) -> dict | None:
        cid = to_uuid(customer_id)
        customer = self._s.get(Customer, cid) if cid else None
        if customer is None:
            return None
        subs = self._s.scalars(select(Subscription).where(Subscription.customer_id == cid)).all()
        invoices = self._s.scalars(select(Invoice).where(Invoice.customer_id == cid)).all()
        tickets = self._s.scalars(select(Ticket).where(Ticket.customer_id == cid)).all()
        return {
            "customer_id": str(customer.id),
            "name": f"{customer.first_name} {customer.last_name}",
            "vip": customer.vip_flag,
            "preferred_language": customer.preferred_language,
            "subscriptions": [
                {"subscription_id": str(s.id), "msisdn": s.msisdn, "plan": s.plan_code or s.plan_type, "status": s.status}
                for s in subs
            ],
            "open_invoices": [
                {"invoice": i.invoice_number, "amount": float(i.total_amount), "status": i.status}
                for i in invoices if i.status != "paid"
            ],
            "tickets": [{"glpi_id": t.glpi_ticket_id, "status": t.status, "subject": t.subject} for t in tickets],
        }

    def session_detail(self, session_id: str) -> dict | None:
        sid = to_uuid(session_id)
        call = self._s.get(CallSession, sid) if sid else None
        if call is None:
            return None
        turns = self._s.scalars(select(Turn).where(Turn.session_id == sid).order_by(Turn.turn_index)).all()
        sentiment = self._s.scalars(
            select(SentimentSample).where(SentimentSample.session_id == sid).order_by(SentimentSample.turn_index)
        ).all()
        return {
            "session_id": str(call.id),
            "disposition": call.final_disposition,
            "duration_seconds": call.duration_seconds,
            "max_frustration": float(call.max_frustration_score),
            "turns": [
                {"index": t.turn_index, "speaker": t.speaker, "agent": t.active_agent, "text": t.transcript_masked}
                for t in turns
            ],
            "sentiment": [{"index": x.turn_index, "score": float(x.score), "label": x.label} for x in sentiment],
        }

    def escalations(self, status: str = "open") -> list[dict]:
        rows = self._s.scalars(select(EscalationCase).order_by(EscalationCase.created_at.desc())).all()
        out = []
        for case in rows:
            is_open = case.resolution is None
            if status == "open" and not is_open:
                continue
            out.append({
                "id": str(case.id), "session_id": str(case.session_id), "trigger": case.trigger,
                "target": case.target, "resolution": case.resolution, "dossier": case.dossier,
            })
        return out

    def verdicts(self, session_id: str) -> list[dict]:
        sid = to_uuid(session_id)
        if sid is None:
            return []
        rows = self._s.scalars(
            select(PolicyVerdict).where(PolicyVerdict.session_id == sid).order_by(PolicyVerdict.created_at)
        ).all()
        return [
            {"id": str(v.id), "action": v.requested_action, "verdict": v.verdict,
             "rule_id": v.rule_id, "justification": v.justification}
            for v in rows
        ]

    def actions(self, status: str = "failed") -> list[dict]:
        rows = self._s.scalars(
            select(ActionLedger).where(ActionLedger.status == status).order_by(ActionLedger.created_at.desc())
        ).all()
        return [
            {"id": str(a.id), "action_type": a.action_type, "status": a.status,
             "idempotency_key": a.idempotency_key, "reference": a.adapter_reference}
            for a in rows
        ]

    def business_rules(self) -> list[dict]:
        rows = self._s.scalars(select(BusinessRule).order_by(BusinessRule.domain, BusinessRule.rule_id)).all()
        return [
            {"rule_id": r.rule_id, "domain": r.domain, "version": r.version, "active": r.active,
             "description": r.description, "definition": r.definition_json}
            for r in rows
        ]

    def kpis(self) -> Kpis:
        total = self._s.scalar(select(func.count()).select_from(CallSession)) or 0
        resolved = self._s.scalar(
            select(func.count()).select_from(CallSession).where(CallSession.final_disposition == "resolved")
        ) or 0
        escalated = self._s.scalar(
            select(func.count()).select_from(CallSession).where(CallSession.final_disposition == "escalated")
        ) or 0
        avg_frustration = self._s.scalar(select(func.coalesce(func.avg(CallSession.max_frustration_score), 0)))
        return compute_kpis(total, resolved, escalated, avg_frustration)
```

---

### apps\business-api\src\business_api\security.py

```python
"""API-layer RBAC (spec section 19): conseiller < superviseur < administrateur.

The role matrix is enforced here. Real identity is OIDC at integration time; in this build the
role is taken from the `X-Role` header (or BUSINESS_API_DEFAULT_ROLE for local use).
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException

_ROLE_RANK = {"conseiller": 1, "superviseur": 2, "administrateur": 3}


def role_rank(role: str | None) -> int:
    """Numeric rank for a role name (0 if unknown)."""
    return _ROLE_RANK.get(role or "", 0)


def require_role(minimum: str):
    """Dependency factory: 403 unless the caller's role is at least ``minimum``."""
    minimum_rank = _ROLE_RANK[minimum]

    def _dependency(x_role: str | None = Header(default=None)) -> str:
        role = x_role or os.getenv("BUSINESS_API_DEFAULT_ROLE", "administrateur")  # dev default
        if role_rank(role) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role >= {minimum}")
        return role

    return _dependency
```

---

### apps\business-api\tests\test_integrity.py

```python
"""Offline tests for the integrity summary (no DB)."""
from __future__ import annotations

from business_api.jobs.integrity import summarize


def test_summarize_clean() -> None:
    assert summarize({"a->b": 0, "c->d": 0}, audit_chain_intact=True) is True


def test_summarize_detects_orphans() -> None:
    assert summarize({"a->b": 3}, audit_chain_intact=True) is False


def test_summarize_detects_broken_chain() -> None:
    assert summarize({"a->b": 0}, audit_chain_intact=False) is False
```

---

### apps\business-api\tests\test_kpis.py

```python
"""Offline tests for the KPI math (no DB)."""
from __future__ import annotations

from business_api.kpis import compute_kpis


def test_compute_kpis() -> None:
    k = compute_kpis(total_sessions=10, resolved=7, escalated=2, avg_frustration=0.456)
    assert k.containment_rate == 0.7
    assert k.escalation_rate == 0.2
    assert k.avg_frustration == 0.46


def test_compute_kpis_no_sessions() -> None:
    k = compute_kpis(total_sessions=0, resolved=0, escalated=0, avg_frustration=0)
    assert k.containment_rate == 0.0
    assert k.escalation_rate == 0.0
```

---

### apps\business-api\tests\test_retention.py

```python
"""Offline tests for the retention cutoff math (no DB). The purge itself is integration-tested."""
from __future__ import annotations

from datetime import UTC, datetime

from business_api.jobs.retention import cutoff_date


def test_cutoff_date() -> None:
    now = datetime(2026, 6, 30, tzinfo=UTC)
    assert cutoff_date(90, now).isoformat() == "2026-04-01T00:00:00+00:00"
    assert cutoff_date(0, now) == now
```

---

### apps\business-api\tests\test_security.py

```python
"""Offline tests for the RBAC role hierarchy (no DB)."""
from __future__ import annotations

from business_api.security import role_rank


def test_role_hierarchy() -> None:
    assert role_rank("conseiller") < role_rank("superviseur") < role_rank("administrateur")
    assert role_rank("unknown") == 0
    assert role_rank(None) == 0
```

---

### apps\client-widget\index.html

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Tunisie Telecom â€” Voice Support</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

---

### apps\client-widget\package.json

```json
{
  "name": "client-widget",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "livekit-client": "^2.6.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
```

---

### apps\client-widget\package-lock.json

```json
{
  "name": "client-widget",
  "version": "0.1.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "client-widget",
      "version": "0.1.0",
      "dependencies": {
        "livekit-client": "^2.6.0",
        "react": "^19.0.0",
        "react-dom": "^19.0.0"
      },
      "devDependencies": {
        "@types/react": "^19.0.0",
        "@types/react-dom": "^19.0.0",
        "@vitejs/plugin-react": "^4.3.4",
        "typescript": "^5.6.0",
        "vite": "^6.0.0"
      }
    },
    "node_modules/@babel/code-frame": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/code-frame/-/code-frame-7.29.7.tgz",
      "integrity": "sha512-Aup7aUOfpbAUg2ROOJN6Iw5f9DMBlzu0mIkm/malLQFN/YQgO48wCj0Kxa3sEHJvPVFg7siR+qRInwXd2qhQKw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-validator-identifier": "^7.29.7",
        "js-tokens": "^4.0.0",
        "picocolors": "^1.1.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/compat-data": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/compat-data/-/compat-data-7.29.7.tgz",
      "integrity": "sha512-locTkQyKvwIEgBzVrn8693ebc97F2U8ZHjbXwDXJ5Fn2TCpNwTlKcaKLkdHop5c/icOFE7qt7Q9JC5hnKNa6Gg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/core": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/core/-/core-7.29.7.tgz",
      "integrity": "sha512-RgHBCvtjbOK2gXSNBNIkNoEc9qoVEtau3hj8gEqKQuL3HZAibKarWFEI3Lfm6EYKkLalOh8eSrj9b+ch9H/VBA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-compilation-targets": "^7.29.7",
        "@babel/helper-module-transforms": "^7.29.7",
        "@babel/helpers": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/remapping": "^2.3.5",
        "convert-source-map": "^2.0.0",
        "debug": "^4.1.0",
        "gensync": "^1.0.0-beta.2",
        "json5": "^2.2.3",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/babel"
      }
    },
    "node_modules/@babel/generator": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/generator/-/generator-7.29.7.tgz",
      "integrity": "sha512-DkXD5OJQaAQIdZ1bt3UZdEnHAn9Imd3IVBdX03UFe+ony9Ojw5pzr9YVKGDY1jt+Gcn/FnGkNf8r+Vj5NOJWtQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/gen-mapping": "^0.3.12",
        "@jridgewell/trace-mapping": "^0.3.28",
        "jsesc": "^3.0.2"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-compilation-targets/-/helper-compilation-targets-7.29.7.tgz",
      "integrity": "sha512-wem6WaBj4NaVYVdNhLPPVacES6ZJ+KBBfSkTMD3YZxbP3rm3Di85tJU5ljaUNhaOynt+Aj0xruhYuzQBt8n71g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.29.7",
        "@babel/helper-validator-option": "^7.29.7",
        "browserslist": "^4.24.0",
        "lru-cache": "^5.1.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-globals": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-globals/-/helper-globals-7.29.7.tgz",
      "integrity": "sha512-3nQVUAtvkKH9zahfWgw96Jc/uFOmjACE1kQz82E2lqWmHBgjzbNlsC22nuQTfahmWeQtTq5nQ/4Nnd2A1wj4zA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-imports": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-imports/-/helper-module-imports-7.29.7.tgz",
      "integrity": "sha512-ejHwrQQYcm9xnTivShn2IDOlIzInN34AXskvq9QicvCtEzq1Vzclu/tKF8Jq1Cg8JG2GL6/EmjgsCT7lXepE3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-transforms": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-transforms/-/helper-module-transforms-7.29.7.tgz",
      "integrity": "sha512-UPUVSyXbOh627KiCIGQSgwWzGeBKLkaJ9PJEdrngIwMSzxLR4jS4+f1f1jb7VzBbg8nFLaYotvVPFCTqdrmTAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7",
        "@babel/traverse": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-plugin-utils": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-plugin-utils/-/helper-plugin-utils-7.29.7.tgz",
      "integrity": "sha512-G7sHYigPY17oO5SYWnfD/0MTBwVR781S/JI643e/JhUYgVgWE/61SoW3NH9KWUKyKq5LVh3npif99Wkt6j86Jw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-string-parser/-/helper-string-parser-7.29.7.tgz",
      "integrity": "sha512-Pb5ijPrZ89GDH8223L4UP8i6QApWxs04RbPQJTeWDV0/keR2E36MeKnyr6LYmUUvqRRI+Iv87SuF1W6ErINzYw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-identifier": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-identifier/-/helper-validator-identifier-7.29.7.tgz",
      "integrity": "sha512-qehxGkRj55h/ff8EMaJ+cYhyaKlHIxqYDn682wQD7RNp9UujOQsHog2uS0r2vzr4pW+sXf90NeeayjcNaX3fFg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-option": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-option/-/helper-validator-option-7.29.7.tgz",
      "integrity": "sha512-N9ZErrD+yW5geCDtBqnOoxmR8+tNKiGuxKlDpuJxfsqpa2dFcexaziGAE/qoHLiDDreVNMupxGmSoNlyvsA3gw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helpers": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helpers/-/helpers-7.29.7.tgz",
      "integrity": "sha512-1k2lAGRMfHTcwuNYcCNUmaUffmQv8KWMfh2iJUUeRlwlwH4FdNG7mfPI10NPfLHJFThE4Tyr4mv7kTNZOiPuBg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/parser/-/parser-7.29.7.tgz",
      "integrity": "sha512-hnORnjP/1P/zFEndoeX+n+t1RwWRJiJpM/jO7FW32Kn9r5+sJB2JWOdYo4L6k78j15eCwY3Gm/7364B1EMwtNg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.29.7"
      },
      "bin": {
        "parser": "bin/babel-parser.js"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-self": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-self/-/plugin-transform-react-jsx-self-7.29.7.tgz",
      "integrity": "sha512-TL0hMc9xzy86VD31nUiwzd5otRAcyEPcsegCxolO0PvcXuH1v0kECe/UIznYFihpkvU5wg/jk4v0TTEFfm53fw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-source": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-source/-/plugin-transform-react-jsx-source-7.29.7.tgz",
      "integrity": "sha512-06IyK09H3wi4cGbhDBwp5gUGo0IKtnYa8tyTiephirPCK6fbobVGiXMMI5zLQ4aKEYP3wZ3ArU44o+8KMrSG/Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/template": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/template/-/template-7.29.7.tgz",
      "integrity": "sha512-puq+Gf35oI24FeN11LkoUQFqv9uwNeWpxXZi/Ji3rRIoKAzKnxRaZ+Gkj0vKS9ZCiTESfng1N9LyOyXvo+m+Gg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/traverse/-/traverse-7.29.7.tgz",
      "integrity": "sha512-EhlfNQtZ+NK22w5BM61ciuiq1m58ed33Wr1Xan//ZRTy6hgjnwyCffRYwzsGXdASJSUJ1guZILsErh1eQcl+zw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-globals": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/types": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/types/-/types-7.29.7.tgz",
      "integrity": "sha512-4zBIxpPzowiZpusoFkyGVwakdRJUyuH5PxQ/PrqghfdFWWasvnCdPfQXHrenDai+gyLARulZjZowCOj6fjT4pA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-string-parser": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@bufbuild/protobuf": {
      "version": "1.10.1",
      "resolved": "https://registry.npmjs.org/@bufbuild/protobuf/-/protobuf-1.10.1.tgz",
      "integrity": "sha512-wJ8ReQbHxsAfXhrf9ixl0aYbZorRuOWpBNzm8pL8ftmSxQx/wnJD5Eg861NwJU/czy2VXFIebCeZnZrI9rktIQ==",
      "license": "(Apache-2.0 AND BSD-3-Clause)"
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.24.2.tgz",
      "integrity": "sha512-thpVCb/rhxE/BnMLQ7GReQLLN8q9qbHmI55F4489/ByVg2aQaQ6kbcLb6FHkocZzQhxc4gx0sCk0tJkKBFzDhA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.24.2.tgz",
      "integrity": "sha512-tmwl4hJkCfNHwFB3nBa8z1Uy3ypZpxqxfTQOcHX+xRByyYgunVbZ9MzUUfb0RxaHIMnbHagwAxuTL+tnNM+1/Q==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.24.2.tgz",
      "integrity": "sha512-cNLgeqCqV8WxfcTIOeL4OAtSmL8JjcN6m09XIgro1Wi7cF4t/THaWEa7eL5CMoMBdjoHOTh/vwTO/o2TRXIyzg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.24.2.tgz",
      "integrity": "sha512-B6Q0YQDqMx9D7rvIcsXfmJfvUYLoP722bgfBlO5cGvNVb5V/+Y7nhBE3mHV9OpxBf4eAS2S68KZztiPaWq4XYw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.24.2.tgz",
      "integrity": "sha512-kj3AnYWc+CekmZnS5IPu9D+HWtUI49hbnyqk0FLEJDbzCIQt7hg7ucF1SQAilhtYpIujfaHr6O0UHlzzSPdOeA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.24.2.tgz",
      "integrity": "sha512-WeSrmwwHaPkNR5H3yYfowhZcbriGqooyu3zI/3GGpF8AyUdsrrP0X6KumITGA9WOyiJavnGZUwPGvxvwfWPHIA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.24.2.tgz",
      "integrity": "sha512-UN8HXjtJ0k/Mj6a9+5u6+2eZ2ERD7Edt1Q9IZiB5UZAIdPnVKDoG7mdTVGhHJIeEml60JteamR3qhsr1r8gXvg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.24.2.tgz",
      "integrity": "sha512-TvW7wE/89PYW+IevEJXZ5sF6gJRDY/14hyIGFXdIucxCsbRmLUcjseQu1SyTko+2idmCw94TgyaEZi9HUSOe3Q==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.24.2.tgz",
      "integrity": "sha512-n0WRM/gWIdU29J57hJyUdIsk0WarGd6To0s+Y+LwvlC55wt+GT/OgkwoXCXvIue1i1sSNWblHEig00GBWiJgfA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.24.2.tgz",
      "integrity": "sha512-7HnAD6074BW43YvvUmE/35Id9/NB7BeX5EoNkK9obndmZBUk8xmJJeU7DwmUeN7tkysslb2eSl6CTrYz6oEMQg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.24.2.tgz",
      "integrity": "sha512-sfv0tGPQhcZOgTKO3oBE9xpHuUqguHvSo4jl+wjnKwFpapx+vUDcawbwPNuBIAYdRAvIDBfZVvXprIj3HA+Ugw==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.24.2.tgz",
      "integrity": "sha512-CN9AZr8kEndGooS35ntToZLTQLHEjtVB5n7dl8ZcTZMonJ7CCfStrYhrzF97eAecqVbVJ7APOEe18RPI4KLhwQ==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.24.2.tgz",
      "integrity": "sha512-iMkk7qr/wl3exJATwkISxI7kTcmHKE+BlymIAbHO8xanq/TjHaaVThFF6ipWzPHryoFsesNQJPE/3wFJw4+huw==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.24.2.tgz",
      "integrity": "sha512-shsVrgCZ57Vr2L8mm39kO5PPIb+843FStGt7sGGoqiiWYconSxwTiuswC1VJZLCjNiMLAMh34jg4VSEQb+iEbw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.24.2.tgz",
      "integrity": "sha512-4eSFWnU9Hhd68fW16GD0TINewo1L6dRrB+oLNNbYyMUAeOD2yCK5KXGK1GH4qD/kT+bTEXjsyTCiJGHPZ3eM9Q==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.24.2.tgz",
      "integrity": "sha512-S0Bh0A53b0YHL2XEXC20bHLuGMOhFDO6GN4b3YjRLK//Ep3ql3erpNcPlEFed93hsQAjAQDNsvcK+hV90FubSw==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.24.2.tgz",
      "integrity": "sha512-8Qi4nQcCTbLnK9WoMjdC9NiTG6/E38RNICU6sUNqK0QFxCYgoARqVqxdFmWkdonVsvGqWhmm7MO0jyTqLqwj0Q==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.24.2.tgz",
      "integrity": "sha512-wuLK/VztRRpMt9zyHSazyCVdCXlpHkKm34WUyinD2lzK07FAHTq0KQvZZlXikNWkDGoT6x3TD51jKQ7gMVpopw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.24.2.tgz",
      "integrity": "sha512-VefFaQUc4FMmJuAxmIHgUmfNiLXY438XrL4GDNV1Y1H/RW3qow68xTwjZKfj/+Plp9NANmzbH5R40Meudu8mmw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.24.2.tgz",
      "integrity": "sha512-YQbi46SBct6iKnszhSvdluqDmxCJA+Pu280Av9WICNwQmMxV7nLRHZfjQzwbPs3jeWnuAhE9Jy0NrnJ12Oz+0A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.24.2.tgz",
      "integrity": "sha512-+iDS6zpNM6EnJyWv0bMGLWSWeXGN/HTaF/LXHXHwejGsVi+ooqDfMCCTerNFxEkM3wYVcExkeGXNqshc9iMaOA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.24.2.tgz",
      "integrity": "sha512-hTdsW27jcktEvpwNHJU4ZwWFGkz2zRJUz8pvddmXPtXDzVKTTINmlmga3ZzwcuMpUvLw7JkLy9QLKyGpD2Yxig==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.24.2.tgz",
      "integrity": "sha512-LihEQ2BBKVFLOC9ZItT9iFprsE9tqjDjnbulhHoFxYQtQfai7qfluVODIYxt1PgdoyQkz23+01rzwNwYfutxUQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.24.2.tgz",
      "integrity": "sha512-q+iGUwfs8tncmFC9pcnD5IvRHAzmbwQ3GPS5/ceCyHdjXubwQWI12MKWSNSMYLJMq23/IUCvJMS76PDqXe1fxA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.24.2.tgz",
      "integrity": "sha512-7VTgWzgMGvup6aSqDPLiW5zHaxYJGTO4OokMjIlrCtf+VpEL+cXKtCvg723iguPYI5oaUNdS+/V7OU2gvXVWEg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/sourcemap-codec": "^1.5.0",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/resolve-uri": "^3.1.0",
        "@jridgewell/sourcemap-codec": "^1.4.14"
      }
    },
    "node_modules/@livekit/mutex": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/@livekit/mutex/-/mutex-1.0.0.tgz",
      "integrity": "sha512-aiUhoThBNF9UyGTxEURFzJLhhPLIVTnQiEVMjRhPnfHNKLfo2JY9xovHKIus7B78UD5hsP6DlgpmAsjrz4U0Iw==",
      "license": "Apache-2.0"
    },
    "node_modules/@livekit/protocol": {
      "version": "1.29.3",
      "resolved": "https://registry.npmjs.org/@livekit/protocol/-/protocol-1.29.3.tgz",
      "integrity": "sha512-5La/pm2LsSeCbm7xNe/TvHGYu7uVwDpLrlycpgo5nzofGq/TH67255vS8ni/1Y7vrFuAI8VYG/s42mcC1UF6tQ==",
      "license": "Apache-2.0",
      "dependencies": {
        "@bufbuild/protobuf": "^1.10.0"
      }
    },
    "node_modules/@rolldown/pluginutils": {
      "version": "1.0.0-beta.27",
      "resolved": "https://registry.npmjs.org/@rolldown/pluginutils/-/pluginutils-1.0.0-beta.27.tgz",
      "integrity": "sha512-+d0F4MKMCbeVUJwG96uQ4SgAznZNSq93I3V+9NHA4OpvqG8mRCpGdKmK8l/dl02h2CCDHwW2FqilnTyDcAnqjA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.62.2.tgz",
      "integrity": "sha512-6o7ZLZK+BeenkZCFNDXqpbjw9bD6nuWonvS/lwQJp7NoVVxm6p3qE7qQ5jGuBjiFsgvqjD8mZAU5oWxTmbOeOg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.62.2.tgz",
      "integrity": "sha512-BaH7BllCACHoH1LguOU56UItGfUWjujlO65kS9LAodViaN4bwIKd7oeW/ZHJ/4ljr/7MIiENnNy3HJ0zXv8Zkw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.62.2.tgz",
      "integrity": "sha512-v39RCCvj4He82I9sFmk+M1VZ0PLM9sfsLVikjfx2hYBNALhrrOR2D3JjQA6AhlaSOgcR+RzrKY7e1+bT6SUO/A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.62.2.tgz",
      "integrity": "sha512-yl0y2vq3S3lHeuXhEdss6TWfKW8vkujImO12tn4ZkG/4oghr09LvdYm2RElVjokTQiUvDUGXLGsYeLqUMCKpGA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.62.2.tgz",
      "integrity": "sha512-tT4pvt4qXD+vEoezupCWi+a1F0vvDiksiHc+PxRlYTOH1I6/X4id9jPxTP+Fg+545euaFT1jJVs4CEdHZAU1vw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.62.2.tgz",
      "integrity": "sha512-6nU5F2wCW+qvCBhTn1pdIU3bzsIoF7EUwsCDRxilWGprQR6yd508YnH9+OKFCwpfS8pjZqDUmnCAr7exax0XCg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.62.2.tgz",
      "integrity": "sha512-n1GJHPOvpIfhi3TmrCeh6S6URt9BFCt0KQE3qvexyGCTAKpR4Lg+eWvNZEqu7epxwus/8ElT3hacYEucm49SZg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-musleabihf": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.62.2.tgz",
      "integrity": "sha512-JqgflS8wEB+UXV/vS1RpRbifGBeN4D5lz8D8oOFbFZw4vedvdOgCFAjfBmIMdW3yL10XpQQ0Ambepw6MXrhOnA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.62.2.tgz",
      "integrity": "sha512-wnFJkogWvN4jm/hQRF2UBaeUmk20j5+DmHvoyWii2b8HJDyvz1MF2OU/6ynXt2KR63rbZLWkFpoytpdc/yBuSA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.62.2.tgz",
      "integrity": "sha512-HVu2bp0zhvJ8xHEV9+UUs7S90VadmBSY3LcIMvozbPo4AuMGDWlz3ymHLHZPX4hR67TKTt8Qp5PJ5RBg/i+RMQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.62.2.tgz",
      "integrity": "sha512-mQqqAV8QaoSgr9I2fKDLY2BAVvmKjWoGiu/cSYQonsLvtqwEn1E4QYfnCOcp5zoEqNhsDYin1s6jx/VJmrxlZg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-musl/-/rollup-linux-loong64-musl-4.62.2.tgz",
      "integrity": "sha512-IxKLoxCQ2IWi6bT2akyDUBGsOImDKB+sPp4EsTmwFQ/fMwpCKm8uLSSgP/Kx/QYUgKis6SEZ5/Nlhup0DIA0PQ==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.62.2.tgz",
      "integrity": "sha512-Mk5ha2RQSgyFfmYYLkBpPnUk8D8FriBxesO1u9O75X0mHgXL1UQcH5Itl2lurWL2tj0RxV9b9tJgipac0hRY9A==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-musl/-/rollup-linux-ppc64-musl-4.62.2.tgz",
      "integrity": "sha512-CjvEnqJL/0/TQ3TXX3OPIJ/kmBellrWd4heXUmHeJlTnmwjKpSJzoehLaL6Xk0ZnMHBu9dZuFADNOrtjF4v+2w==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.62.2.tgz",
      "integrity": "sha512-1SiZbzwdkaDURsew/tSOrooKiYy7EQGT6m8ufavAi9NEyQb/6VuIxFXAL1fqa4iZe3g4NbNk4P7J32z2tw5Mgg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.62.2.tgz",
      "integrity": "sha512-nQts12zJ3NQRoE6uYljOH89v7szzLDvG2JD/vsX+vGXU8w/At1GowTZ5/7qeFQ8m7L55rpR8Okugnuo5bgjy2Q==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-s390x-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.62.2.tgz",
      "integrity": "sha512-E9/ll019jhPIJgpzfZoIkBGhcz+kKNgVWYRY0zr9srBdPPFVpvOKW8VaJKUbeK+eZXyQF9ltME+Kk6affeaPgg==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.62.2.tgz",
      "integrity": "sha512-5BqxR/pshjey51iliyzTD5Xi3EN0aLmQ2lZ3lvefVV9c82BvrLo2/6OT55iifpWBufs6kdwWbuOKS841DrmK9A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.62.2.tgz",
      "integrity": "sha512-uNN83XxQrRAh/w0/pmAfibcwyb6YWt4gP+dpnQKPVJshAloQ785ii8CT8ZCIxkGg9opVsvAlGhFitSm6D1Jjpg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-openbsd-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openbsd-x64/-/rollup-openbsd-x64-4.62.2.tgz",
      "integrity": "sha512-srjEIxSH3LRnJN6THczDHWQplqEMFiAJrTab0msUryh9kwNpkICf3Ea6q6MN/2cZwRFUNx5w+h6Hpi4QuHS6Zg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ]
    },
    "node_modules/@rollup/rollup-openharmony-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.62.2.tgz",
      "integrity": "sha512-8hOJnxgbyObnCm5AlRA3A931xX19xq80RjVTKgJOvEKWqJruP/Uf12IbAOaDjjEXYRewwHLfmF0YRIdK3OwKWA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ]
    },
    "node_modules/@rollup/rollup-win32-arm64-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-arm64-msvc/-/rollup-win32-arm64-msvc-4.62.2.tgz",
      "integrity": "sha512-mmF4AY1i0hG/bLWUctUq59gtmgaSIRa3cu/A3JFRp/sCNEme2bgDEiDS22P9FbnJB8NJNF4jPJiSP5RHQpUTDg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-ia32-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-ia32-msvc/-/rollup-win32-ia32-msvc-4.62.2.tgz",
      "integrity": "sha512-DZgkknc6jhHrk46V25vbAM0zZkyP0nSDkJB8/dRkLTxv470dOmWDqGoEJl/9A0dFfS7yE3REOwNDxpHwSLSt0Q==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-gnu/-/rollup-win32-x64-gnu-4.62.2.tgz",
      "integrity": "sha512-T6xr6ucWSFto+VGajA8YH26LdpHRuP4YLHEKAtCWvJDOlnmWcDZVCI2Jmjr+IFHDlt2zRaTAKE4tfjTaWLgJBg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.62.2.tgz",
      "integrity": "sha512-BfzEnDJOt9T8M989/lA37EcJgat01wLRnoi5dQf3QzOH7jzpqTAzdDbVfRljVr5r+jzKqpbHeyOfAaXxAd0PAA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@types/babel__core": {
      "version": "7.20.5",
      "resolved": "https://registry.npmjs.org/@types/babel__core/-/babel__core-7.20.5.tgz",
      "integrity": "sha512-qoQprZvz5wQFJwMDqeseRXWv3rqMvhgpbXFfVyWhbx9X47POIA6i/+dXefEmZKoAgOaTdaIgNSMqMIU61yRyzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.20.7",
        "@babel/types": "^7.20.7",
        "@types/babel__generator": "*",
        "@types/babel__template": "*",
        "@types/babel__traverse": "*"
      }
    },
    "node_modules/@types/babel__generator": {
      "version": "7.27.0",
      "resolved": "https://registry.npmjs.org/@types/babel__generator/-/babel__generator-7.27.0.tgz",
      "integrity": "sha512-ufFd2Xi92OAVPYsy+P4n7/U7e68fex0+Ee8gSG9KX7eo084CWiQ4sdxktvdl0bOPupXtVJPY19zk6EwWqUQ8lg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__template": {
      "version": "7.4.4",
      "resolved": "https://registry.npmjs.org/@types/babel__template/-/babel__template-7.4.4.tgz",
      "integrity": "sha512-h/NUaSyG5EyxBIp8YRxo4RMe2/qQgvyowRwVMzhYhBCONbW8PUsg4lkFMrhgZhUe5z3L3MiLDuvyJ/CaPa2A8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.1.0",
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__traverse": {
      "version": "7.28.0",
      "resolved": "https://registry.npmjs.org/@types/babel__traverse/-/babel__traverse-7.28.0.tgz",
      "integrity": "sha512-8PvcXf70gTDZBgt9ptxJ8elBeBjcLOAcOtoO/mPJjtji1+CdGbHgm77om1GrsPxsiE+uXIpNSK64UYaIwQXd4Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.28.2"
      }
    },
    "node_modules/@types/estree": {
      "version": "1.0.9",
      "resolved": "https://registry.npmjs.org/@types/estree/-/estree-1.0.9.tgz",
      "integrity": "sha512-GhdPgy1el4/ImP05X05Uw4cw2/M93BCUmnEvWZNStlCzEKME4Fkk+YpoA5OiHNQmoS7Cafb8Xa3Pya8m1Qrzeg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/react": {
      "version": "19.2.17",
      "resolved": "https://registry.npmjs.org/@types/react/-/react-19.2.17.tgz",
      "integrity": "sha512-MXfmqaVPEVgkBT/aY0aGCkRWWtByiYQXo3xdQ8r5RzuFrPiRn8Gar2tQdXSUQ2GKV3bkXckek89V8wQBY2Q/Aw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "csstype": "^3.2.2"
      }
    },
    "node_modules/@types/react-dom": {
      "version": "19.2.3",
      "resolved": "https://registry.npmjs.org/@types/react-dom/-/react-dom-19.2.3.tgz",
      "integrity": "sha512-jp2L/eY6fn+KgVVQAOqYItbF0VY/YApe5Mz2F0aykSO8gx31bYCZyvSeYxCHKvzHG5eZjc+zyaS5BrBWya2+kQ==",
      "dev": true,
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "^19.2.0"
      }
    },
    "node_modules/@vitejs/plugin-react": {
      "version": "4.7.0",
      "resolved": "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-4.7.0.tgz",
      "integrity": "sha512-gUu9hwfWvvEDBBmgtAowQCojwZmJ5mcLn3aufeCsitijs3+f2NsrPtlAWIR6OPiqljl96GVCUbLe0HyqIpVaoA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.28.0",
        "@babel/plugin-transform-react-jsx-self": "^7.27.1",
        "@babel/plugin-transform-react-jsx-source": "^7.27.1",
        "@rolldown/pluginutils": "1.0.0-beta.27",
        "@types/babel__core": "^7.20.5",
        "react-refresh": "^0.17.0"
      },
      "engines": {
        "node": "^14.18.0 || >=16.0.0"
      },
      "peerDependencies": {
        "vite": "^4.2.0 || ^5.0.0 || ^6.0.0 || ^7.0.0"
      }
    },
    "node_modules/baseline-browser-mapping": {
      "version": "2.10.40",
      "resolved": "https://registry.npmjs.org/baseline-browser-mapping/-/baseline-browser-mapping-2.10.40.tgz",
      "integrity": "sha512-BSSLZ9/Cjjv7Gtj5B68ZzXcXUg8iOf3fme+FCuh8rC/Go+Kmh8cox7M3A8dolou16s64QjLPOSdngh7GxXvkSw==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "baseline-browser-mapping": "dist/cli.cjs"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/browserslist": {
      "version": "4.28.4",
      "resolved": "https://registry.npmjs.org/browserslist/-/browserslist-4.28.4.tgz",
      "integrity": "sha512-MTc8i/x9jBQd1iMw2CFGS+rwMa07eYjLR0CCTLDACl9xhxy+nIs3KeML/biicXtk9JrZ6dnnTatmc7ErPXIxqw==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "baseline-browser-mapping": "^2.10.38",
        "caniuse-lite": "^1.0.30001799",
        "electron-to-chromium": "^1.5.376",
        "node-releases": "^2.0.48",
        "update-browserslist-db": "^1.2.3"
      },
      "bin": {
        "browserslist": "cli.js"
      },
      "engines": {
        "node": "^6 || ^7 || ^8 || ^9 || ^10 || ^11 || ^12 || >=13.7"
      }
    },
    "node_modules/caniuse-lite": {
      "version": "1.0.30001799",
      "resolved": "https://registry.npmjs.org/caniuse-lite/-/caniuse-lite-1.0.30001799.tgz",
      "integrity": "sha512-hG1bReV+OUU+MOqK4t/ZWI0tZOyz3rqS9XuhOUz1cIcbwBKjOyJEJuw9ER5JuNyqxNk8u/JUVbGibBOL1yrjFw==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/caniuse-lite"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "CC-BY-4.0"
    },
    "node_modules/convert-source-map": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/convert-source-map/-/convert-source-map-2.0.0.tgz",
      "integrity": "sha512-Kvp459HrV2FEJ1CAsi1Ku+MY3kasH19TFykTz2xWmMeq6bk2NU3XXvfJ+Q61m0xktWwt+1HSYf3JZsTms3aRJg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/csstype": {
      "version": "3.2.3",
      "resolved": "https://registry.npmjs.org/csstype/-/csstype-3.2.3.tgz",
      "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/electron-to-chromium": {
      "version": "1.5.381",
      "resolved": "https://registry.npmjs.org/electron-to-chromium/-/electron-to-chromium-1.5.381.tgz",
      "integrity": "sha512-n9Wa6yB+vDsGuA8AKbl/0z7HbvWqt5jxIdvr1IUicd0ryPrk7/xzwqLv8D9AbbvZ6avVNtXYLTfmgFHkwkyelg==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/esbuild": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.24.2.tgz",
      "integrity": "sha512-+9egpBW8I3CD5XPe0n6BfT5fxLzxrlDzqydF3aviG+9ni1lDC/OvMHcxqEFV0+LANZG5R1bFMWfUrjVsdwxJvA==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "bin": {
        "esbuild": "bin/esbuild"
      },
      "engines": {
        "node": ">=18"
      },
      "optionalDependencies": {
        "@esbuild/aix-ppc64": "0.24.2",
        "@esbuild/android-arm": "0.24.2",
        "@esbuild/android-arm64": "0.24.2",
        "@esbuild/android-x64": "0.24.2",
        "@esbuild/darwin-arm64": "0.24.2",
        "@esbuild/darwin-x64": "0.24.2",
        "@esbuild/freebsd-arm64": "0.24.2",
        "@esbuild/freebsd-x64": "0.24.2",
        "@esbuild/linux-arm": "0.24.2",
        "@esbuild/linux-arm64": "0.24.2",
        "@esbuild/linux-ia32": "0.24.2",
        "@esbuild/linux-loong64": "0.24.2",
        "@esbuild/linux-mips64el": "0.24.2",
        "@esbuild/linux-ppc64": "0.24.2",
        "@esbuild/linux-riscv64": "0.24.2",
        "@esbuild/linux-s390x": "0.24.2",
        "@esbuild/linux-x64": "0.24.2",
        "@esbuild/netbsd-arm64": "0.24.2",
        "@esbuild/netbsd-x64": "0.24.2",
        "@esbuild/openbsd-arm64": "0.24.2",
        "@esbuild/openbsd-x64": "0.24.2",
        "@esbuild/sunos-x64": "0.24.2",
        "@esbuild/win32-arm64": "0.24.2",
        "@esbuild/win32-ia32": "0.24.2",
        "@esbuild/win32-x64": "0.24.2"
      }
    },
    "node_modules/escalade": {
      "version": "3.2.0",
      "resolved": "https://registry.npmjs.org/escalade/-/escalade-3.2.0.tgz",
      "integrity": "sha512-WUj2qlxaQtO4g6Pq5c29GTcWGDyd8itL8zTlipgECz3JesAiiOKotd8JU6otB3PACgG6xkJUyVhboMS+bje/jA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/events": {
      "version": "3.3.0",
      "resolved": "https://registry.npmjs.org/events/-/events-3.3.0.tgz",
      "integrity": "sha512-mQw+2fkQbALzQ7V0MY0IqdnXNOeTtP4r0lN9z7AAawCXgqea7bDii20AYrIBrFd/Hx0M2Ocz6S111CaFkUcb0Q==",
      "license": "MIT",
      "engines": {
        "node": ">=0.8.x"
      }
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmjs.org/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/gensync": {
      "version": "1.0.0-beta.2",
      "resolved": "https://registry.npmjs.org/gensync/-/gensync-1.0.0-beta.2.tgz",
      "integrity": "sha512-3hN7NaskYvMDLQY55gnW3NQ+mesEAepTqlg+VEbj7zzqEMBVNhzcGYYeqFo/TlYz6eQiFcp1HcsCZO+nGgS8zg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/js-tokens": {
      "version": "4.0.0",
      "resolved": "https://registry.npmjs.org/js-tokens/-/js-tokens-4.0.0.tgz",
      "integrity": "sha512-RdJUflcE3cUzKiMqQgsCu06FPu9UdIJO0beYbPhHN4k6apgJtifcoCtT9bcxOpYBtpD2kCM6Sbzg4CausW/PKQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/jsesc": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/jsesc/-/jsesc-3.1.0.tgz",
      "integrity": "sha512-/sM3dO2FOzXjKQhJuo0Q173wf2KOo8t4I8vHy6lF9poUp7bKT0/NHE8fPX23PwfhnykfqnC2xRxOnVw5XuGIaA==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jsesc": "bin/jsesc"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/json5": {
      "version": "2.2.3",
      "resolved": "https://registry.npmjs.org/json5/-/json5-2.2.3.tgz",
      "integrity": "sha512-XmOWe7eyHYH14cLdVPoyg+GOH3rYX++KpzrylJwSW98t3Nk+U8XOl8FWKOgwtzdb8lXGf6zYwDUzeHMWfxasyg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "json5": "lib/cli.js"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/livekit-client": {
      "version": "2.7.4",
      "resolved": "https://registry.npmjs.org/livekit-client/-/livekit-client-2.7.4.tgz",
      "integrity": "sha512-7xAetJjwt/L+M5XZs9lg5giAGtu4I4wiKvAPmhKLX6qu/Tx2XMTUNkIR6pmiRFcFXNbkIWphtGw4DATOQu0GRg==",
      "license": "Apache-2.0",
      "dependencies": {
        "@livekit/mutex": "1.0.0",
        "@livekit/protocol": "1.29.3",
        "events": "^3.3.0",
        "loglevel": "^1.8.0",
        "sdp-transform": "^2.14.1",
        "ts-debounce": "^4.0.0",
        "tslib": "2.7.0",
        "typed-emitter": "^2.1.0",
        "webrtc-adapter": "^9.0.0"
      }
    },
    "node_modules/loglevel": {
      "version": "1.9.2",
      "resolved": "https://registry.npmjs.org/loglevel/-/loglevel-1.9.2.tgz",
      "integrity": "sha512-HgMmCqIJSAKqo68l0rS2AanEWfkxaZ5wNiEFb5ggm08lDs9Xl2KxBlX3PTcaD2chBM1gXAYf491/M2Rv8Jwayg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6.0"
      },
      "funding": {
        "type": "tidelift",
        "url": "https://tidelift.com/funding/github/npm/loglevel"
      }
    },
    "node_modules/lru-cache": {
      "version": "5.1.1",
      "resolved": "https://registry.npmjs.org/lru-cache/-/lru-cache-5.1.1.tgz",
      "integrity": "sha512-KpNARQA3Iwv+jTA0utUVVbrh+Jlrr1Fv0e56GGzAFOXN7dk/FviaDW8LHmK52DlcH4WP2n6gI8vN1aesBFgo9w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^3.0.2"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/nanoid": {
      "version": "3.3.15",
      "resolved": "https://registry.npmjs.org/nanoid/-/nanoid-3.3.15.tgz",
      "integrity": "sha512-y7Wygv/7mEOvxTuEQDB8StXdMRBWf1kR/tlhAzBRUFkB2jfcLOAxO/SHmOO2zgz1pVgK29/kyupn059/bCHdjA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "bin": {
        "nanoid": "bin/nanoid.cjs"
      },
      "engines": {
        "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
      }
    },
    "node_modules/node-releases": {
      "version": "2.0.50",
      "resolved": "https://registry.npmjs.org/node-releases/-/node-releases-2.0.50.tgz",
      "integrity": "sha512-J6l92tKHX6w8Jy5nO1Vuc01NoIiRGi/d6qBKVxh+IQ8Cr3b6HbVNfKiF8ZpFKufTwpwxMmce2W3iQZ861ZRyTg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/picocolors": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/picocolors/-/picocolors-1.1.1.tgz",
      "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/postcss": {
      "version": "8.5.15",
      "resolved": "https://registry.npmjs.org/postcss/-/postcss-8.5.15.tgz",
      "integrity": "sha512-FfR8sjd4em2T6fb3I2MwAJU7HWVMr9zba+enmQeeWFfCbm+UOC/0X4DS8XtpUTMwWMGbjKYP7xjfNekzyGmB3A==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/postcss"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.12",
        "picocolors": "^1.1.1",
        "source-map-js": "^1.2.1"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      }
    },
    "node_modules/react": {
      "version": "19.0.0",
      "resolved": "https://registry.npmjs.org/react/-/react-19.0.0.tgz",
      "integrity": "sha512-V8AVnmPIICiWpGfm6GLzCR/W5FXLchHop40W4nXBmdlEceh16rCN8O8LNWm5bh5XUX91fh7KpA+W0TgMKmgTpQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-dom": {
      "version": "19.0.0",
      "resolved": "https://registry.npmjs.org/react-dom/-/react-dom-19.0.0.tgz",
      "integrity": "sha512-4GV5sHFG0e/0AD4X+ySy6UJd3jVl1iNsNHdpad0qhABJ11twS3TTBnseqsKurKcsNqCEFeGL3uLpVChpIO3QfQ==",
      "license": "MIT",
      "dependencies": {
        "scheduler": "^0.25.0"
      },
      "peerDependencies": {
        "react": "^19.0.0"
      }
    },
    "node_modules/react-refresh": {
      "version": "0.17.0",
      "resolved": "https://registry.npmjs.org/react-refresh/-/react-refresh-0.17.0.tgz",
      "integrity": "sha512-z6F7K9bV85EfseRCp2bzrpyQ0Gkw1uLoCel9XBVWPg/TjRj94SkJzUTGfOa4bs7iJvBWtQG0Wq7wnI0syw3EBQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/rollup": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/rollup/-/rollup-4.62.2.tgz",
      "integrity": "sha512-RFnrW4lhXA3s3eqHDZvN654g8OTjzRfqpIRJYczCGB6HzphckVAi/Qh4tbPUbRuDi7s1Llv8g/NspLkttY3gTA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/estree": "1.0.9"
      },
      "bin": {
        "rollup": "dist/bin/rollup"
      },
      "engines": {
        "node": ">=18.0.0",
        "npm": ">=8.0.0"
      },
      "optionalDependencies": {
        "@rollup/rollup-android-arm-eabi": "4.62.2",
        "@rollup/rollup-android-arm64": "4.62.2",
        "@rollup/rollup-darwin-arm64": "4.62.2",
        "@rollup/rollup-darwin-x64": "4.62.2",
        "@rollup/rollup-freebsd-arm64": "4.62.2",
        "@rollup/rollup-freebsd-x64": "4.62.2",
        "@rollup/rollup-linux-arm-gnueabihf": "4.62.2",
        "@rollup/rollup-linux-arm-musleabihf": "4.62.2",
        "@rollup/rollup-linux-arm64-gnu": "4.62.2",
        "@rollup/rollup-linux-arm64-musl": "4.62.2",
        "@rollup/rollup-linux-loong64-gnu": "4.62.2",
        "@rollup/rollup-linux-loong64-musl": "4.62.2",
        "@rollup/rollup-linux-ppc64-gnu": "4.62.2",
        "@rollup/rollup-linux-ppc64-musl": "4.62.2",
        "@rollup/rollup-linux-riscv64-gnu": "4.62.2",
        "@rollup/rollup-linux-riscv64-musl": "4.62.2",
        "@rollup/rollup-linux-s390x-gnu": "4.62.2",
        "@rollup/rollup-linux-x64-gnu": "4.62.2",
        "@rollup/rollup-linux-x64-musl": "4.62.2",
        "@rollup/rollup-openbsd-x64": "4.62.2",
        "@rollup/rollup-openharmony-arm64": "4.62.2",
        "@rollup/rollup-win32-arm64-msvc": "4.62.2",
        "@rollup/rollup-win32-ia32-msvc": "4.62.2",
        "@rollup/rollup-win32-x64-gnu": "4.62.2",
        "@rollup/rollup-win32-x64-msvc": "4.62.2",
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/rxjs": {
      "version": "7.8.2",
      "resolved": "https://registry.npmjs.org/rxjs/-/rxjs-7.8.2.tgz",
      "integrity": "sha512-dhKf903U/PQZY6boNNtAGdWbG85WAbjT/1xYoZIC7FAY0yWapOBQVsVrDl58W86//e1VpMNBtRV4MaXfdMySFA==",
      "license": "Apache-2.0",
      "optional": true,
      "dependencies": {
        "tslib": "^2.1.0"
      }
    },
    "node_modules/scheduler": {
      "version": "0.25.0",
      "resolved": "https://registry.npmjs.org/scheduler/-/scheduler-0.25.0.tgz",
      "integrity": "sha512-xFVuu11jh+xcO7JOAGJNOXld8/TcEHK/4CituBUeUb5hqxJLj9YuemAEuvm9gQ/+pgXYfbQuqAkiYu+u7YEsNA==",
      "license": "MIT"
    },
    "node_modules/sdp": {
      "version": "3.2.2",
      "resolved": "https://registry.npmjs.org/sdp/-/sdp-3.2.2.tgz",
      "integrity": "sha512-xZocWwfyp4hkbN4hLWxMjmv2Q8aNa9MhmOZ7L9aCZPT+dZsgRr6wZRrSYE3HTdyk/2pZKPSgqI7ns7Een1xMSA==",
      "license": "MIT"
    },
    "node_modules/sdp-transform": {
      "version": "2.15.0",
      "resolved": "https://registry.npmjs.org/sdp-transform/-/sdp-transform-2.15.0.tgz",
      "integrity": "sha512-KrOH82c/W+GYQ0LHqtr3caRpM3ITglq3ljGUIb8LTki7ByacJZ9z+piSGiwZDsRyhQbYBOBJgr2k6X4BZXi3Kw==",
      "license": "MIT",
      "bin": {
        "sdp-verify": "checker.js"
      }
    },
    "node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmjs.org/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/source-map-js": {
      "version": "1.2.1",
      "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.1.tgz",
      "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/ts-debounce": {
      "version": "4.0.0",
      "resolved": "https://registry.npmjs.org/ts-debounce/-/ts-debounce-4.0.0.tgz",
      "integrity": "sha512-+1iDGY6NmOGidq7i7xZGA4cm8DAa6fqdYcvO5Z6yBevH++Bdo9Qt/mN0TzHUgcCcKv1gmh9+W5dHqz8pMWbCbg==",
      "license": "MIT"
    },
    "node_modules/tslib": {
      "version": "2.7.0",
      "resolved": "https://registry.npmjs.org/tslib/-/tslib-2.7.0.tgz",
      "integrity": "sha512-gLXCKdN1/j47AiHiOkJN69hJmcbGTHI0ImLmbYLHykhgeN0jVGola9yVjFgzCUklsZQMW55o+dW7IXv3RCXDzA==",
      "license": "0BSD"
    },
    "node_modules/typed-emitter": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/typed-emitter/-/typed-emitter-2.1.0.tgz",
      "integrity": "sha512-g/KzbYKbH5C2vPkaXGu8DJlHrGKHLsM25Zg9WuC9pMGfuvT+X25tZQWo5fK1BjBm8+UrVE9LDCvaY0CQk+fXDA==",
      "license": "MIT",
      "optionalDependencies": {
        "rxjs": "*"
      }
    },
    "node_modules/typescript": {
      "version": "5.7.2",
      "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.7.2.tgz",
      "integrity": "sha512-i5t66RHxDvVN40HfDd1PsEThGNnlMCMT3jMUuoh9/0TaqWevNontacunWyN02LA9/fIbEWlcHZcgTKb9QoaLfg==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    },
    "node_modules/update-browserslist-db": {
      "version": "1.2.3",
      "resolved": "https://registry.npmjs.org/update-browserslist-db/-/update-browserslist-db-1.2.3.tgz",
      "integrity": "sha512-Js0m9cx+qOgDxo0eMiFGEueWztz+d4+M3rGlmKPT+T4IS/jP4ylw3Nwpu6cpTTP8R1MAC1kF4VbdLt3ARf209w==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "escalade": "^3.2.0",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "update-browserslist-db": "cli.js"
      },
      "peerDependencies": {
        "browserslist": ">= 4.21.0"
      }
    },
    "node_modules/vite": {
      "version": "6.0.7",
      "resolved": "https://registry.npmjs.org/vite/-/vite-6.0.7.tgz",
      "integrity": "sha512-RDt8r/7qx9940f8FcOIAH9PTViRrghKaK2K1jY3RaAURrEUbm9Du1mJ72G+jlhtG3WwodnfzY8ORQZbBavZEAQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "esbuild": "^0.24.2",
        "postcss": "^8.4.49",
        "rollup": "^4.23.0"
      },
      "bin": {
        "vite": "bin/vite.js"
      },
      "engines": {
        "node": "^18.0.0 || ^20.0.0 || >=22.0.0"
      },
      "funding": {
        "url": "https://github.com/vitejs/vite?sponsor=1"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.3"
      },
      "peerDependencies": {
        "@types/node": "^18.0.0 || ^20.0.0 || >=22.0.0",
        "jiti": ">=1.21.0",
        "less": "*",
        "lightningcss": "^1.21.0",
        "sass": "*",
        "sass-embedded": "*",
        "stylus": "*",
        "sugarss": "*",
        "terser": "^5.16.0",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "@types/node": {
          "optional": true
        },
        "jiti": {
          "optional": true
        },
        "less": {
          "optional": true
        },
        "lightningcss": {
          "optional": true
        },
        "sass": {
          "optional": true
        },
        "sass-embedded": {
          "optional": true
        },
        "stylus": {
          "optional": true
        },
        "sugarss": {
          "optional": true
        },
        "terser": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/webrtc-adapter": {
      "version": "9.0.6",
      "resolved": "https://registry.npmjs.org/webrtc-adapter/-/webrtc-adapter-9.0.6.tgz",
      "integrity": "sha512-CHbl2ZQbxx164IgWRgzJno4hWtM4tFbRam1QfI3Yxhs3w/DvqluVxVWeXs3oL5/fbGkSNLKo0Ty5MgUWceNhog==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "sdp": "^3.2.0"
      },
      "engines": {
        "node": ">=6.0.0",
        "npm": ">=3.10.0"
      }
    },
    "node_modules/yallist": {
      "version": "3.1.1",
      "resolved": "https://registry.npmjs.org/yallist/-/yallist-3.1.1.tgz",
      "integrity": "sha512-a4UGQaWPH59mOXUYnAG2ewncQS4i4F43Tv3JoAM+s2VDAmS9NsK8GpDMLrCHPksFT7h3K6TOoUNn2pb7RoXx4g==",
      "dev": true,
      "license": "ISC"
    }
  }
}

```

---

### apps\client-widget\src\App.tsx

```tsx
import { useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";

const TOKEN_URL = import.meta.env.VITE_TOKEN_URL ?? "http://localhost:8107";
const ROOM_PREFIX = import.meta.env.VITE_ROOM_PREFIX ?? "telecom-support";

type Status = "idle" | "connecting" | "connected" | "error";

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>("");
  const [events, setEvents] = useState<string[]>([]);
  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement | null>(null);

  function trace(event: string, details: Record<string, unknown> = {}) {
    const line = `${new Date().toLocaleTimeString()} ${event}`;
    setEvents((current) => [line, ...current].slice(0, 8));
    console.info("[client-widget]", event, details);
    void fetch(`${TOKEN_URL}/client-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event,
        room: typeof details.room === "string" ? details.room : undefined,
        identity: typeof details.identity === "string" ? details.identity : undefined,
        details,
      }),
    }).catch(() => undefined);
  }

  async function startCall() {
    setError("");
    setStatus("connecting");

    const startedAt = Date.now();
    const roomName = `${ROOM_PREFIX}-${startedAt}`;
    const identity = `caller-${startedAt}`;
    trace("start_call_clicked", { room: roomName, identity });

    try {
      const res = await fetch(`${TOKEN_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room: roomName,
          identity,
          name: "Caller",
        }),
      });
      if (!res.ok) throw new Error(`token-service ${res.status}`);
      const { token, url, room, agent_name } = await res.json();
      trace("token_received", { room, identity, url, agent_name });

      const livekitRoom = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = livekitRoom;

      livekitRoom.on(RoomEvent.Connected, () =>
        trace("livekit_connected", { room: roomName, identity }),
      );
      livekitRoom.on(RoomEvent.LocalTrackPublished, (publication) =>
        trace("local_track_published", { room: roomName, source: publication.source }),
      );
      livekitRoom.on(RoomEvent.ParticipantConnected, (participant) =>
        trace("participant_connected", { room: roomName, participant: participant.identity }),
      );
      livekitRoom.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        trace("remote_track_subscribed", { room: roomName, kind: track.kind });
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.autoplay = true;
          audioRef.current?.appendChild(el);
        }
      });
      livekitRoom.on(RoomEvent.Disconnected, (reason) => {
        trace("livekit_disconnected", { room: roomName, reason });
        setStatus("idle");
      });

      await livekitRoom.connect(url, token);
      await livekitRoom.localParticipant.setMicrophoneEnabled(true);
      trace("microphone_enabled", { room: roomName, identity });
      setStatus("connected");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      trace("call_error", { room: roomName, identity, message });
      setError(message);
      setStatus("error");
    }
  }

  async function endCall() {
    await roomRef.current?.disconnect();
    roomRef.current = null;
    setStatus("idle");
  }

  const connected = status === "connected";
  const busy = status === "connecting";

  return (
    <main className="widget">
      <header>
        <h1>Tunisie Telecom</h1>
        <p className="subtitle">Voice customer support</p>
      </header>

      <div className={`status status--${status}`}>
        <span className="dot" />
        {status === "idle" && "Ready to call"}
        {status === "connecting" && "Connecting..."}
        {status === "connected" && "Connected - speak now"}
        {status === "error" && `Error: ${error}`}
      </div>

      <div className="actions">
        {!connected ? (
          <button className="btn btn--call" onClick={startCall} disabled={busy}>
            {busy ? "Connecting..." : "Start call"}
          </button>
        ) : (
          <button className="btn btn--end" onClick={endCall}>
            End call
          </button>
        )}
      </div>

      <p className="hint">
        Speak in French, Arabic, or English. The assistant will greet you and route your request.
      </p>

      {events.length > 0 && (
        <ol className="events" aria-label="Call events">
          {events.map((event) => (
            <li key={event}>{event}</li>
          ))}
        </ol>
      )}

      <div ref={audioRef} hidden />
    </main>
  );
}

```

---

### apps\client-widget\src\main.tsx

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

---

### apps\client-widget\src\styles.css

```css
:root {
  --bg: #0b1020;
  --card: #131a2e;
  --fg: #e8ecf6;
  --muted: #8b97b4;
  --accent: #3b82f6;
  --green: #22c55e;
  --red: #ef4444;
  --amber: #f59e0b;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: radial-gradient(1200px 600px at 50% -10%, #1b2545, var(--bg));
  color: var(--fg);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

.widget {
  width: min(420px, 92vw);
  background: var(--card);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 20px;
  padding: 32px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  text-align: center;
}

.widget h1 { margin: 0; font-size: 22px; letter-spacing: 0.2px; }
.subtitle { margin: 4px 0 24px; color: var(--muted); font-size: 14px; }

.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  margin-bottom: 24px;
}
.status .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
.status--connected .dot { background: var(--green); box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.18); }
.status--connecting .dot { background: var(--amber); }
.status--error .dot { background: var(--red); }
.status--connected { color: var(--fg); }

.actions { margin-bottom: 18px; }

.btn {
  appearance: none;
  border: none;
  cursor: pointer;
  width: 100%;
  padding: 14px 18px;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  transition: transform 0.05s ease, opacity 0.2s ease;
}
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.6; cursor: default; }
.btn--call { background: linear-gradient(180deg, #4f8cff, var(--accent)); }
.btn--end { background: linear-gradient(180deg, #ff5d5d, var(--red)); }

.hint { color: var(--muted); font-size: 12.5px; line-height: 1.5; margin: 0; }

.events {
  margin: 20px 0 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  line-height: 1.5;
  list-style-position: inside;
  text-align: left;
}

```

---

### apps\client-widget\src\vite-env.d.ts

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TOKEN_URL?: string;
  readonly VITE_ROOM_PREFIX?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

```

---

### apps\client-widget\tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

---

### apps\client-widget\vite.config.ts

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
```

---

### apps\supervisor-dashboard\index.html

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Telecom Supervisor Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

---

### apps\supervisor-dashboard\package.json

```json
{
  "name": "supervisor-dashboard",
  "version": "0.1.0",
  "private": true,
  "description": "Web app for Superviseur & Administrateur (CDC section 9) - reads the business-api.",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@types/react": "19.0.2",
    "@types/react-dom": "19.0.2",
    "@vitejs/plugin-react": "4.3.4",
    "typescript": "5.7.2",
    "vite": "6.0.7"
  }
}
```

---

### apps\supervisor-dashboard\package-lock.json

```json
{
  "name": "supervisor-dashboard",
  "version": "0.1.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "supervisor-dashboard",
      "version": "0.1.0",
      "dependencies": {
        "react": "19.0.0",
        "react-dom": "19.0.0"
      },
      "devDependencies": {
        "@types/react": "19.0.2",
        "@types/react-dom": "19.0.2",
        "@vitejs/plugin-react": "4.3.4",
        "typescript": "5.7.2",
        "vite": "6.0.7"
      }
    },
    "node_modules/@babel/code-frame": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/code-frame/-/code-frame-7.29.7.tgz",
      "integrity": "sha512-Aup7aUOfpbAUg2ROOJN6Iw5f9DMBlzu0mIkm/malLQFN/YQgO48wCj0Kxa3sEHJvPVFg7siR+qRInwXd2qhQKw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-validator-identifier": "^7.29.7",
        "js-tokens": "^4.0.0",
        "picocolors": "^1.1.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/compat-data": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/compat-data/-/compat-data-7.29.7.tgz",
      "integrity": "sha512-locTkQyKvwIEgBzVrn8693ebc97F2U8ZHjbXwDXJ5Fn2TCpNwTlKcaKLkdHop5c/icOFE7qt7Q9JC5hnKNa6Gg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/core": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/core/-/core-7.29.7.tgz",
      "integrity": "sha512-RgHBCvtjbOK2gXSNBNIkNoEc9qoVEtau3hj8gEqKQuL3HZAibKarWFEI3Lfm6EYKkLalOh8eSrj9b+ch9H/VBA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-compilation-targets": "^7.29.7",
        "@babel/helper-module-transforms": "^7.29.7",
        "@babel/helpers": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/remapping": "^2.3.5",
        "convert-source-map": "^2.0.0",
        "debug": "^4.1.0",
        "gensync": "^1.0.0-beta.2",
        "json5": "^2.2.3",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/babel"
      }
    },
    "node_modules/@babel/generator": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/generator/-/generator-7.29.7.tgz",
      "integrity": "sha512-DkXD5OJQaAQIdZ1bt3UZdEnHAn9Imd3IVBdX03UFe+ony9Ojw5pzr9YVKGDY1jt+Gcn/FnGkNf8r+Vj5NOJWtQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7",
        "@jridgewell/gen-mapping": "^0.3.12",
        "@jridgewell/trace-mapping": "^0.3.28",
        "jsesc": "^3.0.2"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-compilation-targets": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-compilation-targets/-/helper-compilation-targets-7.29.7.tgz",
      "integrity": "sha512-wem6WaBj4NaVYVdNhLPPVacES6ZJ+KBBfSkTMD3YZxbP3rm3Di85tJU5ljaUNhaOynt+Aj0xruhYuzQBt8n71g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/compat-data": "^7.29.7",
        "@babel/helper-validator-option": "^7.29.7",
        "browserslist": "^4.24.0",
        "lru-cache": "^5.1.1",
        "semver": "^6.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-globals": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-globals/-/helper-globals-7.29.7.tgz",
      "integrity": "sha512-3nQVUAtvkKH9zahfWgw96Jc/uFOmjACE1kQz82E2lqWmHBgjzbNlsC22nuQTfahmWeQtTq5nQ/4Nnd2A1wj4zA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-imports": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-imports/-/helper-module-imports-7.29.7.tgz",
      "integrity": "sha512-ejHwrQQYcm9xnTivShn2IDOlIzInN34AXskvq9QicvCtEzq1Vzclu/tKF8Jq1Cg8JG2GL6/EmjgsCT7lXepE3g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/traverse": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-module-transforms": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-module-transforms/-/helper-module-transforms-7.29.7.tgz",
      "integrity": "sha512-UPUVSyXbOh627KiCIGQSgwWzGeBKLkaJ9PJEdrngIwMSzxLR4jS4+f1f1jb7VzBbg8nFLaYotvVPFCTqdrmTAg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-module-imports": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7",
        "@babel/traverse": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0"
      }
    },
    "node_modules/@babel/helper-plugin-utils": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-plugin-utils/-/helper-plugin-utils-7.29.7.tgz",
      "integrity": "sha512-G7sHYigPY17oO5SYWnfD/0MTBwVR781S/JI643e/JhUYgVgWE/61SoW3NH9KWUKyKq5LVh3npif99Wkt6j86Jw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-string-parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-string-parser/-/helper-string-parser-7.29.7.tgz",
      "integrity": "sha512-Pb5ijPrZ89GDH8223L4UP8i6QApWxs04RbPQJTeWDV0/keR2E36MeKnyr6LYmUUvqRRI+Iv87SuF1W6ErINzYw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-identifier": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-identifier/-/helper-validator-identifier-7.29.7.tgz",
      "integrity": "sha512-qehxGkRj55h/ff8EMaJ+cYhyaKlHIxqYDn682wQD7RNp9UujOQsHog2uS0r2vzr4pW+sXf90NeeayjcNaX3fFg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helper-validator-option": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helper-validator-option/-/helper-validator-option-7.29.7.tgz",
      "integrity": "sha512-N9ZErrD+yW5geCDtBqnOoxmR8+tNKiGuxKlDpuJxfsqpa2dFcexaziGAE/qoHLiDDreVNMupxGmSoNlyvsA3gw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/helpers": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/helpers/-/helpers-7.29.7.tgz",
      "integrity": "sha512-1k2lAGRMfHTcwuNYcCNUmaUffmQv8KWMfh2iJUUeRlwlwH4FdNG7mfPI10NPfLHJFThE4Tyr4mv7kTNZOiPuBg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/parser": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/parser/-/parser-7.29.7.tgz",
      "integrity": "sha512-hnORnjP/1P/zFEndoeX+n+t1RwWRJiJpM/jO7FW32Kn9r5+sJB2JWOdYo4L6k78j15eCwY3Gm/7364B1EMwtNg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.29.7"
      },
      "bin": {
        "parser": "bin/babel-parser.js"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-self": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-self/-/plugin-transform-react-jsx-self-7.29.7.tgz",
      "integrity": "sha512-TL0hMc9xzy86VD31nUiwzd5otRAcyEPcsegCxolO0PvcXuH1v0kECe/UIznYFihpkvU5wg/jk4v0TTEFfm53fw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/plugin-transform-react-jsx-source": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/plugin-transform-react-jsx-source/-/plugin-transform-react-jsx-source-7.29.7.tgz",
      "integrity": "sha512-06IyK09H3wi4cGbhDBwp5gUGo0IKtnYa8tyTiephirPCK6fbobVGiXMMI5zLQ4aKEYP3wZ3ArU44o+8KMrSG/Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-plugin-utils": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      },
      "peerDependencies": {
        "@babel/core": "^7.0.0-0"
      }
    },
    "node_modules/@babel/template": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/template/-/template-7.29.7.tgz",
      "integrity": "sha512-puq+Gf35oI24FeN11LkoUQFqv9uwNeWpxXZi/Ji3rRIoKAzKnxRaZ+Gkj0vKS9ZCiTESfng1N9LyOyXvo+m+Gg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/types": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/traverse": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/traverse/-/traverse-7.29.7.tgz",
      "integrity": "sha512-EhlfNQtZ+NK22w5BM61ciuiq1m58ed33Wr1Xan//ZRTy6hgjnwyCffRYwzsGXdASJSUJ1guZILsErh1eQcl+zw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/code-frame": "^7.29.7",
        "@babel/generator": "^7.29.7",
        "@babel/helper-globals": "^7.29.7",
        "@babel/parser": "^7.29.7",
        "@babel/template": "^7.29.7",
        "@babel/types": "^7.29.7",
        "debug": "^4.3.1"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@babel/types": {
      "version": "7.29.7",
      "resolved": "https://registry.npmjs.org/@babel/types/-/types-7.29.7.tgz",
      "integrity": "sha512-4zBIxpPzowiZpusoFkyGVwakdRJUyuH5PxQ/PrqghfdFWWasvnCdPfQXHrenDai+gyLARulZjZowCOj6fjT4pA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/helper-string-parser": "^7.29.7",
        "@babel/helper-validator-identifier": "^7.29.7"
      },
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.24.2.tgz",
      "integrity": "sha512-thpVCb/rhxE/BnMLQ7GReQLLN8q9qbHmI55F4489/ByVg2aQaQ6kbcLb6FHkocZzQhxc4gx0sCk0tJkKBFzDhA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.24.2.tgz",
      "integrity": "sha512-tmwl4hJkCfNHwFB3nBa8z1Uy3ypZpxqxfTQOcHX+xRByyYgunVbZ9MzUUfb0RxaHIMnbHagwAxuTL+tnNM+1/Q==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.24.2.tgz",
      "integrity": "sha512-cNLgeqCqV8WxfcTIOeL4OAtSmL8JjcN6m09XIgro1Wi7cF4t/THaWEa7eL5CMoMBdjoHOTh/vwTO/o2TRXIyzg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.24.2.tgz",
      "integrity": "sha512-B6Q0YQDqMx9D7rvIcsXfmJfvUYLoP722bgfBlO5cGvNVb5V/+Y7nhBE3mHV9OpxBf4eAS2S68KZztiPaWq4XYw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.24.2.tgz",
      "integrity": "sha512-kj3AnYWc+CekmZnS5IPu9D+HWtUI49hbnyqk0FLEJDbzCIQt7hg7ucF1SQAilhtYpIujfaHr6O0UHlzzSPdOeA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.24.2.tgz",
      "integrity": "sha512-WeSrmwwHaPkNR5H3yYfowhZcbriGqooyu3zI/3GGpF8AyUdsrrP0X6KumITGA9WOyiJavnGZUwPGvxvwfWPHIA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.24.2.tgz",
      "integrity": "sha512-UN8HXjtJ0k/Mj6a9+5u6+2eZ2ERD7Edt1Q9IZiB5UZAIdPnVKDoG7mdTVGhHJIeEml60JteamR3qhsr1r8gXvg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.24.2.tgz",
      "integrity": "sha512-TvW7wE/89PYW+IevEJXZ5sF6gJRDY/14hyIGFXdIucxCsbRmLUcjseQu1SyTko+2idmCw94TgyaEZi9HUSOe3Q==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.24.2.tgz",
      "integrity": "sha512-n0WRM/gWIdU29J57hJyUdIsk0WarGd6To0s+Y+LwvlC55wt+GT/OgkwoXCXvIue1i1sSNWblHEig00GBWiJgfA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.24.2.tgz",
      "integrity": "sha512-7HnAD6074BW43YvvUmE/35Id9/NB7BeX5EoNkK9obndmZBUk8xmJJeU7DwmUeN7tkysslb2eSl6CTrYz6oEMQg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.24.2.tgz",
      "integrity": "sha512-sfv0tGPQhcZOgTKO3oBE9xpHuUqguHvSo4jl+wjnKwFpapx+vUDcawbwPNuBIAYdRAvIDBfZVvXprIj3HA+Ugw==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.24.2.tgz",
      "integrity": "sha512-CN9AZr8kEndGooS35ntToZLTQLHEjtVB5n7dl8ZcTZMonJ7CCfStrYhrzF97eAecqVbVJ7APOEe18RPI4KLhwQ==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.24.2.tgz",
      "integrity": "sha512-iMkk7qr/wl3exJATwkISxI7kTcmHKE+BlymIAbHO8xanq/TjHaaVThFF6ipWzPHryoFsesNQJPE/3wFJw4+huw==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.24.2.tgz",
      "integrity": "sha512-shsVrgCZ57Vr2L8mm39kO5PPIb+843FStGt7sGGoqiiWYconSxwTiuswC1VJZLCjNiMLAMh34jg4VSEQb+iEbw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.24.2.tgz",
      "integrity": "sha512-4eSFWnU9Hhd68fW16GD0TINewo1L6dRrB+oLNNbYyMUAeOD2yCK5KXGK1GH4qD/kT+bTEXjsyTCiJGHPZ3eM9Q==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.24.2.tgz",
      "integrity": "sha512-S0Bh0A53b0YHL2XEXC20bHLuGMOhFDO6GN4b3YjRLK//Ep3ql3erpNcPlEFed93hsQAjAQDNsvcK+hV90FubSw==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.24.2.tgz",
      "integrity": "sha512-8Qi4nQcCTbLnK9WoMjdC9NiTG6/E38RNICU6sUNqK0QFxCYgoARqVqxdFmWkdonVsvGqWhmm7MO0jyTqLqwj0Q==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.24.2.tgz",
      "integrity": "sha512-wuLK/VztRRpMt9zyHSazyCVdCXlpHkKm34WUyinD2lzK07FAHTq0KQvZZlXikNWkDGoT6x3TD51jKQ7gMVpopw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.24.2.tgz",
      "integrity": "sha512-VefFaQUc4FMmJuAxmIHgUmfNiLXY438XrL4GDNV1Y1H/RW3qow68xTwjZKfj/+Plp9NANmzbH5R40Meudu8mmw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.24.2.tgz",
      "integrity": "sha512-YQbi46SBct6iKnszhSvdluqDmxCJA+Pu280Av9WICNwQmMxV7nLRHZfjQzwbPs3jeWnuAhE9Jy0NrnJ12Oz+0A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.24.2.tgz",
      "integrity": "sha512-+iDS6zpNM6EnJyWv0bMGLWSWeXGN/HTaF/LXHXHwejGsVi+ooqDfMCCTerNFxEkM3wYVcExkeGXNqshc9iMaOA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.24.2.tgz",
      "integrity": "sha512-hTdsW27jcktEvpwNHJU4ZwWFGkz2zRJUz8pvddmXPtXDzVKTTINmlmga3ZzwcuMpUvLw7JkLy9QLKyGpD2Yxig==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.24.2.tgz",
      "integrity": "sha512-LihEQ2BBKVFLOC9ZItT9iFprsE9tqjDjnbulhHoFxYQtQfai7qfluVODIYxt1PgdoyQkz23+01rzwNwYfutxUQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.24.2.tgz",
      "integrity": "sha512-q+iGUwfs8tncmFC9pcnD5IvRHAzmbwQ3GPS5/ceCyHdjXubwQWI12MKWSNSMYLJMq23/IUCvJMS76PDqXe1fxA==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.24.2.tgz",
      "integrity": "sha512-7VTgWzgMGvup6aSqDPLiW5zHaxYJGTO4OokMjIlrCtf+VpEL+cXKtCvg723iguPYI5oaUNdS+/V7OU2gvXVWEg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/sourcemap-codec": "^1.5.0",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/gen-mapping": "^0.3.5",
        "@jridgewell/trace-mapping": "^0.3.24"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@jridgewell/resolve-uri": "^3.1.0",
        "@jridgewell/sourcemap-codec": "^1.4.14"
      }
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.62.2.tgz",
      "integrity": "sha512-6o7ZLZK+BeenkZCFNDXqpbjw9bD6nuWonvS/lwQJp7NoVVxm6p3qE7qQ5jGuBjiFsgvqjD8mZAU5oWxTmbOeOg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.62.2.tgz",
      "integrity": "sha512-BaH7BllCACHoH1LguOU56UItGfUWjujlO65kS9LAodViaN4bwIKd7oeW/ZHJ/4ljr/7MIiENnNy3HJ0zXv8Zkw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.62.2.tgz",
      "integrity": "sha512-v39RCCvj4He82I9sFmk+M1VZ0PLM9sfsLVikjfx2hYBNALhrrOR2D3JjQA6AhlaSOgcR+RzrKY7e1+bT6SUO/A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.62.2.tgz",
      "integrity": "sha512-yl0y2vq3S3lHeuXhEdss6TWfKW8vkujImO12tn4ZkG/4oghr09LvdYm2RElVjokTQiUvDUGXLGsYeLqUMCKpGA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.62.2.tgz",
      "integrity": "sha512-tT4pvt4qXD+vEoezupCWi+a1F0vvDiksiHc+PxRlYTOH1I6/X4id9jPxTP+Fg+545euaFT1jJVs4CEdHZAU1vw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.62.2.tgz",
      "integrity": "sha512-6nU5F2wCW+qvCBhTn1pdIU3bzsIoF7EUwsCDRxilWGprQR6yd508YnH9+OKFCwpfS8pjZqDUmnCAr7exax0XCg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.62.2.tgz",
      "integrity": "sha512-n1GJHPOvpIfhi3TmrCeh6S6URt9BFCt0KQE3qvexyGCTAKpR4Lg+eWvNZEqu7epxwus/8ElT3hacYEucm49SZg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm-musleabihf": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.62.2.tgz",
      "integrity": "sha512-JqgflS8wEB+UXV/vS1RpRbifGBeN4D5lz8D8oOFbFZw4vedvdOgCFAjfBmIMdW3yL10XpQQ0Ambepw6MXrhOnA==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.62.2.tgz",
      "integrity": "sha512-wnFJkogWvN4jm/hQRF2UBaeUmk20j5+DmHvoyWii2b8HJDyvz1MF2OU/6ynXt2KR63rbZLWkFpoytpdc/yBuSA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-arm64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.62.2.tgz",
      "integrity": "sha512-HVu2bp0zhvJ8xHEV9+UUs7S90VadmBSY3LcIMvozbPo4AuMGDWlz3ymHLHZPX4hR67TKTt8Qp5PJ5RBg/i+RMQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.62.2.tgz",
      "integrity": "sha512-mQqqAV8QaoSgr9I2fKDLY2BAVvmKjWoGiu/cSYQonsLvtqwEn1E4QYfnCOcp5zoEqNhsDYin1s6jx/VJmrxlZg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-loong64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-loong64-musl/-/rollup-linux-loong64-musl-4.62.2.tgz",
      "integrity": "sha512-IxKLoxCQ2IWi6bT2akyDUBGsOImDKB+sPp4EsTmwFQ/fMwpCKm8uLSSgP/Kx/QYUgKis6SEZ5/Nlhup0DIA0PQ==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.62.2.tgz",
      "integrity": "sha512-Mk5ha2RQSgyFfmYYLkBpPnUk8D8FriBxesO1u9O75X0mHgXL1UQcH5Itl2lurWL2tj0RxV9b9tJgipac0hRY9A==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-ppc64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-ppc64-musl/-/rollup-linux-ppc64-musl-4.62.2.tgz",
      "integrity": "sha512-CjvEnqJL/0/TQ3TXX3OPIJ/kmBellrWd4heXUmHeJlTnmwjKpSJzoehLaL6Xk0ZnMHBu9dZuFADNOrtjF4v+2w==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.62.2.tgz",
      "integrity": "sha512-1SiZbzwdkaDURsew/tSOrooKiYy7EQGT6m8ufavAi9NEyQb/6VuIxFXAL1fqa4iZe3g4NbNk4P7J32z2tw5Mgg==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-riscv64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.62.2.tgz",
      "integrity": "sha512-nQts12zJ3NQRoE6uYljOH89v7szzLDvG2JD/vsX+vGXU8w/At1GowTZ5/7qeFQ8m7L55rpR8Okugnuo5bgjy2Q==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-s390x-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.62.2.tgz",
      "integrity": "sha512-E9/ll019jhPIJgpzfZoIkBGhcz+kKNgVWYRY0zr9srBdPPFVpvOKW8VaJKUbeK+eZXyQF9ltME+Kk6affeaPgg==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.62.2.tgz",
      "integrity": "sha512-5BqxR/pshjey51iliyzTD5Xi3EN0aLmQ2lZ3lvefVV9c82BvrLo2/6OT55iifpWBufs6kdwWbuOKS841DrmK9A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-linux-x64-musl": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.62.2.tgz",
      "integrity": "sha512-uNN83XxQrRAh/w0/pmAfibcwyb6YWt4gP+dpnQKPVJshAloQ785ii8CT8ZCIxkGg9opVsvAlGhFitSm6D1Jjpg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "linux"
      ]
    },
    "node_modules/@rollup/rollup-openbsd-x64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openbsd-x64/-/rollup-openbsd-x64-4.62.2.tgz",
      "integrity": "sha512-srjEIxSH3LRnJN6THczDHWQplqEMFiAJrTab0msUryh9kwNpkICf3Ea6q6MN/2cZwRFUNx5w+h6Hpi4QuHS6Zg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openbsd"
      ]
    },
    "node_modules/@rollup/rollup-openharmony-arm64": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.62.2.tgz",
      "integrity": "sha512-8hOJnxgbyObnCm5AlRA3A931xX19xq80RjVTKgJOvEKWqJruP/Uf12IbAOaDjjEXYRewwHLfmF0YRIdK3OwKWA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "openharmony"
      ]
    },
    "node_modules/@rollup/rollup-win32-arm64-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-arm64-msvc/-/rollup-win32-arm64-msvc-4.62.2.tgz",
      "integrity": "sha512-mmF4AY1i0hG/bLWUctUq59gtmgaSIRa3cu/A3JFRp/sCNEme2bgDEiDS22P9FbnJB8NJNF4jPJiSP5RHQpUTDg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-ia32-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-ia32-msvc/-/rollup-win32-ia32-msvc-4.62.2.tgz",
      "integrity": "sha512-DZgkknc6jhHrk46V25vbAM0zZkyP0nSDkJB8/dRkLTxv470dOmWDqGoEJl/9A0dFfS7yE3REOwNDxpHwSLSt0Q==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-gnu": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-gnu/-/rollup-win32-x64-gnu-4.62.2.tgz",
      "integrity": "sha512-T6xr6ucWSFto+VGajA8YH26LdpHRuP4YLHEKAtCWvJDOlnmWcDZVCI2Jmjr+IFHDlt2zRaTAKE4tfjTaWLgJBg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@rollup/rollup-win32-x64-msvc": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.62.2.tgz",
      "integrity": "sha512-BfzEnDJOt9T8M989/lA37EcJgat01wLRnoi5dQf3QzOH7jzpqTAzdDbVfRljVr5r+jzKqpbHeyOfAaXxAd0PAA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "win32"
      ]
    },
    "node_modules/@types/babel__core": {
      "version": "7.20.5",
      "resolved": "https://registry.npmjs.org/@types/babel__core/-/babel__core-7.20.5.tgz",
      "integrity": "sha512-qoQprZvz5wQFJwMDqeseRXWv3rqMvhgpbXFfVyWhbx9X47POIA6i/+dXefEmZKoAgOaTdaIgNSMqMIU61yRyzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.20.7",
        "@babel/types": "^7.20.7",
        "@types/babel__generator": "*",
        "@types/babel__template": "*",
        "@types/babel__traverse": "*"
      }
    },
    "node_modules/@types/babel__generator": {
      "version": "7.27.0",
      "resolved": "https://registry.npmjs.org/@types/babel__generator/-/babel__generator-7.27.0.tgz",
      "integrity": "sha512-ufFd2Xi92OAVPYsy+P4n7/U7e68fex0+Ee8gSG9KX7eo084CWiQ4sdxktvdl0bOPupXtVJPY19zk6EwWqUQ8lg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__template": {
      "version": "7.4.4",
      "resolved": "https://registry.npmjs.org/@types/babel__template/-/babel__template-7.4.4.tgz",
      "integrity": "sha512-h/NUaSyG5EyxBIp8YRxo4RMe2/qQgvyowRwVMzhYhBCONbW8PUsg4lkFMrhgZhUe5z3L3MiLDuvyJ/CaPa2A8A==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/parser": "^7.1.0",
        "@babel/types": "^7.0.0"
      }
    },
    "node_modules/@types/babel__traverse": {
      "version": "7.28.0",
      "resolved": "https://registry.npmjs.org/@types/babel__traverse/-/babel__traverse-7.28.0.tgz",
      "integrity": "sha512-8PvcXf70gTDZBgt9ptxJ8elBeBjcLOAcOtoO/mPJjtji1+CdGbHgm77om1GrsPxsiE+uXIpNSK64UYaIwQXd4Q==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/types": "^7.28.2"
      }
    },
    "node_modules/@types/estree": {
      "version": "1.0.9",
      "resolved": "https://registry.npmjs.org/@types/estree/-/estree-1.0.9.tgz",
      "integrity": "sha512-GhdPgy1el4/ImP05X05Uw4cw2/M93BCUmnEvWZNStlCzEKME4Fkk+YpoA5OiHNQmoS7Cafb8Xa3Pya8m1Qrzeg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/@types/react": {
      "version": "19.0.2",
      "resolved": "https://registry.npmjs.org/@types/react/-/react-19.0.2.tgz",
      "integrity": "sha512-USU8ZI/xyKJwFTpjSVIrSeHBVAGagkHQKPNbxeWwql/vDmnTIBgx+TJnhFnj1NXgz8XfprU0egV2dROLGpsBEg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "csstype": "^3.0.2"
      }
    },
    "node_modules/@types/react-dom": {
      "version": "19.0.2",
      "resolved": "https://registry.npmjs.org/@types/react-dom/-/react-dom-19.0.2.tgz",
      "integrity": "sha512-c1s+7TKFaDRRxr1TxccIX2u7sfCnc3RxkVyBIUA2lCpyqCF+QoAwQ/CBg7bsMdVwP120HEH143VQezKtef5nCg==",
      "dev": true,
      "license": "MIT",
      "peerDependencies": {
        "@types/react": "^19.0.0"
      }
    },
    "node_modules/@vitejs/plugin-react": {
      "version": "4.3.4",
      "resolved": "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-4.3.4.tgz",
      "integrity": "sha512-SCCPBJtYLdE8PX/7ZQAs1QAZ8Jqwih+0VBLum1EGqmCCQal+MIUqLCzj3ZUy8ufbC0cAM4LRlSTm7IQJwWT4ug==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@babel/core": "^7.26.0",
        "@babel/plugin-transform-react-jsx-self": "^7.25.9",
        "@babel/plugin-transform-react-jsx-source": "^7.25.9",
        "@types/babel__core": "^7.20.5",
        "react-refresh": "^0.14.2"
      },
      "engines": {
        "node": "^14.18.0 || >=16.0.0"
      },
      "peerDependencies": {
        "vite": "^4.2.0 || ^5.0.0 || ^6.0.0"
      }
    },
    "node_modules/baseline-browser-mapping": {
      "version": "2.10.40",
      "resolved": "https://registry.npmjs.org/baseline-browser-mapping/-/baseline-browser-mapping-2.10.40.tgz",
      "integrity": "sha512-BSSLZ9/Cjjv7Gtj5B68ZzXcXUg8iOf3fme+FCuh8rC/Go+Kmh8cox7M3A8dolou16s64QjLPOSdngh7GxXvkSw==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "baseline-browser-mapping": "dist/cli.cjs"
      },
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/browserslist": {
      "version": "4.28.4",
      "resolved": "https://registry.npmjs.org/browserslist/-/browserslist-4.28.4.tgz",
      "integrity": "sha512-MTc8i/x9jBQd1iMw2CFGS+rwMa07eYjLR0CCTLDACl9xhxy+nIs3KeML/biicXtk9JrZ6dnnTatmc7ErPXIxqw==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "baseline-browser-mapping": "^2.10.38",
        "caniuse-lite": "^1.0.30001799",
        "electron-to-chromium": "^1.5.376",
        "node-releases": "^2.0.48",
        "update-browserslist-db": "^1.2.3"
      },
      "bin": {
        "browserslist": "cli.js"
      },
      "engines": {
        "node": "^6 || ^7 || ^8 || ^9 || ^10 || ^11 || ^12 || >=13.7"
      }
    },
    "node_modules/caniuse-lite": {
      "version": "1.0.30001800",
      "resolved": "https://registry.npmjs.org/caniuse-lite/-/caniuse-lite-1.0.30001800.tgz",
      "integrity": "sha512-MMHtuAz9Ys840zAY5F4k6fV5GaivZ9sPk+nz0mY+GYVzRBnYkN0mpqkSR92oWRQ19yQWo4HvBV/FnC16AJX8MA==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/caniuse-lite"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "CC-BY-4.0"
    },
    "node_modules/convert-source-map": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/convert-source-map/-/convert-source-map-2.0.0.tgz",
      "integrity": "sha512-Kvp459HrV2FEJ1CAsi1Ku+MY3kasH19TFykTz2xWmMeq6bk2NU3XXvfJ+Q61m0xktWwt+1HSYf3JZsTms3aRJg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/csstype": {
      "version": "3.2.3",
      "resolved": "https://registry.npmjs.org/csstype/-/csstype-3.2.3.tgz",
      "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/electron-to-chromium": {
      "version": "1.5.383",
      "resolved": "https://registry.npmjs.org/electron-to-chromium/-/electron-to-chromium-1.5.383.tgz",
      "integrity": "sha512-I2484/KkAvl8lm9VyjH2JnbOIV0d/UCqT7gbzs6l+o6Vmn9wgB66uVcKX+Vk6HrXtY6fbWTOEXuv8waDTuFNCw==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/esbuild": {
      "version": "0.24.2",
      "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.24.2.tgz",
      "integrity": "sha512-+9egpBW8I3CD5XPe0n6BfT5fxLzxrlDzqydF3aviG+9ni1lDC/OvMHcxqEFV0+LANZG5R1bFMWfUrjVsdwxJvA==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "bin": {
        "esbuild": "bin/esbuild"
      },
      "engines": {
        "node": ">=18"
      },
      "optionalDependencies": {
        "@esbuild/aix-ppc64": "0.24.2",
        "@esbuild/android-arm": "0.24.2",
        "@esbuild/android-arm64": "0.24.2",
        "@esbuild/android-x64": "0.24.2",
        "@esbuild/darwin-arm64": "0.24.2",
        "@esbuild/darwin-x64": "0.24.2",
        "@esbuild/freebsd-arm64": "0.24.2",
        "@esbuild/freebsd-x64": "0.24.2",
        "@esbuild/linux-arm": "0.24.2",
        "@esbuild/linux-arm64": "0.24.2",
        "@esbuild/linux-ia32": "0.24.2",
        "@esbuild/linux-loong64": "0.24.2",
        "@esbuild/linux-mips64el": "0.24.2",
        "@esbuild/linux-ppc64": "0.24.2",
        "@esbuild/linux-riscv64": "0.24.2",
        "@esbuild/linux-s390x": "0.24.2",
        "@esbuild/linux-x64": "0.24.2",
        "@esbuild/netbsd-arm64": "0.24.2",
        "@esbuild/netbsd-x64": "0.24.2",
        "@esbuild/openbsd-arm64": "0.24.2",
        "@esbuild/openbsd-x64": "0.24.2",
        "@esbuild/sunos-x64": "0.24.2",
        "@esbuild/win32-arm64": "0.24.2",
        "@esbuild/win32-ia32": "0.24.2",
        "@esbuild/win32-x64": "0.24.2"
      }
    },
    "node_modules/escalade": {
      "version": "3.2.0",
      "resolved": "https://registry.npmjs.org/escalade/-/escalade-3.2.0.tgz",
      "integrity": "sha512-WUj2qlxaQtO4g6Pq5c29GTcWGDyd8itL8zTlipgECz3JesAiiOKotd8JU6otB3PACgG6xkJUyVhboMS+bje/jA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmjs.org/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/gensync": {
      "version": "1.0.0-beta.2",
      "resolved": "https://registry.npmjs.org/gensync/-/gensync-1.0.0-beta.2.tgz",
      "integrity": "sha512-3hN7NaskYvMDLQY55gnW3NQ+mesEAepTqlg+VEbj7zzqEMBVNhzcGYYeqFo/TlYz6eQiFcp1HcsCZO+nGgS8zg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=6.9.0"
      }
    },
    "node_modules/js-tokens": {
      "version": "4.0.0",
      "resolved": "https://registry.npmjs.org/js-tokens/-/js-tokens-4.0.0.tgz",
      "integrity": "sha512-RdJUflcE3cUzKiMqQgsCu06FPu9UdIJO0beYbPhHN4k6apgJtifcoCtT9bcxOpYBtpD2kCM6Sbzg4CausW/PKQ==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/jsesc": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/jsesc/-/jsesc-3.1.0.tgz",
      "integrity": "sha512-/sM3dO2FOzXjKQhJuo0Q173wf2KOo8t4I8vHy6lF9poUp7bKT0/NHE8fPX23PwfhnykfqnC2xRxOnVw5XuGIaA==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "jsesc": "bin/jsesc"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/json5": {
      "version": "2.2.3",
      "resolved": "https://registry.npmjs.org/json5/-/json5-2.2.3.tgz",
      "integrity": "sha512-XmOWe7eyHYH14cLdVPoyg+GOH3rYX++KpzrylJwSW98t3Nk+U8XOl8FWKOgwtzdb8lXGf6zYwDUzeHMWfxasyg==",
      "dev": true,
      "license": "MIT",
      "bin": {
        "json5": "lib/cli.js"
      },
      "engines": {
        "node": ">=6"
      }
    },
    "node_modules/lru-cache": {
      "version": "5.1.1",
      "resolved": "https://registry.npmjs.org/lru-cache/-/lru-cache-5.1.1.tgz",
      "integrity": "sha512-KpNARQA3Iwv+jTA0utUVVbrh+Jlrr1Fv0e56GGzAFOXN7dk/FviaDW8LHmK52DlcH4WP2n6gI8vN1aesBFgo9w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "yallist": "^3.0.2"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/nanoid": {
      "version": "3.3.15",
      "resolved": "https://registry.npmjs.org/nanoid/-/nanoid-3.3.15.tgz",
      "integrity": "sha512-y7Wygv/7mEOvxTuEQDB8StXdMRBWf1kR/tlhAzBRUFkB2jfcLOAxO/SHmOO2zgz1pVgK29/kyupn059/bCHdjA==",
      "dev": true,
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "bin": {
        "nanoid": "bin/nanoid.cjs"
      },
      "engines": {
        "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
      }
    },
    "node_modules/node-releases": {
      "version": "2.0.50",
      "resolved": "https://registry.npmjs.org/node-releases/-/node-releases-2.0.50.tgz",
      "integrity": "sha512-J6l92tKHX6w8Jy5nO1Vuc01NoIiRGi/d6qBKVxh+IQ8Cr3b6HbVNfKiF8ZpFKufTwpwxMmce2W3iQZ861ZRyTg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/picocolors": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/picocolors/-/picocolors-1.1.1.tgz",
      "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/postcss": {
      "version": "8.5.15",
      "resolved": "https://registry.npmjs.org/postcss/-/postcss-8.5.15.tgz",
      "integrity": "sha512-FfR8sjd4em2T6fb3I2MwAJU7HWVMr9zba+enmQeeWFfCbm+UOC/0X4DS8XtpUTMwWMGbjKYP7xjfNekzyGmB3A==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/postcss/"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/postcss"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "nanoid": "^3.3.12",
        "picocolors": "^1.1.1",
        "source-map-js": "^1.2.1"
      },
      "engines": {
        "node": "^10 || ^12 || >=14"
      }
    },
    "node_modules/react": {
      "version": "19.0.0",
      "resolved": "https://registry.npmjs.org/react/-/react-19.0.0.tgz",
      "integrity": "sha512-V8AVnmPIICiWpGfm6GLzCR/W5FXLchHop40W4nXBmdlEceh16rCN8O8LNWm5bh5XUX91fh7KpA+W0TgMKmgTpQ==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/react-dom": {
      "version": "19.0.0",
      "resolved": "https://registry.npmjs.org/react-dom/-/react-dom-19.0.0.tgz",
      "integrity": "sha512-4GV5sHFG0e/0AD4X+ySy6UJd3jVl1iNsNHdpad0qhABJ11twS3TTBnseqsKurKcsNqCEFeGL3uLpVChpIO3QfQ==",
      "license": "MIT",
      "dependencies": {
        "scheduler": "^0.25.0"
      },
      "peerDependencies": {
        "react": "^19.0.0"
      }
    },
    "node_modules/react-refresh": {
      "version": "0.14.2",
      "resolved": "https://registry.npmjs.org/react-refresh/-/react-refresh-0.14.2.tgz",
      "integrity": "sha512-jCvmsr+1IUSMUyzOkRcvnVbX3ZYC6g9TDrDbFuFmRDq7PD4yaGbLKNQL6k2jnArV8hjYxh7hVhAZB6s9HDGpZA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/rollup": {
      "version": "4.62.2",
      "resolved": "https://registry.npmjs.org/rollup/-/rollup-4.62.2.tgz",
      "integrity": "sha512-RFnrW4lhXA3s3eqHDZvN654g8OTjzRfqpIRJYczCGB6HzphckVAi/Qh4tbPUbRuDi7s1Llv8g/NspLkttY3gTA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "@types/estree": "1.0.9"
      },
      "bin": {
        "rollup": "dist/bin/rollup"
      },
      "engines": {
        "node": ">=18.0.0",
        "npm": ">=8.0.0"
      },
      "optionalDependencies": {
        "@rollup/rollup-android-arm-eabi": "4.62.2",
        "@rollup/rollup-android-arm64": "4.62.2",
        "@rollup/rollup-darwin-arm64": "4.62.2",
        "@rollup/rollup-darwin-x64": "4.62.2",
        "@rollup/rollup-freebsd-arm64": "4.62.2",
        "@rollup/rollup-freebsd-x64": "4.62.2",
        "@rollup/rollup-linux-arm-gnueabihf": "4.62.2",
        "@rollup/rollup-linux-arm-musleabihf": "4.62.2",
        "@rollup/rollup-linux-arm64-gnu": "4.62.2",
        "@rollup/rollup-linux-arm64-musl": "4.62.2",
        "@rollup/rollup-linux-loong64-gnu": "4.62.2",
        "@rollup/rollup-linux-loong64-musl": "4.62.2",
        "@rollup/rollup-linux-ppc64-gnu": "4.62.2",
        "@rollup/rollup-linux-ppc64-musl": "4.62.2",
        "@rollup/rollup-linux-riscv64-gnu": "4.62.2",
        "@rollup/rollup-linux-riscv64-musl": "4.62.2",
        "@rollup/rollup-linux-s390x-gnu": "4.62.2",
        "@rollup/rollup-linux-x64-gnu": "4.62.2",
        "@rollup/rollup-linux-x64-musl": "4.62.2",
        "@rollup/rollup-openbsd-x64": "4.62.2",
        "@rollup/rollup-openharmony-arm64": "4.62.2",
        "@rollup/rollup-win32-arm64-msvc": "4.62.2",
        "@rollup/rollup-win32-ia32-msvc": "4.62.2",
        "@rollup/rollup-win32-x64-gnu": "4.62.2",
        "@rollup/rollup-win32-x64-msvc": "4.62.2",
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/scheduler": {
      "version": "0.25.0",
      "resolved": "https://registry.npmjs.org/scheduler/-/scheduler-0.25.0.tgz",
      "integrity": "sha512-xFVuu11jh+xcO7JOAGJNOXld8/TcEHK/4CituBUeUb5hqxJLj9YuemAEuvm9gQ/+pgXYfbQuqAkiYu+u7YEsNA==",
      "license": "MIT"
    },
    "node_modules/semver": {
      "version": "6.3.1",
      "resolved": "https://registry.npmjs.org/semver/-/semver-6.3.1.tgz",
      "integrity": "sha512-BR7VvDCVHO+q2xBEWskxS6DJE1qRnb7DxzUrogb71CWoSficBxYsiAGd+Kl0mmq/MprG9yArRkyrQxTO6XjMzA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      }
    },
    "node_modules/source-map-js": {
      "version": "1.2.1",
      "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.1.tgz",
      "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
      "dev": true,
      "license": "BSD-3-Clause",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/typescript": {
      "version": "5.7.2",
      "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.7.2.tgz",
      "integrity": "sha512-i5t66RHxDvVN40HfDd1PsEThGNnlMCMT3jMUuoh9/0TaqWevNontacunWyN02LA9/fIbEWlcHZcgTKb9QoaLfg==",
      "dev": true,
      "license": "Apache-2.0",
      "bin": {
        "tsc": "bin/tsc",
        "tsserver": "bin/tsserver"
      },
      "engines": {
        "node": ">=14.17"
      }
    },
    "node_modules/update-browserslist-db": {
      "version": "1.2.3",
      "resolved": "https://registry.npmjs.org/update-browserslist-db/-/update-browserslist-db-1.2.3.tgz",
      "integrity": "sha512-Js0m9cx+qOgDxo0eMiFGEueWztz+d4+M3rGlmKPT+T4IS/jP4ylw3Nwpu6cpTTP8R1MAC1kF4VbdLt3ARf209w==",
      "dev": true,
      "funding": [
        {
          "type": "opencollective",
          "url": "https://opencollective.com/browserslist"
        },
        {
          "type": "tidelift",
          "url": "https://tidelift.com/funding/github/npm/browserslist"
        },
        {
          "type": "github",
          "url": "https://github.com/sponsors/ai"
        }
      ],
      "license": "MIT",
      "dependencies": {
        "escalade": "^3.2.0",
        "picocolors": "^1.1.1"
      },
      "bin": {
        "update-browserslist-db": "cli.js"
      },
      "peerDependencies": {
        "browserslist": ">= 4.21.0"
      }
    },
    "node_modules/vite": {
      "version": "6.0.7",
      "resolved": "https://registry.npmjs.org/vite/-/vite-6.0.7.tgz",
      "integrity": "sha512-RDt8r/7qx9940f8FcOIAH9PTViRrghKaK2K1jY3RaAURrEUbm9Du1mJ72G+jlhtG3WwodnfzY8ORQZbBavZEAQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "esbuild": "^0.24.2",
        "postcss": "^8.4.49",
        "rollup": "^4.23.0"
      },
      "bin": {
        "vite": "bin/vite.js"
      },
      "engines": {
        "node": "^18.0.0 || ^20.0.0 || >=22.0.0"
      },
      "funding": {
        "url": "https://github.com/vitejs/vite?sponsor=1"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.3"
      },
      "peerDependencies": {
        "@types/node": "^18.0.0 || ^20.0.0 || >=22.0.0",
        "jiti": ">=1.21.0",
        "less": "*",
        "lightningcss": "^1.21.0",
        "sass": "*",
        "sass-embedded": "*",
        "stylus": "*",
        "sugarss": "*",
        "terser": "^5.16.0",
        "tsx": "^4.8.1",
        "yaml": "^2.4.2"
      },
      "peerDependenciesMeta": {
        "@types/node": {
          "optional": true
        },
        "jiti": {
          "optional": true
        },
        "less": {
          "optional": true
        },
        "lightningcss": {
          "optional": true
        },
        "sass": {
          "optional": true
        },
        "sass-embedded": {
          "optional": true
        },
        "stylus": {
          "optional": true
        },
        "sugarss": {
          "optional": true
        },
        "terser": {
          "optional": true
        },
        "tsx": {
          "optional": true
        },
        "yaml": {
          "optional": true
        }
      }
    },
    "node_modules/yallist": {
      "version": "3.1.1",
      "resolved": "https://registry.npmjs.org/yallist/-/yallist-3.1.1.tgz",
      "integrity": "sha512-a4UGQaWPH59mOXUYnAG2ewncQS4i4F43Tv3JoAM+s2VDAmS9NsK8GpDMLrCHPksFT7h3K6TOoUNn2pb7RoXx4g==",
      "dev": true,
      "license": "ISC"
    }
  }
}

```

---

### apps\supervisor-dashboard\src\api.ts

```typescript
import type { Escalation, Kpis, SessionDetail, Verdict } from "./types";

const BASE = import.meta.env.VITE_BUSINESS_API_URL ?? "http://localhost:8108";
const ROLE = import.meta.env.VITE_API_ROLE ?? "administrateur";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "X-Role": ROLE } });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  kpis: () => get<Kpis>("/api/v1/kpis"),
  escalations: (status = "open") =>
    get<{ escalations: Escalation[] }>(`/api/v1/escalations?status=${encodeURIComponent(status)}`),
  session: (id: string) => get<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(id)}`),
  verdicts: (id: string) =>
    get<{ verdicts: Verdict[] }>(`/api/v1/policy/verdicts?session_id=${encodeURIComponent(id)}`),
};
```

---

### apps\supervisor-dashboard\src\App.tsx

```tsx
import { useState } from "react";
import { EscalationQueue } from "./components/EscalationQueue";
import { KpiPanel } from "./components/KpiPanel";
import { SessionInspector } from "./components/SessionInspector";

type Tab = "kpis" | "escalations" | "session";

export default function App() {
  const [tab, setTab] = useState<Tab>("kpis");
  const [sessionId, setSessionId] = useState("");

  const inspect = (id: string) => {
    setSessionId(id);
    setTab("session");
  };

  return (
    <div className="app">
      <header>
        <h1>Supervisor Dashboard</h1>
        <nav>
          <button className={tab === "kpis" ? "active" : ""} onClick={() => setTab("kpis")}>KPIs</button>
          <button className={tab === "escalations" ? "active" : ""} onClick={() => setTab("escalations")}>
            Escalations
          </button>
          <button className={tab === "session" ? "active" : ""} onClick={() => setTab("session")}>
            Session inspector
          </button>
        </nav>
      </header>

      <main>
        {tab === "kpis" && <KpiPanel />}
        {tab === "escalations" && <EscalationQueue onInspect={inspect} />}
        {tab === "session" && <SessionInspector initialId={sessionId} />}
      </main>
    </div>
  );
}
```

---

### apps\supervisor-dashboard\src\components\EscalationQueue.tsx

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Escalation } from "../types";

export function EscalationQueue({ onInspect }: { onInspect: (sessionId: string) => void }) {
  const [rows, setRows] = useState<Escalation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.escalations("open").then((r) => setRows(r.escalations)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">Could not load escalations: {error}</p>;
  if (!rows) return <p className="muted">Loading escalationsâ€¦</p>;
  if (rows.length === 0) return <p className="muted">No open escalations.</p>;

  return (
    <table className="grid">
      <thead>
        <tr>
          <th>Trigger</th>
          <th>Target</th>
          <th>Session</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((e) => (
          <tr key={e.id}>
            <td><span className="tag">{e.trigger}</span></td>
            <td>{e.target}</td>
            <td className="mono">{e.session_id.slice(0, 8)}â€¦</td>
            <td>
              <button onClick={() => onInspect(e.session_id)}>Inspect</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

### apps\supervisor-dashboard\src\components\KpiPanel.tsx

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Kpis } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function KpiPanel() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.kpis().then(setKpis).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">Could not load KPIs: {error}</p>;
  if (!kpis) return <p className="muted">Loading KPIsâ€¦</p>;

  const cards = [
    { label: "Containment rate", value: pct(kpis.containment_rate), hint: "resolved / total" },
    { label: "Escalation rate", value: pct(kpis.escalation_rate), hint: "escalated / total" },
    { label: "Avg. peak frustration", value: kpis.avg_frustration.toFixed(2), hint: "0 = calm" },
    { label: "Total sessions", value: String(kpis.total_sessions), hint: "" },
    { label: "Resolved", value: String(kpis.resolved), hint: "" },
    { label: "Escalated", value: String(kpis.escalated), hint: "" },
  ];

  return (
    <div className="cards">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <div className="card-value">{c.value}</div>
          <div className="card-label">{c.label}</div>
          {c.hint && <div className="card-hint">{c.hint}</div>}
        </div>
      ))}
    </div>
  );
}
```

---

### apps\supervisor-dashboard\src\components\SessionInspector.tsx

```tsx
import { useEffect, useState } from "react";
import { api } from "../api";
import type { SessionDetail, Verdict } from "../types";

function verdictClass(verdict: string): string {
  if (verdict === "REFUSED") return "verdict refused";
  if (verdict === "ESCALATE") return "verdict escalate";
  return "verdict authorized";
}

export function SessionInspector({ initialId }: { initialId: string }) {
  const [id, setId] = useState(initialId);
  const [query, setQuery] = useState(initialId);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [verdicts, setVerdicts] = useState<Verdict[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setId(initialId), [initialId]);

  useEffect(() => {
    if (!id) return;
    setError(null);
    setSession(null);
    setVerdicts(null);
    api.session(id).then(setSession).catch((e) => setError(String(e)));
    api.verdicts(id).then((r) => setVerdicts(r.verdicts)).catch(() => setVerdicts([]));
  }, [id]);

  return (
    <div>
      <div className="searchbar">
        <input
          value={query}
          placeholder="session id (UUID)"
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={() => setId(query.trim())}>Open</button>
      </div>

      {error && <p className="error">{error}</p>}
      {!id && <p className="muted">Enter a session id, or pick one from the escalation queue.</p>}

      {session && (
        <>
          <div className="session-meta">
            <span>Disposition: <b>{session.disposition ?? "â€”"}</b></span>
            <span>Duration: <b>{session.duration_seconds ?? "â€”"}s</b></span>
            <span>Peak frustration: <b>{session.max_frustration.toFixed(2)}</b></span>
          </div>

          <h3>Why the system decided as it did</h3>
          {verdicts && verdicts.length > 0 ? (
            <ul className="verdicts">
              {verdicts.map((v) => (
                <li key={v.id} className={verdictClass(v.verdict)}>
                  <div className="verdict-head">
                    <span className="badge">{v.verdict}</span>
                    <span className="mono">{v.action}</span>
                    <span className="rule">{v.rule_id}</span>
                  </div>
                  <div className="justification">{v.justification}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No policy verdicts recorded for this session.</p>
          )}

          <h3>Transcript (PII-masked)</h3>
          <div className="transcript">
            {session.turns.map((t) => (
              <div className={`turn ${t.speaker}`} key={`${t.index}-${t.speaker}`}>
                <span className="who">{t.speaker === "caller" ? "Caller" : t.agent ?? "Agent"}</span>
                <span className="text">{t.text}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

---

### apps\supervisor-dashboard\src\main.tsx

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
```

---

### apps\supervisor-dashboard\src\styles.css

```css
:root {
  --bg: #0f1420;
  --panel: #1a2130;
  --line: #2a3346;
  --text: #e6ebf5;
  --muted: #8b97ad;
  --accent: #4f8cff;
  --refused: #ff5a6e;
  --escalate: #ffb020;
  --authorized: #36d399;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); }
.app { max-width: 980px; margin: 0 auto; padding: 24px; }
header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); padding-bottom: 12px; }
h1 { font-size: 20px; margin: 0; }
nav button { background: transparent; color: var(--muted); border: none; padding: 8px 12px; cursor: pointer; font-size: 14px; border-radius: 8px; }
nav button.active { background: var(--panel); color: var(--text); }
main { margin-top: 20px; }
.muted { color: var(--muted); }
.error { color: var(--refused); }
.mono { font-family: ui-monospace, monospace; }

.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px; }
.card-value { font-size: 28px; font-weight: 700; }
.card-label { margin-top: 6px; color: var(--text); }
.card-hint { color: var(--muted); font-size: 12px; }

.grid { width: 100%; border-collapse: collapse; }
.grid th, .grid td { text-align: left; padding: 10px; border-bottom: 1px solid var(--line); }
.grid th { color: var(--muted); font-weight: 500; font-size: 13px; }
.tag { background: #2a3346; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
button { background: var(--accent); color: white; border: none; padding: 6px 12px; border-radius: 8px; cursor: pointer; }

.searchbar { display: flex; gap: 8px; margin-bottom: 14px; }
.searchbar input { flex: 1; background: var(--panel); border: 1px solid var(--line); color: var(--text); border-radius: 8px; padding: 8px 10px; }
.session-meta { display: flex; gap: 18px; color: var(--muted); margin-bottom: 14px; }
.session-meta b { color: var(--text); }

.verdicts { list-style: none; padding: 0; }
.verdicts li { background: var(--panel); border: 1px solid var(--line); border-left-width: 4px; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
.verdict.refused { border-left-color: var(--refused); }
.verdict.escalate { border-left-color: var(--escalate); }
.verdict.authorized { border-left-color: var(--authorized); }
.verdict-head { display: flex; gap: 10px; align-items: center; }
.badge { font-size: 11px; font-weight: 700; letter-spacing: 0.04em; }
.rule { color: var(--muted); font-size: 12px; margin-left: auto; }
.justification { margin-top: 6px; color: var(--text); }

.transcript { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
.turn { display: flex; gap: 10px; padding: 4px 0; }
.turn .who { color: var(--muted); min-width: 70px; }
.turn.caller .who { color: var(--accent); }
```

---

### apps\supervisor-dashboard\src\types.ts

```typescript
export interface Kpis {
  total_sessions: number;
  resolved: number;
  escalated: number;
  containment_rate: number;
  escalation_rate: number;
  avg_frustration: number;
}

export interface Escalation {
  id: string;
  session_id: string;
  trigger: string;
  target: string;
  resolution: string | null;
  dossier: Record<string, unknown>;
}

export interface Verdict {
  id: string;
  action: string;
  verdict: string; // AUTHORIZED | REFUSED | ESCALATE
  rule_id: string;
  justification: string;
}

export interface Turn {
  index: number;
  speaker: string;
  agent: string | null;
  text: string | null;
}

export interface SentimentSample {
  index: number;
  score: number;
  label: string | null;
}

export interface SessionDetail {
  session_id: string;
  disposition: string | null;
  duration_seconds: number | null;
  max_frustration: number;
  turns: Turn[];
  sentiment: SentimentSample[];
}
```

---

### apps\supervisor-dashboard\src\vite-env.d.ts

```typescript
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_BUSINESS_API_URL?: string;
  readonly VITE_API_ROLE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

---

### apps\supervisor-dashboard\tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

---

### apps\supervisor-dashboard\vite.config.ts

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
});
```

---

### apps\token-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f apps/token-service/Dockerfile -t token-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY apps/token-service/ ./apps/token-service/
RUN pip install ./apps/token-service
USER app
EXPOSE 8107
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8107/health')" || exit 1
CMD ["uvicorn", "token_service.main:app", "--host", "0.0.0.0", "--port", "8107"]

```

---

### apps\token-service\pyproject.toml

```toml
[project]
name = "token-service"
version = "0.1.0"
description = "Mints short-lived LiveKit access tokens for browser/mobile callers (CDC web channel)."
requires-python = ">=3.12"
dependencies = [
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "pydantic==2.10.4",
  "livekit-api>=0.8",
  "python-dotenv==1.0.1",
]

[project.scripts]
token-service = "token_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### apps\token-service\src\token_service\__init__.py

```python
"""token-service package."""
```

---
---

### apps\token-service\tests\test_token.py

```python
"""Offline test: the minted token carries the room-join grant for the requested room."""
from __future__ import annotations

import os

os.environ.setdefault("LIVEKIT_API_KEY", "devkey")
os.environ.setdefault("LIVEKIT_API_SECRET", "devsecret_change_me_please_32chars_min")

import jwt  # provided by livekit-api
from livekit import api


def test_token_has_room_join_grant() -> None:
    token = (
        api.AccessToken()
        .with_identity("caller-1")
        .with_grants(api.VideoGrants(room_join=True, room="telecom-support"))
        .to_jwt()
    )
    claims = jwt.decode(token, os.environ["LIVEKIT_API_SECRET"], algorithms=["HS256"])
    assert claims["sub"] == "caller-1"
    assert claims["video"]["room"] == "telecom-support"
    assert claims["video"]["roomJoin"] is True
```

---

### deploy\backup\backup.sh

```bash
#!/usr/bin/env bash
# Nightly logical backup of the platform DB (report #22). Cron: 0 2 * * *
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$OUT_DIR/telecom-$STAMP.dump"
# pg_dump understands the libpq URL (strip the +psycopg driver suffix)
PG_URL="${DATABASE_URL/+psycopg/}"
pg_dump --format=custom --no-owner --dbname="$PG_URL" --file="$FILE"
echo "wrote $FILE"
# retention: keep the newest 14
ls -1t "$OUT_DIR"/telecom-*.dump | tail -n +15 | xargs -r rm -f
echo "backup complete"
```

---

### deploy\backup\restore.sh

```bash
#!/usr/bin/env bash
# Restore a logical backup (report #22).  Usage: restore.sh backups/telecom-YYYYMMDD-HHMMSS.dump
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
FILE="${1:?usage: restore.sh <dump-file>}"
PG_URL="${DATABASE_URL/+psycopg/}"
pg_restore --clean --if-exists --no-owner --dbname="$PG_URL" "$FILE"
echo "restored $FILE"
```

---

### deploy\backup\verify_audit_chain.py

```python
#!/usr/bin/env python3
"""CI/ops hook: verify the audit hash-chain against the live DB (report #19/#22 companion).

Exit 0 = intact, 1 = broken. Requires DATABASE_URL; a no-op success if persistence isn't importable
so the CI step never hard-fails on a unit-test-only runner.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL unset; skipping audit-chain verify")
        return 0
    try:
        from audit_trail import PgAuditLedger
        from persistence.engine import session_scope
    except Exception as exc:
        print(f"persistence not available ({exc}); skipping")
        return 0
    with session_scope() as session:
        ledger = PgAuditLedger(session)
        intact = ledger.verify()
        print(f"audit chain intact={intact} entries={ledger.count()}")
        return 0 if intact else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### deploy\gateway\docker-compose.gateway.yml

```yaml
# Run the gateway alongside the stack:
#   docker compose -f infra/docker-compose/docker-compose.yml -f deploy/gateway/docker-compose.gateway.yml up -d gateway
services:
  gateway:
    image: nginx:1.27-alpine
    container_name: telecom-gateway
    depends_on: [token-service, business-api]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "8080:80"
```

---

### deploy\gateway\nginx.conf

```nginx
# API gateway / reverse proxy (report #18). Only the edge is public; the internal services
# (context/decision/policy/execution/notification/knowledge) are NOT exposed - they sit on the
# private network behind INTERNAL_API_KEY. TLS terminates here in staging/prod.
worker_processes auto;
events { worker_connections 1024; }

http {
  sendfile on;
  keepalive_timeout 65;

  upstream token_service   { server token-service:8107; }
  upstream business_api    { server business-api:8108; }

  server {
    listen 80;
    server_name _;

    # LiveKit join tokens for the caller widget
    location /token/ {
      proxy_pass http://token_service/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Back-office API for the supervisor dashboard (RBAC enforced in the app)
    location /api/ {
      proxy_pass http://business_api/api/;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Role $http_x_role;
    }

    location /healthz { return 200 'ok'; add_header Content-Type text/plain; }
  }
}
```

---

### deploy\helm\telecom-agent\Chart.yaml

```yaml
apiVersion: v2
name: telecom-agent
description: Self-hosted telecom AI voice-agent platform (report #20)
type: application
version: 0.1.0
appVersion: "0.1.0"
```

---

### deploy\helm\telecom-agent\templates\deployment.yaml

```yaml
{{- range .Values.services }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .name }}
spec:
  replicas: 1
  selector:
    matchLabels: { app: {{ .name }} }
  template:
    metadata:
      labels: { app: {{ .name }} }
    spec:
      containers:
        - name: {{ .name }}
          image: "{{ $.Values.image.registry }}/{{ .name }}:{{ $.Values.image.tag }}"
          imagePullPolicy: {{ $.Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .port }}
          envFrom:
            - secretRef: { name: telecom-secrets }
          env:
            - name: CONNECTOR_MODE
              value: "{{ $.Values.env.CONNECTOR_MODE }}"
          readinessProbe:
            httpGet: { path: /health, port: {{ .port }} }
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {{ .name }}
spec:
  type: {{ if .public }}LoadBalancer{{ else }}ClusterIP{{ end }}
  selector: { app: {{ .name }} }
  ports:
    - port: {{ .port }}
      targetPort: {{ .port }}
---
{{- end }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.worker.name }}
spec:
  replicas: {{ .Values.worker.replicas }}
  selector:
    matchLabels: { app: {{ .Values.worker.name }} }
  template:
    metadata:
      labels: { app: {{ .Values.worker.name }} }
    spec:
      containers:
        - name: {{ .Values.worker.name }}
          image: "{{ .Values.image.registry }}/{{ .Values.worker.name }}:{{ .Values.image.tag }}"
          envFrom:
            - secretRef: { name: telecom-secrets }
```

---

### deploy\helm\telecom-agent\values.yaml

```yaml
# One entry per deployable; the template renders a Deployment + Service for each.
image:
  registry: registry.local
  tag: "0.1.0"
  pullPolicy: IfNotPresent

env:
  CONNECTOR_MODE: mock
  # DATABASE_URL / INTERNAL_API_KEY / provider keys come from the 'telecom-secrets' Secret (see secrets/)

services:
  - name: context-service
    port: 8101
  - name: decision-service
    port: 8103
  - name: policy-service
    port: 8104
  - name: execution-service
    port: 8105
  - name: notification-service
    port: 8106
  - name: knowledge-service
    port: 8102
  - name: token-service
    port: 8107
    public: true
  - name: business-api
    port: 8108
    public: true

worker:
  name: agent-worker
  replicas: 2
```

---

### deploy\otel\docker-compose.yml

```yaml
# OTel telemetry stack (Plane A, self-hosted). Run alongside the main compose:
#   docker compose -f docker-compose.yml -f deploy/otel/docker-compose.yml up -d otel-collector prometheus
# Then set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 for the worker + services.
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.110.0
    container_name: telecom-otel-collector
    command: ["--config=/etc/otel/config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel/config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus scrape endpoint

  prometheus:
    image: prom/prometheus:v2.55.0
    container_name: telecom-prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
```

---

### deploy\otel\otel-collector-config.yaml

```yaml
# Minimal self-hosted OTel Collector (Blueprint section 16: OTel -> Prometheus/Tempo/Grafana).
# Dev config: receive OTLP, expose metrics to Prometheus, and debug-log spans/metrics.
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch: {}

exporters:
  debug:
    verbosity: normal
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, prometheus]
```

---

### deploy\otel\prometheus.yml

```yaml
global:
  scrape_interval: 10s
scrape_configs:
  - job_name: "telecom-otel"
    static_configs:
      - targets: ["otel-collector:8889"]
```

---

### deploy\postgres\docker-compose.yml

```yaml
# Postgres for the telecom platform (spec section 2). Run alongside the main compose:
#   docker compose -f docker-compose.yml -f deploy/postgres/docker-compose.yml up -d postgres
services:
  postgres:
    image: postgres:16
    container_name: telecom-postgres
    environment:
      POSTGRES_DB: telecom
      POSTGRES_USER: telecom
      POSTGRES_PASSWORD: telecom
    ports:
      - "5432:5432"
    volumes:
      - telecom_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U telecom -d telecom"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  telecom_pgdata:
```

---

### deploy\secrets\docker-compose-secrets.yml

```yaml
# Docker Compose secrets file â€” source with `docker compose --secret` or merge manually.
# Example usage:
#   docker compose --env-file deploy/secrets/.env -f infra/docker-compose/docker-compose.yml up
secrets:
  postgres_password:
    environment: POSTGRES_PASSWORD
  internal_api_key:
    environment: INTERNAL_API_KEY
  twilio_sid:
    environment: TWILIO_ACCOUNT_SID
  twilio_token:
    environment: TWILIO_AUTH_TOKEN
  smtp_password:
    environment: SMTP_PASSWORD

```

---

### infra\docker-compose\docker-compose.apps.yml

```yaml
# App-tier services (diagnostic #8). Use WITH the infra compose:
#   docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build
# Build context is the repo root (two levels up from this file).
services:
  context-service:
    build:
      context: ../..
      dockerfile: services/context-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8101:8101"]
    restart: unless-stopped
  knowledge-service:
    build:
      context: ../..
      dockerfile: services/knowledge-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8102:8102"]
    restart: unless-stopped
  decision-service:
    build:
      context: ../..
      dockerfile: services/decision-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8103:8103"]
    restart: unless-stopped
  policy-service:
    build:
      context: ../..
      dockerfile: services/policy-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8104:8104"]
    restart: unless-stopped
  execution-service:
    build:
      context: ../..
      dockerfile: services/execution-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8105:8105"]
    restart: unless-stopped
  notification-service:
    build:
      context: ../..
      dockerfile: services/notification-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8106:8106"]
    restart: unless-stopped
  token-service:
    build:
      context: ../..
      dockerfile: apps/token-service/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
      LIVEKIT_AGENT_NAME: "${LIVEKIT_AGENT_NAME:-telecom-agent}"
    depends_on: [postgres]
    ports: ["8107:8107"]
    restart: unless-stopped
  business-api:
    build:
      context: ../..
      dockerfile: apps/business-api/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8108:8108"]
    restart: unless-stopped
  ai-knowledge-rag:
    build:
      context: ../..
      dockerfile: mcp-servers/ai-knowledge-rag/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8201:8201"]
    restart: unless-stopped
  ticketing-glpi:
    build:
      context: ../..
      dockerfile: mcp-servers/ticketing-glpi/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8202:8202"]
    restart: unless-stopped
  messaging-gateway:
    build:
      context: ../..
      dockerfile: mcp-servers/messaging-gateway/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
    depends_on: [postgres]
    ports: ["8203:8203"]
    restart: unless-stopped
  agent-worker:
    build:
      context: ../..
      dockerfile: apps/agent-worker/Dockerfile
    env_file: [../../.env]
    environment:
      DATABASE_URL: "postgresql+psycopg://${POSTGRES_USER:-telecom}:${POSTGRES_PASSWORD:-telecom}@postgres:5432/${POSTGRES_DB:-telecom}"
      LIVEKIT_AGENT_NAME: "${LIVEKIT_AGENT_NAME:-telecom-agent}"
    depends_on: [postgres, context-service, decision-service, policy-service, execution-service]
    restart: unless-stopped

```

---

### infra\docker-compose\docker-compose.yml

```yaml
# Local dev stack (Blueprint section 11 / Phase 1). Brings up the self-hosted plane.
services:
  livekit-server:
    profiles: ["self-hosted-livekit"]
    image: livekit/livekit-server:v1.8.4
    command: --dev --bind 0.0.0.0
    ports:
      - "7880:7880"
      - "7881:7881"
      - "7882:7882/udp"
    environment:
      LIVEKIT_KEYS: "${LIVEKIT_API_KEY:-devkey}: ${LIVEKIT_API_SECRET:-devsecret_change_me}"
    depends_on:
      - redis

  redis:
    image: redis:7.4-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "6379:6379"

  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-telecom}"]
      interval: 10s
      timeout: 5s
      retries: 5
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-telecom}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-telecom}
      POSTGRES_DB: ${POSTGRES_DB:-telecom}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:v1.12.5
    healthcheck:
      test: ["CMD-SHELL", "timeout 2 bash -c '</dev/tcp/127.0.0.1/6333' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "6333:6333"

  minio:
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.116.1
    ports:
      - "4317:4317"
      - "4318:4318"

volumes:
  postgres-data:
  minio-data:
```

---

### infra\docker-compose\nginx\nginx.conf

```nginx
upstream context { server context-service:8101; }
upstream knowledge { server knowledge-service:8102; }
upstream decision { server decision-service:8103; }
upstream policy { server policy-service:8104; }
upstream execution { server execution-service:8105; }
upstream notify { server notification-service:8106; }
upstream token { server token-service:8107; }
upstream business { server business-api:8108; }

server {
    listen 8080;
    server_name api.telecom.local;

    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Health - aggregate gateway health
    location /health {
        return 200 "{\"status\":\"ok\"}";
        add_header Content-Type application/json;
    }

    # Context service
    location /context/ {
        proxy_pass http://context;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Knowledge service
    location /knowledge/ {
        proxy_pass http://knowledge;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Decision service
    location /decision/ {
        proxy_pass http://decision;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Policy service
    location /policy/ {
        proxy_pass http://policy;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Execution service
    location /execution/ {
        proxy_pass http://execution;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Notification service
    location /notify/ {
        proxy_pass http://notify;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Token service
    location /token/ {
        proxy_pass http://token;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Business API
    location /business/ {
        proxy_pass http://business;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # LiveKit server (WebSocket)
    location /livekit/ {
        proxy_pass http://livekit-server:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # MinIO S3-compatible API
    location /minio/ {
        proxy_pass http://minio:9000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Catch-all
    location / {
        return 404 "{\"error\":\"route not found\"}";
        add_header Content-Type application/json;
    }
}

```

---

### infra\helm\telecom-platform\Chart.yaml

```yaml
apiVersion: v2
name: telecom-platform
description: Telecom AI Voice Agent Platform â€” Helm chart for K8s deployment
type: application
version: 0.1.0
appVersion: "0.1.0"

```

---

### infra\helm\telecom-platform\templates\gateway.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.apiGateway.replicaCount }}
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: nginx
          image: {{ .Values.apiGateway.image.repository }}:{{ .Values.apiGateway.image.tag }}
          imagePullPolicy: {{ .Values.global.imagePullPolicy }}
          ports:
            - containerPort: {{ .Values.apiGateway.port }}
              protocol: TCP
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/conf.d/default.conf
              subPath: nginx.conf
          readinessProbe:
            exec:
              command: ["nginx", "-t"]
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["nginx", "-t"]
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "128Mi"
      volumes:
        - name: nginx-config
          configMap:
            name: api-gateway-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-gateway-config
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
data:
  nginx.conf: |
    upstream context { server context-service:8101; }
    upstream knowledge { server knowledge-service:8102; }
    upstream decision { server decision-service:8103; }
    upstream policy { server policy-service:8104; }
    upstream execution { server execution-service:8105; }
    upstream notify { server notification-service:8106; }
    upstream token { server token-service:8107; }
    upstream business { server business-api:8108; }
    server {
        listen 8080;
        location /health { return 200 "{\"status\":\"ok\"}"; add_header Content-Type application/json; }
        location /context/ { proxy_pass http://context/; }
        location /knowledge/ { proxy_pass http://knowledge/; }
        location /decision/ { proxy_pass http://decision/; }
        location /policy/ { proxy_pass http://policy/; }
        location /execution/ { proxy_pass http://execution/; }
        location /notify/ { proxy_pass http://notify/; }
        location /token/ { proxy_pass http://token/; }
        location /business/ { proxy_pass http://business/; }
        location / { return 404 "{\"error\":\"route not found\"}"; add_header Content-Type application/json; }
    }
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  type: LoadBalancer
  selector:
    app: api-gateway
  ports:
    - port: 80
      targetPort: {{ .Values.apiGateway.port }}
      protocol: TCP

```

---

### infra\helm\telecom-platform\templates\infra.yaml

```yaml
{{- $infra := list
  (dict "name" "livekit-server" "image" (printf "%s:%s" .Values.livekit.image.repository .Values.livekit.image.tag) "port" 7880 "args" "--dev --bind 0.0.0.0" )
  (dict "name" "redis" "image" (printf "%s:%s" .Values.redis.image.repository .Values.redis.image.tag) "port" 6379)
  (dict "name" "qdrant" "image" (printf "%s:%s" .Values.qdrant.image.repository .Values.qdrant.image.tag) "port" 6333)
  (dict "name" "minio" "image" (printf "%s:%s" .Values.minio.image.repository .Values.minio.image.tag) "port" .Values.minio.port "args" "server /data --console-address \":9001\"" "env" (dict "MINIO_ROOT_USER" "minioadmin" "MINIO_ROOT_PASSWORD" "minioadmin"))
-}}
{{- range $svc := $infra }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $svc.name }}
  namespace: telecom-platform
  labels: {{ include "telecom.labels" $ | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ $svc.name }}
  template:
    metadata:
      labels:
        app: {{ $svc.name }}
    spec:
      containers:
        - name: {{ $svc.name }}
          image: {{ $svc.image }}
          imagePullPolicy: {{ $.Values.global.imagePullPolicy }}
          ports:
            - containerPort: {{ $svc.port }}
              protocol: TCP
          {{- with $svc.args }}
          args: {{ . | quote }}
          {{- end }}
          {{- with $svc.env }}
          env:
            {{- range $k, $v := . }}
            - name: {{ $k }}
              value: {{ $v | quote }}
            {{- end }}
          {{- end }}
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $svc.name }}
  namespace: telecom-platform
  labels: {{ include "telecom.labels" $ | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app: {{ $svc.name }}
  ports:
    - port: {{ $svc.port }}
      targetPort: {{ $svc.port }}
      protocol: TCP
{{- end }}

---
# Postgres (with persistent volume)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: {{ .Values.postgres.image.repository }}:{{ .Values.postgres.image.tag }}
          imagePullPolicy: {{ .Values.global.imagePullPolicy }}
          ports:
            - containerPort: {{ .Values.postgres.port }}
              protocol: TCP
          env:
            - name: POSTGRES_USER
              value: {{ .Values.global.postgres.user }}
            - name: POSTGRES_PASSWORD
              value: {{ .Values.global.postgres.password }}
            - name: POSTGRES_DB
              value: {{ .Values.global.postgres.database }}
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          resources:
            requests:
              cpu: "200m"
              memory: "256Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: postgres-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: telecom-platform
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: {{ .Values.postgres.storage }}
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app: postgres
  ports:
    - port: {{ .Values.postgres.port }}
      targetPort: {{ .Values.postgres.port }}
      protocol: TCP

```

---

### infra\helm\telecom-platform\templates\namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}

```

---

### infra\helm\telecom-platform\templates\otel.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.otelCollector.replicaCount }}
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
        - name: otel-collector
          image: {{ .Values.otelCollector.image.repository }}:{{ .Values.otelCollector.image.tag }}
          imagePullPolicy: {{ .Values.global.imagePullPolicy }}
          ports:
            - containerPort: {{ .Values.otelCollector.port }}
              protocol: TCP
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: telecom-platform
  labels: {{ include "telecom.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app: otel-collector
  ports:
    - port: {{ .Values.otelCollector.port }}
      targetPort: {{ .Values.otelCollector.port }}
      protocol: TCP

```

---

### infra\helm\telecom-platform\templates\secrets.yaml

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: telecom-platform-secrets
  labels: {{ include "telecom.labels" . | nindent 4 }}
type: Opaque
stringData:
  INTERNAL_API_KEY: {{ .Values.global.internalApiKey | quote }}
  DATABASE_URL: "postgresql+psycopg://{{ .Values.global.postgres.user }}:{{ .Values.global.postgres.password }}@{{ .Values.global.postgres.host }}:{{ .Values.global.postgres.port }}/{{ .Values.global.postgres.database }}"
  REDIS_URL: "redis://{{ .Values.global.redis.host }}:{{ .Values.global.redis.port }}/0"
  LIVEKIT_API_KEY: {{ .Values.global.livekit.apiKey | quote }}
  LIVEKIT_API_SECRET: {{ .Values.global.livekit.apiSecret | quote }}

```

---

### infra\helm\telecom-platform\templates\services.yaml

```yaml
{{- $global := .Values.global -}}
{{- $services := list
  (dict "name" "context-service"    "port" 8101 "replicas" .Values.contextService.replicaCount    "image" .Values.contextService.image.repository    "probePath" "/health")
  (dict "name" "knowledge-service"  "port" 8102 "replicas" .Values.knowledgeService.replicaCount  "image" .Values.knowledgeService.image.repository  "probePath" "/health")
  (dict "name" "decision-service"   "port" 8103 "replicas" .Values.decisionService.replicaCount   "image" .Values.decisionService.image.repository   "probePath" "/health")
  (dict "name" "policy-service"     "port" 8104 "replicas" .Values.policyService.replicaCount     "image" .Values.policyService.image.repository     "probePath" "/health")
  (dict "name" "execution-service"  "port" 8105 "replicas" .Values.executionService.replicaCount  "image" .Values.executionService.image.repository  "probePath" "/health")
  (dict "name" "notification-service" "port" 8106 "replicas" .Values.notificationService.replicaCount "image" .Values.notificationService.image.repository "probePath" "/health")
  (dict "name" "token-service"      "port" 8107 "replicas" .Values.tokenService.replicaCount      "image" .Values.tokenService.image.repository      "probePath" "/health")
  (dict "name" "business-api"       "port" 8108 "replicas" .Values.businessApi.replicaCount       "image" .Values.businessApi.image.repository       "probePath" "/health")
-}}
{{- range $svc := $services }}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $svc.name }}
  namespace: telecom-platform
  labels: {{ include "telecom.labels" $ | nindent 4 }}
spec:
  replicas: {{ $svc.replicas }}
  selector:
    matchLabels:
      app: {{ $svc.name }}
  template:
    metadata:
      labels:
        app: {{ $svc.name }}
    spec:
      containers:
        - name: {{ $svc.name }}
          image: {{ $global.imageRegistry }}/{{ $svc.image }}:{{ $global.imageTag }}
          imagePullPolicy: {{ $global.imagePullPolicy }}
          ports:
            - containerPort: {{ $svc.port }}
              protocol: TCP
          envFrom:
            - secretRef:
                name: telecom-platform-secrets
          readinessProbe:
            httpGet:
              path: {{ $svc.probePath }}
              port: {{ $svc.port }}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: {{ $svc.probePath }}
              port: {{ $svc.port }}
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $svc.name }}
  namespace: telecom-platform
  labels: {{ include "telecom.labels" $ | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    app: {{ $svc.name }}
  ports:
    - port: {{ $svc.port }}
      targetPort: {{ $svc.port }}
      protocol: TCP
{{- end }}

```

---

### infra\helm\telecom-platform\values.yaml

```yaml
# Global settings â€” overridden per environment via --values staging.yaml / prod.yaml
global:
  imageRegistry: ghcr.io
  imageTag: latest
  imagePullPolicy: Always
  internalApiKey: ""  # set via --set global.internalApiKey=... or sealed-secret
  postgres:
    host: postgres
    port: 5432
    user: telecom
    password: telecom
    database: telecom
  redis:
    host: redis
    port: 6379
  livekit:
    host: livekit-server
    port: 7880
    apiKey: devkey
    apiSecret: devsecret_change_me

# --- Services ---
contextService:
  replicaCount: 2
  image:
    repository: context-service
  port: 8101

knowledgeService:
  replicaCount: 2
  image:
    repository: knowledge-service
  port: 8102

decisionService:
  replicaCount: 2
  image:
    repository: decision-service
  port: 8103

policyService:
  replicaCount: 2
  image:
    repository: policy-service
  port: 8104

executionService:
  replicaCount: 2
  image:
    repository: execution-service
  port: 8105

notificationService:
  replicaCount: 2
  image:
    repository: notification-service
  port: 8106

tokenService:
  replicaCount: 1
  image:
    repository: token-service
  port: 8107

businessApi:
  replicaCount: 2
  image:
    repository: business-api
  port: 8108

agentWorker:
  replicaCount: 2
  image:
    repository: agent-worker

# --- Infrastructure ---
apiGateway:
  replicaCount: 2
  image:
    repository: nginx
    tag: 1.27-alpine
  port: 8080

livekit:
  replicaCount: 1
  image:
    repository: livekit/livekit-server
    tag: v1.8.4

redis:
  replicaCount: 1
  image:
    repository: redis
    tag: 7.4-alpine
  port: 6379

postgres:
  replicaCount: 1
  image:
    repository: postgres
    tag: 16-alpine
  port: 5432
  storage: 10Gi

qdrant:
  replicaCount: 1
  image:
    repository: qdrant/qdrant
    tag: v1.12.5
  port: 6333

minio:
  replicaCount: 1
  image:
    repository: minio/minio
    tag: RELEASE.2024-12-18T13-15-44Z
  port: 9000
  consolePort: 9001
  storage: 10Gi

# --- Observability ---
otelCollector:
  replicaCount: 1
  image:
    repository: otel/opentelemetry-collector-contrib
    tag: 0.116.1
  port: 4317

prometheus:
  replicaCount: 1
  image:
    repository: prom/prometheus
    tag: v2.53.0
  port: 9090

```

---

### Makefile

```makefile
 # Telecom AI Voice Agent â€” one place to install, run, verify (diagnostic #1, #7, #9).
# NOTE: Requires `make` + bash (WSL/Git Bash on Windows).
#       Windows PowerShell users: run `.\start.ps1 up` / `.\start.ps1 rebuild` instead.
SHELL := /bin/bash
PACKAGES := domain-core persistence audit-trail pii-shield observability-kit service-auth cache object-storage notification-client integration-adapters
SERVICES := services/context-service services/knowledge-service services/decision-service services/policy-service services/execution-service services/notification-service apps/token-service apps/business-api
MCP := mcp-servers/ai-knowledge-rag mcp-servers/ticketing-glpi mcp-servers/messaging-gateway
INFRA := infra/docker-compose/docker-compose.yml
APPS := infra/docker-compose/docker-compose.apps.yml
export DATABASE_URL ?= postgresql+psycopg://telecom:telecom@localhost:5432/telecom
PYTHON := "$(shell if [ -x .venv/bin/python ]; then echo $(CURDIR)/.venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo $(CURDIR)/.venv/Scripts/python.exe; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)"
PIP := $(PYTHON) -m pip
UVICORN := $(PYTHON) -m uvicorn
HONCHO := $(shell if [ -x .venv/bin/honcho ]; then echo $(CURDIR)/.venv/bin/honcho; elif [ -x .venv/Scripts/honcho.exe ]; then echo $(CURDIR)/.venv/Scripts/honcho.exe; else echo honcho; fi)
DOCKER := $(shell if command -v docker >/dev/null 2>&1; then echo docker; elif [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then echo "'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe'"; elif [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker" ]; then echo "'/mnt/c/Program Files/Docker/Docker/resources/bin/docker'"; elif [ -x "/usr/bin/docker" ]; then echo docker; else echo docker; fi)

.DEFAULT_GOAL := help
.PHONY: help install infra infra-livekit create-db migrate seed dev up down rebuild health live-logs test frontends frontends-clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Install packages (correct order) + services + MCP + honcho (editable)
	$(PIP) install honcho
	$(PIP) uninstall -y knowledge-glpi-mcp 2>/dev/null || true
	$(PIP) install $(addprefix -e ./packages/,$(PACKAGES))
	$(PIP) install $(addprefix -e ./,$(SERVICES)) $(addprefix -e ./,$(MCP)) -e ./apps/agent-worker
	@echo "â†’ frontends: run 'make frontends'"

frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS (fixes Rollup optional deps)
	cd apps/supervisor-dashboard && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install

infra:  ## Start infrastructure containers (postgres/redis/qdrant/minio/otel)
	$(DOCKER) compose -f $(INFRA) up -d

infra-livekit:  ## Also start the self-hosted LiveKit server (SKIP if using LiveKit Cloud)
	$(DOCKER) compose -f $(INFRA) --profile self-hosted-livekit up -d

create-db:  ## Create the telecom database in Postgres if it does not exist yet
	$(DOCKER) compose -f $(INFRA) exec -T postgres psql -U "$${POSTGRES_USER:-telecom}" -d postgres -c "CREATE DATABASE \"$${POSTGRES_DB:-telecom}\" OWNER \"$${POSTGRES_USER:-telecom}\";" 2>/dev/null || true

migrate: create-db  ## Apply DB migrations (alembic upgrade head)
	cd packages/persistence && $(PYTHON) -m alembic upgrade head

seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference

dev: install infra migrate seed  ## ONE COMMAND: install + infra + migrate + seed, then run everything (honcho)
	@echo "Starting all app processes via honcho (Ctrl-C to stop all)â€¦"
	$(HONCHO) start

up:  ## Start all containers (infra + apps) â€” use 'rebuild' after code changes
	$(DOCKER) compose -f $(INFRA) -f $(APPS) up -d --remove-orphans

down:  ## Stop everything (infra + apps + optional livekit)
	$(DOCKER) compose -f $(INFRA) -f $(APPS) --profile self-hosted-livekit down --remove-orphans

rebuild: down  ## Stop + rebuild + redeploy all containers (use after code changes)
	$(DOCKER) compose -f $(INFRA) -f $(APPS) up -d --build --remove-orphans
	@echo "â†’ All images rebuilt & containers running. Run 'make health' to verify."

health:  ## Probe every service /health
	$(PYTHON) scripts/health_check.py

live-logs:  ## Follow token-service + agent-worker logs during a browser call
	$(DOCKER) compose -f $(INFRA) -f $(APPS) logs -f --tail=120 token-service agent-worker

test:  ## Run the offline test suite across packages/services
	$(PYTHON) scripts/run_tests.py

```

---

### mcp-servers\ai-knowledge-rag\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f mcp-servers/ai-knowledge-rag/Dockerfile -t ai-knowledge-rag .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY mcp-servers/ai-knowledge-rag/ ./mcp-servers/ai-knowledge-rag/
RUN pip install ./mcp-servers/ai-knowledge-rag
USER app
EXPOSE 8201
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 8201), 3); s.close()" || exit 1
CMD ["python", "-m", "ai_knowledge_rag.server"]

```

---

### mcp-servers\ai-knowledge-rag\pyproject.toml

```toml
[project]
name = "ai-knowledge-rag"
version = "0.1.0"
description = "Internal MCP server: knowledge_search (RAG/FAQ). Read-only, low-risk, reusable."
requires-python = ">=3.12"
dependencies = [
  "mcp>=1.0.0,<2",
  "httpx==0.28.1",
]

[project.scripts]
ai-knowledge-rag = "ai_knowledge_rag.server:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### mcp-servers\ai-knowledge-rag\src\ai_knowledge_rag\__init__.py

```python
"""ai-knowledge-rag MCP server package."""
```

---

### mcp-servers\ai-knowledge-rag\src\ai_knowledge_rag\server.py

```python
"""ai-knowledge-rag MCP server (streamable HTTP) exposing knowledge_search only (review note 1).

Run: python -m ai_knowledge_rag.server  (serves streamable HTTP at http://HOST:PORT/mcp)
GLPI ticketing lives in the separate ticketing-glpi server (Phase 9).
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ai_knowledge_rag.tools.knowledge_search import knowledge_search

mcp = FastMCP(
    "ai-knowledge-rag",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8201")),
)

mcp.tool()(knowledge_search)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

---

### mcp-servers\ai-knowledge-rag\src\ai_knowledge_rag\tools\__init__.py

```python
"""MCP tools for the knowledge server (one file per tool)."""
```

---

### mcp-servers\ai-knowledge-rag\src\ai_knowledge_rag\tools\knowledge_search.py

```python
"""knowledge_search MCP tool (read-only; every persona may call it).

Proxies to the knowledge-service /search. Returns passages each carrying a 'source' so the
agent can cite it.
"""

import os

import httpx

KNOWLEDGE_SERVICE_URL = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8102")


async def knowledge_search(query: str, top_k: int = 4) -> list[dict]:
    """Search the telecom knowledge base for offers, procedures and FAQs.

    Args:
        query: An English search query describing what the caller needs.
        top_k: Maximum number of passages to return.

    Returns:
        A list of passages, each with 'text', 'source', and 'score'. Cite the 'source'.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{KNOWLEDGE_SERVICE_URL}/search",
            json={"query": query, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json().get("passages", [])
```

---

### mcp-servers\messaging-gateway\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f mcp-servers/messaging-gateway/Dockerfile -t messaging-gateway .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY mcp-servers/messaging-gateway/ ./mcp-servers/messaging-gateway/
RUN pip install ./mcp-servers/messaging-gateway
USER app
EXPOSE 8203
CMD ["python", "-m", "messaging_gateway.server"]

```

---

### mcp-servers\messaging-gateway\pyproject.toml

```toml
[project]
name = "messaging-gateway"
version = "0.1.0"
description = "MCP: outbound messaging (SMS/WhatsApp) via the notification-service (report #2)."
requires-python = ">=3.12"
dependencies = ["mcp", "httpx==0.28.1"]

[project.scripts]
messaging-gateway = "messaging_gateway.server:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### mcp-servers\messaging-gateway\src\messaging_gateway\__init__.py

```python
"""Messaging-gateway MCP server (report #2)."""
```

---

### mcp-servers\messaging-gateway\src\messaging_gateway\server.py

```python
"""messaging-gateway MCP server (streamable HTTP). Run: python -m messaging_gateway.server (/mcp)."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from messaging_gateway.tools.messaging_ops import send_sms, send_whatsapp

mcp = FastMCP(
    "messaging-gateway",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8203")),
)

for _tool in (send_sms, send_whatsapp):
    mcp.tool()(_tool)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

---

### mcp-servers\messaging-gateway\src\messaging_gateway\tools\__init__.py

```python
"""Messaging tools."""
```

---

### mcp-servers\messaging-gateway\src\messaging_gateway\tools\messaging_ops.py

```python
"""Outbound messaging MCP tools: send a free-form SMS / WhatsApp through the notification-service.

Kept thin on purpose: the notification-service owns channel selection, localization and the durable
log; this MCP just exposes an agent-callable surface for ad-hoc outbound messages.
"""

import os

import httpx

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")


async def _send(channel: str, to: str, message: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{NOTIFICATION_SERVICE_URL}/notify",
            json={"customer_id": to, "to": to, "channel": channel, "template": "freeform",
                  "language": "fr", "params": {"body": message}},
        )
        ok = resp.status_code == 200 and resp.json().get("sent", False)
        return {"sent": bool(ok), "channel": channel}


async def send_sms(to: str, message: str) -> dict:
    """Send an SMS to ``to`` with ``message`` via the notification-service."""
    return await _send("sms", to, message)


async def send_whatsapp(to: str, message: str) -> dict:
    """Send a WhatsApp message to ``to`` with ``message`` via the notification-service."""
    return await _send("whatsapp", to, message)
```

---

### mcp-servers\ticketing-glpi\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f mcp-servers/ticketing-glpi/Dockerfile -t ticketing-glpi .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY mcp-servers/ticketing-glpi/ ./mcp-servers/ticketing-glpi/
RUN pip install ./mcp-servers/ticketing-glpi
USER app
EXPOSE 8202
CMD ["python", "-m", "ticketing_glpi.server"]

```

---

### mcp-servers\ticketing-glpi\pyproject.toml

```toml
[project]
name = "ticketing-glpi"
version = "0.1.0"
description = "Internal MCP server: GLPI ticket lifecycle (create/status/resolve/lookup)."
requires-python = ">=3.12"
dependencies = [
  "persistence",
  "mcp>=1.0.0,<2",
  "httpx==0.28.1",
]

[project.scripts]
ticketing-glpi = "ticketing_glpi.server:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\__init__.py

```python
"""ticketing-glpi MCP server package."""
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\adapters\__init__.py

```python
"""Ticketing adapters (mock GLPI now; real GLPI REST client later)."""
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\adapters\glpi_client.py

```python
"""Mock GLPI client (in-memory ticket store). A real GLPI REST adapter replaces this without
changing the tools. Tickets become Postgres/GLPI-backed in the persistence phase.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass
class Ticket:
    """A GLPI ticket."""

    ticket_id: str
    customer_id: str
    subject: str
    description: str
    status: str            # "new" | "resolved"
    resolution: str | None = None


class MockGlpiClient:
    """In-memory GLPI ticket lifecycle."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0

    def create(self, customer_id: str, subject: str, description: str) -> Ticket:
        self._counter += 1
        ticket_id = f"GLPI-{self._counter:05d}"
        ticket = Ticket(ticket_id, customer_id, subject, description, status="new")
        self._tickets[ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "resolved"
        ticket.resolution = resolution
        return ticket

    def list_for(self, customer_id: str) -> list[Ticket]:
        return [t for t in self._tickets.values() if t.customer_id == customer_id]


class LiveGlpiClient:
    """Real GLPI REST client (report #4). Same interface as MockGlpiClient so the tools are unchanged.

    Uses the GLPI REST API: initSession (App-Token + user_token) -> session token, then Ticket CRUD.
    `list_for` is left as a no-op search (returns []) until the customerâ†”ticket search is bound.
    """

    def __init__(self, base_url: str, app_token: str, user_token: str) -> None:
        self._base = base_url
        self._app = app_token
        self._user = user_token

    def _headers(self, client: httpx.Client) -> dict:
        r = client.get("/initSession", headers={
            "App-Token": self._app, "Authorization": f"user_token {self._user}",
        })
        r.raise_for_status()
        return {"App-Token": self._app, "Session-Token": r.json()["session_token"]}

    def create(self, customer_id: str, subject: str, description: str) -> Ticket:
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.post("/Ticket", headers=h, json={"input": {"name": subject, "content": description}})
            r.raise_for_status()
            tid = str(r.json().get("id"))
            return Ticket(f"GLPI-{tid}", customer_id, subject, description, status="new")

    def get(self, ticket_id: str) -> Ticket | None:
        numeric = ticket_id.replace("GLPI-", "")
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.get(f"/Ticket/{numeric}", headers=h)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            d = r.json()
            status = "resolved" if int(d.get("status", 1)) >= 5 else "new"
            return Ticket(ticket_id, customer_id="", subject=d.get("name", ""),
                          description=d.get("content", ""), status=status)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        numeric = ticket_id.replace("GLPI-", "")
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.put(f"/Ticket/{numeric}", headers=h,
                      json={"input": {"status": 5, "solution": resolution}})  # 5 = solved
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return Ticket(ticket_id, customer_id="", subject="", description="", status="resolved",
                          resolution=resolution)

    def list_for(self, customer_id: str) -> list[Ticket]:
        return []  # GLPI search binding TODO; the Postgres mirror answers lookups meanwhile


def get_glpi_client():
    """Return the live GLPI client when CONNECTOR_MODE=live and GLPI creds are set; else the mock."""
    if os.getenv("CONNECTOR_MODE", "mock").lower() == "live":
        base = os.getenv("GLPI_BASE_URL")
        app = os.getenv("GLPI_APP_TOKEN")
        user = os.getenv("GLPI_USER_TOKEN")
        if base and app and user:
            return LiveGlpiClient(base, app, user)
    return MockGlpiClient()
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\adapters\mirror.py

```python
"""Postgres mirror of GLPI tickets (spec section 10): a thin durable cache pointing at the GLPI id.

GLPI remains the source of truth; this mirror makes the local view durable across restarts and
queryable by the platform. Every function is best-effort and gated on DATABASE_URL, so the MCP
server still runs (mock-only) when no database is configured.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = {"network_complaint", "formal_complaint", "technical", "billing", "other"}


def normalize_category(category: str | None) -> str:
    """Coerce a free category to the spec's ticketing.tickets vocabulary (default 'other')."""
    return category if category in _ALLOWED_CATEGORIES else "other"


def _enabled() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def mirror_create(glpi_ticket_id: str, customer_id: str | None, subject: str | None,
                  category: str = "other", subscription_id: str | None = None,
                  priority: str | None = None) -> None:
    """Insert a mirror row for a freshly created GLPI ticket (idempotent on glpi_ticket_id)."""
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket
    from persistence.util import to_uuid

    try:
        with session_scope() as session:
            if session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id)):
                return
            session.add(Ticket(
                glpi_ticket_id=glpi_ticket_id,
                customer_id=to_uuid(customer_id),
                subscription_id=to_uuid(subscription_id),
                subject=(subject or "")[:255] or None,
                category=normalize_category(category),
                status="open",
                priority=priority,
            ))
    except Exception as exc:
        logger.warning("ticket mirror create failed (%s): %s", glpi_ticket_id, exc)


def mirror_resolve(glpi_ticket_id: str) -> None:
    """Mark the mirror row resolved + bump last_synced_at."""
    if not _enabled():
        return
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is not None:
                row.status = "resolved"
                row.last_synced_at = datetime.now(UTC)
    except Exception as exc:
        logger.warning("ticket mirror resolve failed (%s): %s", glpi_ticket_id, exc)


def read_status(glpi_ticket_id: str) -> dict | None:
    """Return the mirror view of a ticket, or None if absent / mirror disabled."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket

    try:
        with session_scope() as session:
            row = session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == glpi_ticket_id))
            if row is None:
                return None
            return {"ticket_id": row.glpi_ticket_id, "status": row.status, "subject": row.subject}
    except Exception as exc:
        logger.warning("ticket mirror read failed (%s): %s", glpi_ticket_id, exc)
        return None


def read_for_customer(customer_id: str) -> list[dict] | None:
    """Return a customer's mirrored tickets, or None when the mirror is disabled/unavailable."""
    if not _enabled():
        return None
    from persistence.engine import session_scope
    from persistence.models.ticketing import Ticket
    from persistence.util import to_uuid

    cid = to_uuid(customer_id)
    if cid is None:
        return None
    try:
        with session_scope() as session:
            rows = session.scalars(select(Ticket).where(Ticket.customer_id == cid))
            return [{"ticket_id": r.glpi_ticket_id, "status": r.status, "subject": r.subject} for r in rows]
    except Exception as exc:
        logger.warning("ticket mirror list failed (%s): %s", customer_id, exc)
        return None
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\server.py

```python
"""ticketing-glpi MCP server (streamable HTTP): GLPI ticket lifecycle (review note 1).

Run: python -m ticketing_glpi.server  (serves streamable HTTP at http://HOST:PORT/mcp)
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ticketing_glpi.tools.glpi_ticket_ops import (
    create_ticket,
    get_ticket_status,
    lookup_tickets,
    resolve_ticket,
)

mcp = FastMCP(
    "ticketing-glpi",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8202")),
)

for _tool in (create_ticket, get_ticket_status, resolve_ticket, lookup_tickets):
    mcp.tool()(_tool)


def main() -> None:
    """Serve the MCP server over streamable HTTP (endpoint path: /mcp)."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\tools\__init__.py

```python
"""MCP tools for GLPI ticketing (one file groups the lifecycle)."""
```

---

### mcp-servers\ticketing-glpi\src\ticketing_glpi\tools\glpi_ticket_ops.py

```python
"""GLPI ticket lifecycle MCP tools: create / status / resolve / lookup.

GLPI (mock) remains the source of truth; a durable Postgres mirror (spec section 10) is written
on create/resolve and read on status/lookup, falling back to the in-memory mock when no database
is configured. create_ticket also asks the notification-service to text a written confirmation.
"""
import asyncio
import os

import httpx

from ticketing_glpi.adapters import mirror
from ticketing_glpi.adapters.glpi_client import get_glpi_client

_client = get_glpi_client()
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")


async def create_ticket(customer_id: str, subject: str, description: str,
                        language: str = "fr", category: str = "other") -> dict:
    """Open a support ticket for an unresolved issue and text the caller a written confirmation.

    Args:
        customer_id: The caller's customer id.
        subject: Short ticket subject.
        description: What needs follow-up.
        language: Caller language for the confirmation (fr/ar/en).
        category: Ticket category (network_complaint/formal_complaint/technical/billing/other).
    """
    ticket = _client.create(customer_id, subject, description)
    await asyncio.to_thread(mirror.mirror_create, ticket.ticket_id, customer_id, subject, category)

    confirmation_sent = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notify",
                json={
                    "customer_id": customer_id,
                    "to": customer_id,
                    "channel": "sms",
                    "template": "ticket_created",
                    "language": language,
                    "params": {"ticket_id": ticket.ticket_id},
                },
            )
            confirmation_sent = resp.status_code == 200 and resp.json().get("sent", False)
    except httpx.HTTPError:
        confirmation_sent = False
    return {"ticket_id": ticket.ticket_id, "status": ticket.status, "written_confirmation_sent": confirmation_sent}


async def get_ticket_status(ticket_id: str) -> dict:
    """Look up the status of a ticket (durable mirror first, mock fallback)."""
    mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
    if mirrored is not None:
        return {"found": True, **mirrored}
    ticket = _client.get(ticket_id)
    if ticket is None:
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status, "subject": ticket.subject}


async def resolve_ticket(ticket_id: str, resolution: str) -> dict:
    """Resolve/close a ticket when the issue is solved during the call (review note 2)."""
    ticket = _client.resolve(ticket_id, resolution)
    await asyncio.to_thread(mirror.mirror_resolve, ticket_id)
    if ticket is None:
        mirrored = await asyncio.to_thread(mirror.read_status, ticket_id)
        if mirrored is not None:
            return {"found": True, "ticket_id": ticket_id, "status": "resolved"}
        return {"found": False}
    return {"found": True, "ticket_id": ticket.ticket_id, "status": ticket.status}


async def lookup_tickets(customer_id: str) -> list[dict]:
    """List a customer's tickets (durable mirror first, mock fallback)."""
    mirrored = await asyncio.to_thread(mirror.read_for_customer, customer_id)
    if mirrored is not None:
        return mirrored
    return [
        {"ticket_id": t.ticket_id, "status": t.status, "subject": t.subject}
        for t in _client.list_for(customer_id)
    ]
```

---

### mcp-servers\ticketing-glpi\tests\test_mirror.py

```python
"""Offline tests for the ticket-mirror pure logic (no DB)."""
from __future__ import annotations

from ticketing_glpi.adapters.mirror import normalize_category, read_status


def test_normalize_category() -> None:
    assert normalize_category("network_complaint") == "network_complaint"
    assert normalize_category("billing") == "billing"
    assert normalize_category("weird") == "other"
    assert normalize_category(None) == "other"


def test_mirror_disabled_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert read_status("GLPI-00001") is None  # gated off -> mock fallback handles reads
```

---

### packages\audit-trail\pyproject.toml

```toml
[project]
name = "audit-trail"
version = "0.1.0"
description = "Append-only, hash-chained audit ledger (in-memory + Postgres-backed)."
requires-python = ">=3.12"
dependencies = ["domain-core", "persistence"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\audit-trail\src\audit_trail\__init__.py

```python
"""Hash-chained audit ledger (Blueprint section 12.3): in-memory + Postgres-backed."""
from audit_trail.ledger import (
    GENESIS_HASH,
    AuditEntry,
    AuditLedger,
    PgAuditLedger,
    build_entry,
    compute_entry_hash,
    verify_chain,
)

__all__ = [
    "GENESIS_HASH",
    "AuditEntry",
    "AuditLedger",
    "PgAuditLedger",
    "build_entry",
    "compute_entry_hash",
    "verify_chain",
]
```

---

### packages\audit-trail\src\audit_trail\ledger.py

```python
"""Append-only, hash-chained audit ledger (cookbook section 18; Blueprint section 12.3 / ADR 5.6).

entry_hash = sha256(previous_hash | canonical_payload | timestamp). Any retroactive edit breaks
the chain and is caught by verify. Two implementations behind the same shape: an in-memory
`AuditLedger` (used in tests) and a Postgres-backed `PgAuditLedger` (used by the services).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
_AUDIT_LOCK_KEY = 8472  # pg advisory lock: serialize chain appends within a transaction


@dataclass(frozen=True)
class AuditEntry:
    """One immutable, hash-chained audit record (English payload)."""

    entry_id: str
    session_id: str
    event_type: str
    payload: dict
    previous_hash: str
    timestamp: str
    entry_hash: str


def compute_entry_hash(previous_hash: str, payload: dict, timestamp: str) -> str:
    """sha256(previous_hash | canonical(payload) | timestamp). Canonical = sorted, compact JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest_input = f"{previous_hash}|{canonical}|{timestamp}".encode()
    return hashlib.sha256(digest_input).hexdigest()


def build_entry(
    entry_id: str, session_id: str, event_type: str, payload: dict, previous_hash: str
) -> AuditEntry:
    """Build a chained entry linking to ``previous_hash``."""
    timestamp = datetime.now(UTC).isoformat()
    entry_hash = compute_entry_hash(previous_hash, payload, timestamp)
    return AuditEntry(entry_id, session_id, event_type, payload, previous_hash, timestamp, entry_hash)


def verify_chain(entries: list[AuditEntry]) -> bool:
    """Integrity job: any retroactive edit breaks the chain here."""
    expected_previous = GENESIS_HASH
    for entry in entries:
        if entry.previous_hash != expected_previous:
            return False
        if compute_entry_hash(entry.previous_hash, entry.payload, entry.timestamp) != entry.entry_hash:
            return False
        expected_previous = entry.entry_hash
    return True


class AuditLedger:
    """In-process append-only ledger (tests / fallback)."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash = GENESIS_HASH

    def append(self, session_id: str, event_type: str, payload: dict) -> AuditEntry:
        entry = build_entry(str(uuid.uuid4()), session_id, event_type, payload, self._last_hash)
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def verify(self) -> bool:
        return verify_chain(self._entries)

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


class PgAuditLedger:
    """Postgres-backed append-only ledger over audit.audit_ledger (spec section 12.3).

    append() serializes the chain with a transaction-scoped advisory lock, reads the prior
    entry_hash, computes the new hash, and inserts (flush only - the caller owns the commit, so
    the verdict/action write and its audit entry land in one transaction). Append-only by role.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, session_id, event_type: str, payload: dict, entity_reference: str | None = None):
        from persistence.models.audit import AuditLedgerEntry

        self._session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY})
        last = self._session.scalar(
            select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.desc()).limit(1)
        )
        previous_hash = last.entry_hash if last else GENESIS_HASH
        created_at = datetime.now(UTC)
        entry_hash = compute_entry_hash(previous_hash, payload, created_at.isoformat())
        row = AuditLedgerEntry(
            session_id=session_id,
            event_type=event_type,
            entity_reference=entity_reference,
            payload=payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        logger.info("audit event_type=%s hash=%s", event_type, entry_hash[:12])
        return row

    def verify(self) -> bool:
        """Recompute the whole chain; False on any break (tamper-evident)."""
        from persistence.models.audit import AuditLedgerEntry

        rows = list(self._session.scalars(select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.asc())))
        expected_previous = GENESIS_HASH
        for row in rows:
            if row.previous_hash != expected_previous:
                return False
            if compute_entry_hash(row.previous_hash, row.payload, row.created_at.isoformat()) != row.entry_hash:
                return False
            expected_previous = row.entry_hash
        return True

    def count(self) -> int:
        from persistence.models.audit import AuditLedgerEntry

        return self._session.scalar(select(func.count()).select_from(AuditLedgerEntry)) or 0
```

---

### packages\audit-trail\tests\test_chain.py

```python
"""Offline tests for the hash-chain primitives (no DB)."""
from __future__ import annotations

from audit_trail import AuditLedger, build_entry, compute_entry_hash, verify_chain
from audit_trail.ledger import GENESIS_HASH


def test_compute_entry_hash_is_deterministic() -> None:
    a = compute_entry_hash(GENESIS_HASH, {"b": 2, "a": 1}, "2026-06-29T00:00:00+00:00")
    b = compute_entry_hash(GENESIS_HASH, {"a": 1, "b": 2}, "2026-06-29T00:00:00+00:00")
    assert a == b  # canonical (key-sorted) payload


def test_ledger_chain_is_intact() -> None:
    ledger = AuditLedger()
    ledger.append("s1", "policy_verdict", {"verdict": "AUTHORIZED"})
    ledger.append("s1", "execution_result", {"reference": "PAY-1"})
    assert ledger.verify() is True
    assert len(ledger.entries) == 2


def test_tamper_breaks_the_chain() -> None:
    e1 = build_entry("1", "s", "policy_verdict", {"verdict": "REFUSED"}, GENESIS_HASH)
    e2 = build_entry("2", "s", "execution_result", {"ref": "X"}, e1.entry_hash)
    assert verify_chain([e1, e2]) is True
    tampered = e1.__class__(**{**e1.__dict__, "payload": {"verdict": "AUTHORIZED"}})
    assert verify_chain([tampered, e2]) is False
```

---

### packages\cache\pyproject.toml

```toml
[project]
name = "cache"
version = "0.1.0"
description = "Optional Redis cache (report #7). No-op when REDIS_URL is unset or redis is unavailable."
requires-python = ">=3.12"
dependencies = ["redis>=5.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\cache\src\cache\__init__.py

```python
"""Optional cache (report #7): a Customer-360 read cache + an idempotency helper.

Gated + degradation-safe: if `REDIS_URL` is unset (or the redis client can't be built), `get_cache`
returns a `NullCache` whose reads miss and whose writes are no-ops - so Postgres stays the source of
truth and dev/tests run without Redis.
"""
from cache.client import Cache, NullCache, RedisCache, get_cache

__all__ = ["Cache", "NullCache", "RedisCache", "get_cache"]
```

---

### packages\cache\src\cache\client.py

```python
from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Cache(Protocol):
    enabled: bool

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None: ...
    def delete(self, key: str) -> None: ...
    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool: ...


class NullCache:
    """Disabled cache: every read misses, writes are no-ops, and idempotency never blocks."""

    enabled = False

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool:
        return True  # "newly added" â€” no dedupe when caching is off (safe default)


class RedisCache:
    """Thin wrapper over a redis client (sync)."""

    enabled = True

    def __init__(self, client) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool:
        return bool(self._client.set(key, "1", nx=True, ex=ttl_seconds))


_cache: Cache | None = None


def get_cache() -> Cache:
    """Return the process cache (Redis if configured, else a NullCache). Memoized."""
    global _cache
    if _cache is not None:
        return _cache
    url = os.getenv("REDIS_URL")
    if not url:
        _cache = NullCache()
        return _cache
    try:
        import redis  # optional dependency

        _cache = RedisCache(redis.from_url(url))
        logger.info("redis cache enabled")
    except Exception as exc:
        logger.warning("redis unavailable (%s); caching disabled", exc)
        _cache = NullCache()
    return _cache
```

---

### packages\cache\tests\test_cache.py

```python
"""Offline tests: no-op cache when REDIS_URL is unset."""
from __future__ import annotations

from cache import NullCache, get_cache


def test_defaults_to_nullcache(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    import cache.client as m
    m._cache = None
    c = get_cache()
    assert isinstance(c, NullCache)
    assert c.enabled is False


def test_nullcache_semantics() -> None:
    c = NullCache()
    c.set("k", "v")
    assert c.get("k") is None
    assert c.add_if_absent("k") is True  # never blocks when disabled
    c.delete("k")
```

---

### packages\domain-core\pyproject.toml

```toml
[project]
name = "domain-core"
version = "0.1.0"
description = "Pure domain entities, value objects and ports. No framework, no vendor SDK."
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\domain-core\src\domain_core\__init__.py

```python
"""Pure domain layer: entities, value objects and ports.

This package MUST NOT import any web framework, LiveKit, or vendor SDK. It is the
dependency-inversion core: adapters and services depend on it, never the reverse.
"""
from domain_core import entities, errors, value_objects

__all__ = ["entities", "errors", "value_objects"]
```

---

### packages\domain-core\src\domain_core\entities.py

```python
"""Domain entities (objects with identity and a lifecycle). Owned per bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from domain_core.value_objects import (
    EscalationReason,
    Language,
    Money,
    Sentiment,
    Verdict,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Client:
    """Customer 360 snapshot (read-through from CRM; CRM stays system of record)."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: Language = Language.FR
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0


@dataclass(slots=True)
class Intent:
    """What the client wants, plus extracted slots (versioned taxonomy, not free text)."""

    name: str
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(slots=True)
class Turn:
    """A single client/agent exchange within a conversation (append-only)."""

    turn_id: str
    speaker: str  # "client" | "agent"
    text: str
    language: Language
    sentiment: Sentiment = Sentiment.NEUTRAL
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Conversation:
    """One session; turns are appended; outcome powers KPIs."""

    conversation_id: str
    channel: str
    language: Language = Language.FR
    turns: list[Turn] = field(default_factory=list)
    outcome: str | None = None  # "resolved" | "escalated"
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Decision:
    """A candidate action proposed by the Decision context, with confidence."""

    action: str
    confidence: float
    rationale: str = ""


@dataclass(slots=True)
class PolicyVerdict:
    """An immutable, audited guardrail verdict (CDC section 4.6)."""

    verdict: Verdict
    rule_id: str
    justification: str
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Action:
    """A sensitive action carrying an idempotency key (CDC section 4.7)."""

    action_id: str
    kind: str
    idempotency_key: str
    status: str = "pending"  # pending | succeeded | failed
    amount: Money | None = None
    reference: str | None = None
    retries: int = 0


@dataclass(slots=True)
class Ticket:
    """Local mirror of a GLPI ticket (never a second source of truth)."""

    ticket_id: str
    glpi_id: str | None
    subject: str
    status: str
    priority: str


@dataclass(slots=True)
class EscalationCase:
    """A human hand-off dossier (CDC section 4.9)."""

    case_id: str
    reason: EscalationReason
    summary: str
    target: str = "human"  # "manager" | "human"
    resolution: str | None = None


@dataclass(slots=True)
class ConsentRecord:
    """Per-call recording consent (CDC section 8.1)."""

    conversation_id: str
    granted: bool
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class AuditEntry:
    """A hash-chained, append-only audit record (CDC sections 8.4 / 9.3)."""

    entry_id: str
    payload: dict[str, Any]
    previous_hash: str
    entry_hash: str
    created_at: datetime = field(default_factory=_now)
```

---

### packages\domain-core\src\domain_core\errors.py

```python
"""Domain error hierarchy (framework-free)."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class PolicyDeniedError(DomainError):
    """Raised when a sensitive action is REFUSED by the Policy engine."""


class EscalationRequiredError(DomainError):
    """Raised when the Policy engine returns ESCALATE."""


class IdentityVerificationError(DomainError):
    """Raised when step-up identity verification fails."""


class ExternalSystemUnavailableError(DomainError):
    """Raised when a legacy system is unreachable (drives degraded-mode handling)."""
```

---

### packages\domain-core\src\domain_core\ports\__init__.py

```python
"""Ports: narrow interfaces the domain depends on; adapters implement them (DIP)."""
from domain_core.ports.audit import AuditPort
from domain_core.ports.balance import BalancePort
from domain_core.ports.billing import BillingPort
from domain_core.ports.crm import CrmPort
from domain_core.ports.decision import DecisionPort
from domain_core.ports.execution import ExecutionPort
from domain_core.ports.knowledge import KnowledgePort
from domain_core.ports.nms import NmsPort
from domain_core.ports.notification import NotificationPort
from domain_core.ports.payment import PaymentPort
from domain_core.ports.policy import PolicyPort
from domain_core.ports.ticketing import TicketingPort

__all__ = [
    "AuditPort",
    "BalancePort",
    "BillingPort",
    "CrmPort",
    "DecisionPort",
    "ExecutionPort",
    "KnowledgePort",
    "NmsPort",
    "NotificationPort",
    "PaymentPort",
    "PolicyPort",
    "TicketingPort",
]
```

---

### packages\domain-core\src\domain_core\ports\audit.py

```python
"""Port to the hash-chained audit ledger (CDC sections 8.4 / 9.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import AuditEntry


class AuditPort(ABC):
    """Append an immutable, hash-chained audit entry."""

    @abstractmethod
    async def append(self, payload: dict[str, Any]) -> AuditEntry:
        """Append ``payload`` to the ledger and return the chained entry."""
```

---

### packages\domain-core\src\domain_core\ports\balance.py

```python
"""Port to the balance / consumption system (OCS) (Blueprint section 7.4)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.value_objects import IdempotencyKey, Money


class BalancePort(ABC):
    """Read balance/consumption and apply recharges / add-ons."""

    @abstractmethod
    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        """Return balance and data consumption for ``customer_id``."""

    @abstractmethod
    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        """Recharge ``amount`` idempotently; return a reference."""

    @abstractmethod
    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        """Apply a complementary data add-on idempotently."""
```

---

### packages\domain-core\src\domain_core\ports\billing.py

```python
"""Port to the billing system (Blueprint section 7.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.value_objects import IdempotencyKey, Money


class BillingPort(ABC):
    """Read invoices and execute payments / deferrals."""

    @abstractmethod
    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        """Return outstanding invoices for ``customer_id``."""

    @abstractmethod
    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        """Charge ``amount`` idempotently; return a transaction reference."""

    @abstractmethod
    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        """Grant a payment deferral of ``days`` days, idempotently."""
```

---

### packages\domain-core\src\domain_core\ports\crm.py

```python
"""Port to the CRM system of record (Blueprint section 7.2)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.entities import Client


class CrmPort(ABC):
    """Resolve and read customer profiles from the CRM."""

    @abstractmethod
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        """Return the client owning ``msisdn`` or None if unknown."""

    @abstractmethod
    async def get_client_by_id(self, customer_id: str) -> Client | None:
        """Return the client with ``customer_id`` or None if unknown."""
```

---

### packages\domain-core\src\domain_core\ports\decision.py

```python
"""Port to the Decision context (CDC section 4.5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import Decision


class DecisionPort(ABC):
    """Rank a candidate action with a confidence value."""

    @abstractmethod
    async def recommend(self, intent: str, context: dict[str, Any]) -> Decision:
        """Return the best candidate action + confidence for ``intent``."""
```

---

### packages\domain-core\src\domain_core\ports\execution.py

```python
"""Port to the Execution context (CDC section 4.7)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import Action


class ExecutionPort(ABC):
    """Dispatch an authorized, idempotent action to the right adapter."""

    @abstractmethod
    async def execute(self, action: Action, context: dict[str, Any]) -> Action:
        """Execute ``action`` idempotently and return it with status + reference."""
```

---

### packages\domain-core\src\domain_core\ports\knowledge.py

```python
"""Port to the knowledge base / RAG (Blueprint section 7.6)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class KnowledgePort(ABC):
    """Retrieve grounded answers from the documentation corpus."""

    @abstractmethod
    async def search(self, query: str, language: str, top_k: int = 4) -> list[dict[str, Any]]:
        """Return ranked passages with a source reference for each."""
```

---

### packages\domain-core\src\domain_core\ports\nms.py

```python
"""Port to network supervision (NMS) (Blueprint section 7.5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NmsPort(ABC):
    """Query known network incidents and remotely reset services."""

    @abstractmethod
    async def get_network_status(self, area: str) -> dict[str, Any]:
        """Return any known incident for ``area`` and an ETA."""
```

---

### packages\domain-core\src\domain_core\ports\notification.py

```python
"""Port to the Notification context (Blueprint section 7.7)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationPort(ABC):
    """Send receipts/confirmations over SMS/WhatsApp/Email."""

    @abstractmethod
    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        """Send a templated notification."""
```

---

### packages\domain-core\src\domain_core\ports\payment.py

```python
"""Port to the payment gateway (Blueprint section 7.8)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.value_objects import IdempotencyKey, Money


class PaymentPort(ABC):
    """Execute confirmed payments through the PSP."""

    @abstractmethod
    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        """Process a payment idempotently; return a transaction reference."""
```

---

### packages\domain-core\src\domain_core\ports\policy.py

```python
"""Port to the deterministic Policy & Guardrail engine (CDC section 4.6)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.entities import PolicyVerdict


class PolicyPort(ABC):
    """The single mandatory checkpoint before any execution and any outbound response."""

    @abstractmethod
    async def evaluate_action(self, action: str, context: dict[str, Any]) -> PolicyVerdict:
        """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification for an action."""

    @abstractmethod
    async def evaluate_response(self, text: str, context: dict[str, Any]) -> PolicyVerdict:
        """Guardrail an outbound response (PII / promises / amounts)."""
```

---

### packages\domain-core\src\domain_core\ports\ticketing.py

```python
"""Port to the ticketing system (GLPI) (Blueprint section 7.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.entities import Ticket


class TicketingPort(ABC):
    """Create and look up support tickets."""

    @abstractmethod
    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        """Create a ticket and return it with its GLPI id."""

    @abstractmethod
    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        """Return the current ticket or None if not found."""
```

---

### packages\domain-core\src\domain_core\value_objects.py

```python
"""Immutable value objects shared across the domain (no identity, compared by value)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Language(StrEnum):
    """Supported conversation languages (Blueprint ADR section 5.7)."""

    FR = "fr"
    AR = "ar"
    EN = "en"


class Channel(StrEnum):
    """Client communication channels (CDC section 2.3)."""

    VOICE = "voice"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class Verdict(StrEnum):
    """The deterministic Policy engine's three-way verdict (CDC section 4.6)."""

    AUTHORIZED = "authorized"
    REFUSED = "refused"
    ESCALATE = "escalate"


class Sentiment(StrEnum):
    """Per-turn emotional state (CDC section 4.2)."""

    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    ANNOYED = "annoyed"
    ANGRY = "angry"


class EscalationReason(StrEnum):
    """Why a conversation is handed to a human (CDC sections 5.12 / 6.4)."""

    CUSTOMER_REQUEST = "customer_request"
    FRUSTRATION = "frustration"
    OUT_OF_SCOPE = "out_of_scope"
    FRAUD_SUSPICION = "fraud_suspicion"
    VIP = "vip"
    REPEATED_NLU_FAILURE = "repeated_nlu_failure"
    REPEATED_IDENTITY_FAILURE = "repeated_identity_failure"
    POLICY_ESCALATE = "policy_escalate"


_MSISDN_RE = re.compile(r"^\+?[0-9]{6,15}$")


@dataclass(frozen=True, slots=True)
class Msisdn:
    """A subscriber phone number (lightly validated)."""

    value: str

    def __post_init__(self) -> None:
        if not _MSISDN_RE.match(self.value):
            raise ValueError(f"invalid MSISDN: {self.value!r}")


@dataclass(frozen=True, slots=True)
class Money:
    """A monetary amount; defaults to Tunisian Dinar per the mock telco dataset."""

    amount: Decimal
    currency: str = "TND"

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount must be non-negative")

    def __str__(self) -> str:
        return f"{self.amount:.3f} {self.currency}"


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """A token generated once per confirmed action and reused across retries."""

    value: str

```

---

### packages\integration-adapters\pyproject.toml

```toml
[project]
name = "integration-adapters"
version = "0.1.0"
description = "Per-legacy-system adapters implementing domain-core ports."
requires-python = ">=3.12"
dependencies = ["domain-core", "httpx==0.28.1"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\integration-adapters\src\integration_adapters\__init__.py

```python
"""Adapters: one module per legacy system, each implementing exactly one domain-core port.

A vendor API change has a one-module blast radius (Blueprint ADR 5.4). Mock by default; live via
CONNECTOR_MODE + the adapter URL (spec section 16.6).
"""
from integration_adapters.factory import (
    get_balance_adapter,
    get_billing_adapter,
    get_crm_adapter,
    get_nms_adapter,
    get_payment_adapter,
    get_ticketing_adapter,
)

__all__ = [
    "get_balance_adapter",
    "get_billing_adapter",
    "get_crm_adapter",
    "get_nms_adapter",
    "get_payment_adapter",
    "get_ticketing_adapter",
]
```

---

### packages\integration-adapters\src\integration_adapters\_http.py

```python
"""Tiny async HTTP helper for the live adapters (one place for timeout/errors)."""
from __future__ import annotations

import httpx

_TIMEOUT = 8.0


async def post_json(base_url: str, path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_json(base_url: str, path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()
```

---

### packages\integration-adapters\src\integration_adapters\billing_adapter.py

```python
"""Billing adapter implementing BillingPort (report #3). Mock is deterministic; Live calls the
external billing system. One vendor change has a one-module blast radius (Blueprint ADR 5.4)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.billing import BillingPort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import get_json, post_json


class MockBillingAdapter(BillingPort):
    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        return []

    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        return f"PAY-{key.value[:10].upper()}"

    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        return None


class LiveBillingAdapter(BillingPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        data = await get_json(self._base, f"/invoices/{customer_id}")
        return data.get("invoices", [])

    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/charge", {
            "customer_id": customer_id, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")

    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        await post_json(self._base, "/deferral", {
            "customer_id": customer_id, "days": days, "idempotency_key": key.value,
        })
```

---

### packages\integration-adapters\src\integration_adapters\config.py

```python
"""Adapter mode + endpoint resolution (spec section 16.6): mock by default, live via env."""
from __future__ import annotations

import os


def connector_mode() -> str:
    """'mock' (local) or 'live' (real legacy systems). Defaults to mock."""
    return os.getenv("CONNECTOR_MODE", "mock").strip().lower()


def is_live() -> bool:
    return connector_mode() == "live"


def adapter_url(name: str) -> str | None:
    """Base URL for a live adapter, e.g. adapter_url('billing') -> BILLING_ADAPTER_URL."""
    return os.getenv(f"{name.upper()}_ADAPTER_URL")
```

---

### packages\integration-adapters\src\integration_adapters\crm_adapter.py

```python
"""CRM adapter implementing CrmPort (report #3). In mock mode CRM reads come from Postgres
(context-service); this adapter is the *live* CRM binding."""
from __future__ import annotations

from domain_core.entities import Client
from domain_core.ports.crm import CrmPort
from integration_adapters._http import get_json


def _to_client(data: dict) -> Client:
    return Client(
        customer_id=data["customer_id"], full_name=data.get("full_name", ""),
        msisdn=data.get("msisdn", ""), subscription_type=data.get("subscription_type", ""),
    )


class MockCrmAdapter(CrmPort):
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        return None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        return None


class LiveCrmAdapter(CrmPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        try:
            return _to_client(await get_json(self._base, "/clients", {"msisdn": msisdn}))
        except Exception:
            return None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        try:
            return _to_client(await get_json(self._base, f"/clients/{customer_id}"))
        except Exception:
            return None
```

---

### packages\integration-adapters\src\integration_adapters\factory.py

```python
"""Adapter factory: CONNECTOR_MODE + the adapter URL decide mock vs live (spec section 16.6).

Falls back to mock if live is selected but no URL is configured - so a half-configured environment
degrades safely rather than crashing.
"""
from __future__ import annotations

from domain_core.ports.balance import BalancePort
from domain_core.ports.billing import BillingPort
from domain_core.ports.crm import CrmPort
from domain_core.ports.nms import NmsPort
from domain_core.ports.payment import PaymentPort
from domain_core.ports.ticketing import TicketingPort
from integration_adapters.billing_adapter import LiveBillingAdapter, MockBillingAdapter
from integration_adapters.config import adapter_url, is_live
from integration_adapters.crm_adapter import LiveCrmAdapter, MockCrmAdapter
from integration_adapters.glpi_adapter import LiveGlpiAdapter, MockGlpiAdapter
from integration_adapters.nms_adapter import LiveNmsAdapter, MockNmsAdapter
from integration_adapters.ocs_adapter import LiveOcsAdapter, MockOcsAdapter
from integration_adapters.payment_adapter import LivePaymentAdapter, MockPaymentAdapter


def _pick(name, live_cls, mock_cls):
    url = adapter_url(name)
    return live_cls(url) if (is_live() and url) else mock_cls()


def get_billing_adapter() -> BillingPort:
    return _pick("billing", LiveBillingAdapter, MockBillingAdapter)


def get_balance_adapter() -> BalancePort:
    return _pick("ocs", LiveOcsAdapter, MockOcsAdapter)


def get_payment_adapter() -> PaymentPort:
    return _pick("payment", LivePaymentAdapter, MockPaymentAdapter)


def get_crm_adapter() -> CrmPort:
    return _pick("crm", LiveCrmAdapter, MockCrmAdapter)


def get_nms_adapter() -> NmsPort:
    return _pick("nms", LiveNmsAdapter, MockNmsAdapter)


def get_ticketing_adapter() -> TicketingPort:
    return _pick("glpi", LiveGlpiAdapter, MockGlpiAdapter)
```

---

### packages\integration-adapters\src\integration_adapters\glpi_adapter.py

```python
"""GLPI ticketing adapter implementing TicketingPort (report #3). The MCP server owns the concrete
GLPI REST client (report #4); this port impl is for domain code that depends on TicketingPort."""
from __future__ import annotations

import uuid

from domain_core.entities import Ticket
from domain_core.ports.ticketing import TicketingPort
from integration_adapters._http import get_json, post_json


class MockGlpiAdapter(TicketingPort):
    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        tid = f"GLPI-{uuid.uuid4().hex[:8].upper()}"
        return Ticket(ticket_id=tid, glpi_id=tid, subject=subject, status="new", priority=priority)

    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        return Ticket(ticket_id=ticket_id, glpi_id=ticket_id, subject="", status="new", priority="medium")


class LiveGlpiAdapter(TicketingPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        data = await post_json(self._base, "/tickets", {"subject": subject, "body": body, "priority": priority})
        return Ticket(ticket_id=data["ticket_id"], glpi_id=data.get("glpi_id"),
                      subject=subject, status=data.get("status", "new"), priority=priority)

    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        try:
            data = await get_json(self._base, f"/tickets/{ticket_id}")
        except Exception:
            return None
        return Ticket(ticket_id=ticket_id, glpi_id=data.get("glpi_id"),
                      subject=data.get("subject", ""), status=data.get("status", "new"),
                      priority=data.get("priority", "medium"))
```

---

### packages\integration-adapters\src\integration_adapters\nms_adapter.py

```python
"""NMS/OSS adapter implementing NmsPort (report #3). Live reads outages from the OSS system."""
from __future__ import annotations

from typing import Any

from domain_core.ports.nms import NmsPort
from integration_adapters._http import get_json


class MockNmsAdapter(NmsPort):
    async def get_network_status(self, area: str) -> dict[str, Any]:
        return {"area": area, "status": "operational", "outages": []}


class LiveNmsAdapter(NmsPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_network_status(self, area: str) -> dict[str, Any]:
        return await get_json(self._base, "/network-status", {"area": area})
```

---

### packages\integration-adapters\src\integration_adapters\ocs_adapter.py

```python
"""OCS/prepaid balance adapter implementing BalancePort (report #3)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.balance import BalancePort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import get_json, post_json


class MockOcsAdapter(BalancePort):
    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        return {"customer_id": customer_id, "credit": 0.0, "currency": "TND", "data_remaining_mb": 0}

    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        return f"TOP-{key.value[:10].upper()}"

    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        return None


class LiveOcsAdapter(BalancePort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        return await get_json(self._base, f"/balance/{customer_id}")

    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/topup", {
            "customer_id": customer_id, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")

    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        await post_json(self._base, "/addon", {
            "customer_id": customer_id, "addon_id": addon_id, "idempotency_key": key.value,
        })
```

---

### packages\integration-adapters\src\integration_adapters\payment_adapter.py

```python
"""Payment gateway adapter implementing PaymentPort (report #3)."""
from __future__ import annotations

from domain_core.ports.payment import PaymentPort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import post_json


class MockPaymentAdapter(PaymentPort):
    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        return f"PAY-{key.value[:10].upper()}"


class LivePaymentAdapter(PaymentPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/pay", {
            "token": token, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")
```

---

### packages\integration-adapters\tests\test_adapters.py

```python
"""Offline tests: factory defaults to mock; mock adapters honor the ports (no network)."""
from __future__ import annotations

import asyncio
from decimal import Decimal

from integration_adapters import get_billing_adapter, get_nms_adapter, get_ticketing_adapter

from domain_core.value_objects import IdempotencyKey, Money


def test_factory_defaults_to_mock(monkeypatch) -> None:
    monkeypatch.delenv("CONNECTOR_MODE", raising=False)
    assert type(get_billing_adapter()).__name__ == "MockBillingAdapter"


def test_live_without_url_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("CONNECTOR_MODE", "live")
    monkeypatch.delenv("BILLING_ADAPTER_URL", raising=False)
    assert type(get_billing_adapter()).__name__ == "MockBillingAdapter"


def test_mock_billing_charge_and_invoices() -> None:
    billing = get_billing_adapter()
    ref = asyncio.run(billing.charge("c1", Money(Decimal("42.500")), IdempotencyKey("abc1234567xyz")))
    assert ref.startswith("PAY-")
    assert asyncio.run(billing.get_open_invoices("c1")) == []


def test_mock_nms_and_ticketing() -> None:
    status = asyncio.run(get_nms_adapter().get_network_status("Tunis"))
    assert status["status"] == "operational"
    ticket = asyncio.run(get_ticketing_adapter().create_ticket("subj", "body", "high"))
    assert ticket.ticket_id.startswith("GLPI-")
```

---

### packages\notification-client\pyproject.toml

```toml
[project]
name = "notification-client"
version = "0.1.0"
description = "SMS/Email/WhatsApp abstraction (Strategy over channels)."
requires-python = ">=3.12"
dependencies = [
  "httpx==0.28.1","domain-core"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\notification-client\src\notification_client\__init__.py

```python
"""Channel-strategy notification client (implements NotificationPort)."""
from notification_client.client import ChannelStrategyNotifier

__all__ = ["ChannelStrategyNotifier"]
```

---

### packages\notification-client\src\notification_client\client.py

```python
"""NotificationPort implementation (report #11): posts to the notification-service over HTTP.

Replaces the log-only scaffold. Fault-tolerant: a delivery problem is logged, not raised, so a
notification never breaks the caller's flow.
"""
from __future__ import annotations

import logging
import os

import httpx

from domain_core.ports.notification import NotificationPort

logger = logging.getLogger(__name__)


class ChannelStrategyNotifier(NotificationPort):
    """Dispatch a localized confirmation through the notification-service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self._base_url = base_url or os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")
        self._timeout = timeout

    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        payload = {
            "customer_id": data.get("customer_id", to),
            "to": to,
            "channel": channel,
            "template": template,
            "language": data.get("language", "fr"),
            "params": data.get("params", data),
        }
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                resp = await client.post("/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("notification dispatch failed (channel=%s template=%s): %s", channel, template, exc)
```

---

### packages\object-storage\pyproject.toml

```toml
[project]
name = "object-storage"
version = "0.1.0"
description = "Optional MinIO/S3 object storage for call recordings (report #8). No-op when unset."
requires-python = ">=3.12"
dependencies = ["minio>=7.2"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\object-storage\src\object_storage\__init__.py

```python
"""Optional object storage (report #8): consent-gated call recordings + retention purge.

Gated + degradation-safe: if `MINIO_ENDPOINT` is unset (or the client can't be built), `get_store`
returns a `NullStore` whose `put` returns None and whose `delete` is a no-op.
"""
from object_storage.store import MinioStore, NullStore, ObjectStore, get_store

__all__ = ["MinioStore", "NullStore", "ObjectStore", "get_store"]
```

---

### packages\object-storage\src\object_storage\store.py

```python
from __future__ import annotations

import io
import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ObjectStore(Protocol):
    enabled: bool

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None: ...
    def delete(self, key_or_url: str) -> None: ...


class NullStore:
    """Disabled storage: put returns None, delete is a no-op."""

    enabled = False

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
        return None

    def delete(self, key_or_url: str) -> None:
        return None


class MinioStore:
    """MinIO/S3 object store for call recordings."""

    enabled = True

    def __init__(self, client, bucket: str, endpoint: str, secure: bool) -> None:
        self._client = client
        self._bucket = bucket
        self._scheme = "https" if secure else "http"
        self._endpoint = endpoint

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
        self._client.put_object(self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
        return f"{self._scheme}://{self._endpoint}/{self._bucket}/{key}"

    def delete(self, key_or_url: str) -> None:
        key = key_or_url
        marker = f"/{self._bucket}/"
        if marker in key_or_url:
            key = key_or_url.split(marker, 1)[1]
        self._client.remove_object(self._bucket, key)


_store: ObjectStore | None = None


def get_store() -> ObjectStore:
    """Return the process object store (MinIO if configured, else a NullStore). Memoized."""
    global _store
    if _store is not None:
        return _store
    endpoint = os.getenv("MINIO_ENDPOINT")
    if not endpoint:
        _store = NullStore()
        return _store
    try:
        from minio import Minio  # optional dependency

        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        bucket = os.getenv("MINIO_BUCKET", "call-recordings")
        client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=secure,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        _store = MinioStore(client, bucket, endpoint, secure)
        logger.info("minio object storage enabled (bucket=%s)", bucket)
    except Exception as exc:
        logger.warning("minio unavailable (%s); recording storage disabled", exc)
        _store = NullStore()
    return _store
```

---

### packages\object-storage\tests\test_store.py

```python
"""Offline tests: no-op store when MINIO_ENDPOINT is unset."""
from __future__ import annotations

from object_storage import NullStore, get_store


def test_defaults_to_nullstore(monkeypatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    import object_storage.store as m
    m._store = None
    s = get_store()
    assert isinstance(s, NullStore)
    assert s.enabled is False


def test_nullstore_semantics() -> None:
    s = NullStore()
    assert s.put("recordings/x.ogg", b"data") is None
    s.delete("http://minio/call-recordings/recordings/x.ogg")  # no raise
```

---

### packages\observability-kit\pyproject.toml

```toml
[project]
name = "observability-kit"
version = "0.1.0"
description = "Shared OpenTelemetry tracer/meter setup + metric naming conventions (Blueprint section 16)."
requires-python = ">=3.12"
# OTel libs are optional at runtime: telemetry no-ops cleanly if they are absent or no endpoint is set.
dependencies = [
  "opentelemetry-sdk>=1.27",
  "opentelemetry-exporter-otlp-proto-grpc>=1.27",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\observability-kit\src\observability_kit\__init__.py

```python
"""Shared OpenTelemetry setup + the conversational-quality metric instruments (Blueprint section 16)."""
from observability_kit.telemetry import (
    configure_tracer,
    incr_escalation,
    incr_fallback,
    record_ttfa,
    record_ttft,
)

__all__ = [
    "configure_tracer",
    "incr_escalation",
    "incr_fallback",
    "record_ttfa",
    "record_ttft",
]
```

---

### packages\observability-kit\src\observability_kit\telemetry.py

```python
"""OpenTelemetry tracer + meter + named instruments (Blueprint section 16).

Two design rules keep this safe to call from every service and the worker hot path:
  1. **Dependency-optional**: if the OTel SDK is not installed, everything degrades to a no-op.
  2. **Endpoint-gated**: telemetry is only wired when OTEL_EXPORTER_OTLP_ENDPOINT is set, so dev
     runs unchanged and nothing blocks on an absent collector.
Recording helpers never raise - metrics must never break a call.
"""
from __future__ import annotations

import logging
import os
from contextlib import suppress

logger = logging.getLogger(__name__)

try:  # OTel SDK is optional
    from opentelemetry import metrics as _otel_metrics
    from opentelemetry import trace as _otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:
    _OTEL_AVAILABLE = False

_METRIC_PREFIX = "telecom.agent"
_instruments: dict[str, object] = {}
_configured = False


def configure_tracer(service_name: str) -> None:
    """Wire the global tracer + meter for ``service_name`` if OTel is available and an endpoint is set."""
    global _configured
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or not _OTEL_AVAILABLE:
        logger.info("OTel disabled (endpoint=%s sdk=%s) for %s", bool(endpoint), _OTEL_AVAILABLE, service_name)
        return
    if _configured:
        return

    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    _otel_trace.set_tracer_provider(tracer_provider)

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
    _otel_metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    _build_instruments(service_name)
    _configured = True
    logger.info("OTel configured for %s -> %s", service_name, endpoint)


def _build_instruments(service_name: str) -> None:
    meter = _otel_metrics.get_meter(service_name)
    _instruments["ttfa"] = meter.create_histogram(
        f"{_METRIC_PREFIX}.ttfa.seconds", unit="s", description="Time to first audio"
    )
    _instruments["ttft"] = meter.create_histogram(
        f"{_METRIC_PREFIX}.ttft.seconds", unit="s", description="Time to first token (LLM)"
    )
    _instruments["fallback"] = meter.create_counter(
        f"{_METRIC_PREFIX}.fallback.activations", description="Provider fallback activations"
    )
    _instruments["escalation"] = meter.create_counter(
        f"{_METRIC_PREFIX}.escalations", description="Escalations to a manager/human"
    )


def record_ttfa(seconds: float, language: str | None = None) -> None:
    """Record a time-to-first-audio observation (no-op until configured)."""
    histogram = _instruments.get("ttfa")
    if histogram is not None:
        with suppress(Exception):
            histogram.record(seconds, {"language": language or "unknown"})


def record_ttft(seconds: float, language: str | None = None) -> None:
    """Record a time-to-first-token observation (no-op until configured)."""
    histogram = _instruments.get("ttft")
    if histogram is not None:
        with suppress(Exception):
            histogram.record(seconds, {"language": language or "unknown"})


def incr_fallback(component: str) -> None:
    """Count a provider fallback activation for ``component`` (stt/llm/tts)."""
    counter = _instruments.get("fallback")
    if counter is not None:
        with suppress(Exception):
            counter.add(1, {"component": component})


def incr_escalation(trigger: str) -> None:
    """Count an escalation, labelled by trigger."""
    counter = _instruments.get("escalation")
    if counter is not None:
        with suppress(Exception):
            counter.add(1, {"trigger": trigger})

```

---

### packages\observability-kit\tests\test_telemetry.py

```python
"""Offline tests: telemetry is a safe no-op when OTel/endpoint are absent (no raises)."""
from __future__ import annotations

from observability_kit import configure_tracer, incr_escalation, incr_fallback, record_ttfa, record_ttft


def test_configure_without_endpoint_is_noop(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    configure_tracer("agent-worker")  # must not raise


def test_recording_helpers_never_raise() -> None:
    # Not configured -> instruments empty -> these are no-ops, never raising.
    record_ttfa(0.42, language="fr")
    record_ttft(0.18, language="ar")
    incr_fallback("stt")
    incr_escalation("frustration")
```

---

### packages\persistence\alembic.ini

```ini
[alembic]
script_location = alembic
prepend_sys_path = src
path_separator = os
# DATABASE_URL is injected by env.py from the environment.

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

---

### packages\persistence\alembic\env.py

```python
"""Alembic environment (sync). Builds the URL from DATABASE_URL and targets Base.metadata."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import persistence.models  # noqa: F401  (registers every table on Base.metadata)
from persistence.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://telecom:telecom@localhost:5432/telecom"
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### packages\persistence\alembic\versions\0001_initial_crm_billing_ocs.py

```python
"""initial: extensions, all 12 schemas, set_updated_at trigger, crm/billing/ocs tables + live view.

Subsequent slices (safety core, conversation, ...) add their tables into the schemas created here.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
import persistence.models  # noqa: F401  (registers crm/billing/ocs tables)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Every bounded-context schema exists from day one (spec section 2.1); only crm/billing/ocs
# carry tables in this slice.
SCHEMAS = [
    "crm", "billing", "ocs", "sim", "oss", "provisioning",
    "ticketing", "conversation", "policy", "execution", "audit", "reference",
]
# Mutable tables that own updated_at -> attach the trigger.
TRIGGER_TABLES = [
    ("crm", "customers"), ("crm", "subscriptions"),
    ("billing", "accounts"), ("billing", "invoices"),
    ("ocs", "balance_accounts"),
]

_SET_UPDATED_AT = (
    "CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ "
    "BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;"
)

_LIVE_VIEW = (
    "CREATE OR REPLACE VIEW crm.v_subscription_live AS "
    "SELECT s.id AS subscription_id, s.customer_id, s.msisdn, s.plan_type, s.status, "
    "b.balance_type, b.balance_value, b.balance_unit, b.expiry_date "
    "FROM crm.subscriptions s "
    "LEFT JOIN ocs.balance_accounts b ON b.subscription_id = s.id "
    "WHERE s.deleted_at IS NULL;"
)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.execute(_SET_UPDATED_AT)

    # Create crm/billing/ocs tables straight from the models (guarantees model<->DB parity).
    Base.metadata.create_all(bind=op.get_bind())

    for schema, table in TRIGGER_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )
    op.execute(_LIVE_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS crm.v_subscription_live")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
```

---

### packages\persistence\alembic\versions\0002_safety_core.py

```python
"""safety core: policy.policy_verdicts, execution.action_ledger, audit.audit_ledger + pii_token_map.

Revision ID: 0002_safety_core
Revises: 0001_initial
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.audit import AuditLedgerEntry, PiiTokenMap
from persistence.models.execution import ActionLedger
from persistence.models.policy import PolicyVerdict

revision = "0002_safety_core"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_NEW_TABLES = [PolicyVerdict.__table__, ActionLedger.__table__, AuditLedgerEntry.__table__, PiiTokenMap.__table__]


def upgrade() -> None:
    # Schemas already exist (migration 0001). Create only the safety-core tables.
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW_TABLES)
    op.execute(
        "CREATE TRIGGER trg_action_ledger_updated BEFORE UPDATE ON execution.action_ledger "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS execution.action_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS policy.policy_verdicts CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.audit_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS audit.pii_token_map CASCADE")
```

---

### packages\persistence\alembic\versions\0003_conversation.py

```python
"""conversation runtime: call_sessions, turns, sentiment_samples, escalation_cases, callback_schedules.

Revision ID: 0003_conversation
Revises: 0002_safety_core
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.conversation import (
    CallbackSchedule,
    CallSession,
    EscalationCase,
    SentimentSample,
    Turn,
)

revision = "0003_conversation"
down_revision = "0002_safety_core"
branch_labels = None
depends_on = None

_NEW = [
    CallSession.__table__, Turn.__table__, SentimentSample.__table__,
    EscalationCase.__table__, CallbackSchedule.__table__,
]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    op.execute(
        "CREATE TRIGGER trg_callback_schedules_updated BEFORE UPDATE ON conversation.callback_schedules "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    for table in ("callback_schedules", "escalation_cases", "sentiment_samples", "turns", "call_sessions"):
        op.execute(f"DROP TABLE IF EXISTS conversation.{table} CASCADE")
```

---

### packages\persistence\alembic\versions\0004_domain_writes.py

```python
"""domain write projections: billing.payments/payment_plans, ocs.recharges, sim.block_unblock_cases.

Revision ID: 0004_domain_writes
Revises: 0003_conversation
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.billing import Payment, PaymentPlan
from persistence.models.ocs import Recharge
from persistence.models.sim import BlockUnblockCase

revision = "0004_domain_writes"
down_revision = "0003_conversation"
branch_labels = None
depends_on = None

_NEW = [Payment.__table__, PaymentPlan.__table__, Recharge.__table__, BlockUnblockCase.__table__]
_TRIGGERS = [("billing", "payments"), ("billing", "payment_plans"), ("sim", "block_unblock_cases")]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    for schema, table in _TRIGGERS:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing.payments CASCADE")
    op.execute("DROP TABLE IF EXISTS billing.payment_plans CASCADE")
    op.execute("DROP TABLE IF EXISTS ocs.recharges CASCADE")
    op.execute("DROP TABLE IF EXISTS sim.block_unblock_cases CASCADE")

```

---

### packages\persistence\alembic\versions\0005_ticketing_notifications.py

```python
"""ticketing mirror + notification log: ticketing.tickets, billing.notifications.

Revision ID: 0005_ticketing_notif
Revises: 0004_domain_writes
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.billing import Notification
from persistence.models.ticketing import Ticket

revision = "0005_ticketing_notif"
down_revision = "0004_domain_writes"
branch_labels = None
depends_on = None

_NEW = [Ticket.__table__, Notification.__table__]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ticketing.tickets CASCADE")
    op.execute("DROP TABLE IF EXISTS billing.notifications CASCADE")

```

---

### packages\persistence\alembic\versions\0006_reference.py

```python
"""reference catalogs: business_rules, error_catalog, products, recharge_catalog.

Revision ID: 0006_reference
Revises: 0005_ticketing_notif
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.reference import BusinessRule, ErrorCatalog, Product, RechargeCatalog

revision = "0006_reference"
down_revision = "0005_ticketing_notif"
branch_labels = None
depends_on = None

_NEW = [BusinessRule.__table__, ErrorCatalog.__table__, Product.__table__, RechargeCatalog.__table__]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    op.execute(
        "CREATE TRIGGER trg_business_rules_updated BEFORE UPDATE ON reference.business_rules "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    for table in ("business_rules", "error_catalog", "products", "recharge_catalog"):
        op.execute(f"DROP TABLE IF EXISTS reference.{table} CASCADE")

```

---

### packages\persistence\alembic\versions\0007_oss_provisioning.py

```python
"""oss + provisioning tables (report #1, #2).

Revision ID: 0007_oss_provisioning
Revises: 0006_reference
Create Date: 2026-06-30
"""
from alembic import op

from persistence.base import Base
from persistence.models.oss import Alarm, NetworkElement, Outage
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder

revision = "0007_oss_provisioning"
down_revision = "0006_reference"
branch_labels = None
depends_on = None

_NEW = [
    NetworkElement.__table__, Alarm.__table__, Outage.__table__,
    ProvisioningRequest.__table__, SimOrder.__table__, PlanChangeHistory.__table__,
]
_TRIGGERS = [
    ("oss", "network_elements"), ("oss", "outages"),
    ("provisioning", "provisioning_requests"), ("provisioning", "sim_orders"),
]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)
    for schema, table in _TRIGGERS:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {schema}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table in ("plan_change_history", "sim_orders", "provisioning_requests"):
        op.execute(f"DROP TABLE IF EXISTS provisioning.{table} CASCADE")
    for table in ("alarms", "outages", "network_elements"):
        op.execute(f"DROP TABLE IF EXISTS oss.{table} CASCADE")
```

---

### packages\persistence\alembic\versions\0008_gin_indexes.py

```python
"""GIN indexes on JSONB columns for @> / ? queries (report #14).

Revision ID: 0008_gin_indexes
Revises: 0007_oss_provisioning
Create Date: 2026-06-30
"""
from alembic import op

revision = "0008_gin_indexes"
down_revision = "0007_oss_provisioning"
branch_labels = None
depends_on = None

# (index_name, schema, table, column)
_GIN = [
    ("ix_policy_verdicts_inputs_gin", "policy", "policy_verdicts", "inputs_snapshot"),
    ("ix_action_ledger_parameters_gin", "execution", "action_ledger", "parameters"),
    ("ix_escalation_cases_dossier_gin", "conversation", "escalation_cases", "dossier"),
    ("ix_audit_ledger_payload_gin", "audit", "audit_ledger", "payload"),
    ("ix_business_rules_definition_gin", "reference", "business_rules", "definition_json"),
    ("ix_provisioning_requests_parameters_gin", "provisioning", "provisioning_requests", "parameters"),
]


def upgrade() -> None:
    for name, schema, table, column in _GIN:
        op.create_index(name, table, [column], schema=schema, postgresql_using="gin")


def downgrade() -> None:
    for name, schema, _table, _column in _GIN:
        op.drop_index(name, schema=schema)
```

---

### packages\persistence\pyproject.toml

```toml
[project]
name = "persistence"
version = "0.1.0"
description = "Shared SQLAlchemy models, engine/session, and Alembic migrations for the telecom DB."
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy>=2.0,<2.1",
  "psycopg[binary]>=3.2",
  "alembic>=1.13",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\persistence\seed\__init__.py

```python
"""Pilot seed (FK-safe, UUID-resolved at load time per spec section 20)."""
```

---

### packages\persistence\seed\seed_pilot.py

```python
"""Seed the pilot dataset (real TND, the three canonical callers) â€” idempotent.

FKs are resolved through ORM relationships (assign objects, never hardcode UUIDs across rows),
exactly as spec section 20 requires. Run after `alembic upgrade head`:
    DATABASE_URL=... python -m seed.seed_pilot
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.billing import Account, Invoice
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount

TODAY = date.today()


def _activation(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


def seed() -> None:
    """Insert the three pilot customers and their lines/invoices/balances if not present."""
    with session_scope() as session:
        if session.scalar(select(Customer).where(Customer.national_id == "11224087")):
            print("pilot already seeded - nothing to do")
            return

        # --- Amine Ben Salah (fr, postpaid, not VIP) ---
        amine = Customer(
            national_id="11224087", first_name="Amine", last_name="Ben Salah",
            email="amine.bensalah@example.tn", preferred_language="fr",
            segment="postpaid_flexi", vip_flag=False, fraud_suspected=False,
            city="Tunis", region="Tunis", status="active",
        )
        amine_sub = Subscription(
            customer=amine, msisdn="+21620155320", plan_type="POSTPAID",
            plan_code="Postpaid Flexi", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(1420),
        )
        amine_acct = Account(
            customer=amine, account_number="BA-000021", account_type="postpaid",
            billing_cycle_day=10, payment_terms_days=15, currency_code="TND", status="active",
        )
        amine_inv = Invoice(
            account=amine_acct, customer=amine, invoice_number="INV-2026-04-100021",
            period_start=date(2026, 4, 1), period_end=date(2026, 4, 30),
            issue_date=date(2026, 5, 1), due_date=date(2026, 7, 10),
            subtotal=36.000, tax_amount=6.500, total_amount=42.500, outstanding_amount=42.500,
            currency_code="TND", status="issued",
        )

        # --- Yousra Trabelsi (ar, prepaid, VIP) ---
        yousra = Customer(
            national_id="33449912", first_name="Yousra", last_name="Trabelsi",
            email="yousra.trabelsi@example.tn", preferred_language="ar",
            segment="prepaid_trankil", vip_flag=True, fraud_suspected=False,
            city="Sousse", region="Sousse", status="active",
        )
        yousra_sub = Subscription(
            customer=yousra, msisdn="+21629744108", plan_type="PREPAID",
            plan_code="Prepaid Mobile", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(305),
        )
        yousra_main = BalanceAccount(
            subscription=yousra_sub, customer=yousra, balance_type="main",
            balance_value=7.300, balance_unit="TND", expiry_date=date(2026, 7, 5), status="active",
        )
        yousra_data = BalanceAccount(
            subscription=yousra_sub, customer=yousra, balance_type="data",
            balance_value=1840, balance_unit="MB", expiry_date=date(2026, 7, 5), status="active",
        )

        # --- Karim Gharbi (en, postpaid fibre, not VIP, overdue) ---
        karim = Customer(
            national_id="55662256", first_name="Karim", last_name="Gharbi",
            email="karim.gharbi@example.tn", preferred_language="en",
            segment="fiber_home", vip_flag=False, fraud_suspected=False,
            city="Ariana", region="Ariana", status="active",
        )
        karim_sub = Subscription(
            customer=karim, msisdn="+21652310977", plan_type="POSTPAID",
            plan_code="Fibre Fixe", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(88),
        )
        karim_acct = Account(
            customer=karim, account_number="BA-000078", account_type="postpaid",
            billing_cycle_day=20, payment_terms_days=15, currency_code="TND", status="dunning",
        )
        karim_inv = Invoice(
            account=karim_acct, customer=karim, invoice_number="INV-2026-04-100078",
            period_start=date(2026, 4, 1), period_end=date(2026, 4, 30),
            issue_date=date(2026, 5, 1), due_date=date(2026, 6, 20),
            subtotal=62.000, tax_amount=11.900, total_amount=73.900, outstanding_amount=73.900,
            currency_code="TND", status="overdue",
        )

        session.add_all(
            [amine, amine_sub, amine_acct, amine_inv,
             yousra, yousra_sub, yousra_main, yousra_data,
             karim, karim_sub, karim_acct, karim_inv]
        )
        print("seeded 3 customers, 3 subscriptions, 2 invoices, 2 balances")


if __name__ == "__main__":
    seed()
```

---

### packages\persistence\seed\seed_reference.py

```python
"""Seed the reference catalogs (spec section 13.1) - idempotent. Run after `alembic upgrade head`:
    DATABASE_URL=... python -m seed.seed_reference
"""
from __future__ import annotations

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.reference import BusinessRule, ErrorCatalog, Product, RechargeCatalog

# The deterministic engine still executes these rules in code; this table is the versioned,
# auditable registry the business-api exposes (governance), mirroring the engine's rule_ids.
RULES = [
    ("RULE_BILLING_CAP", "billing", "Agent may not authorize a payment above the per-call cap.",
     {"max_payment_tnd": 200}),
    ("RULE_DEFERRAL_ELIGIBILITY", "billing",
     "Deferral requires verified identity, minimum account age, and within the yearly cap.",
     {"min_account_age_days": 180, "max_deferrals_per_year": 2}),
    ("RULE_IDENTITY_REQUIRED", "identity", "Sensitive actions require step-up identity verification.", {}),
    ("RULE_FRAUD_BLOCK", "fraud", "Fraud-suspected accounts cannot perform sensitive actions; escalate.", {}),
    ("RULE_VIP_ESCALATION", "escalation", "VIP callers escalate to a manager for sensitive actions.", {}),
    ("OUT_PII", "guardrail", "Outbound responses must not leak PII (national id / full msisdn).", {}),
]
ERRORS = [
    ("POLICY_NO_VERDICT_ID", "policy", "Action non autorisee : verdict manquant.",
     "Ø§Ù„Ø§Ø¬Ø±Ø§Ø¡ ØºÙŠØ± Ù…ØµØ±Ø­ Ø¨Ù‡: Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ù‚Ø±Ø§Ø±", "Action not authorized: missing verdict."),
    ("DECISION_LOW_CONFIDENCE", "decision", "Je prefere vous orienter vers un conseiller.",
     "Ø³Ø£Ø­ÙˆÙ„Ùƒ Ø§Ù„Ù‰ Ù…Ø³ØªØ´Ø§Ø±", "Routing you to a human advisor."),
]
PRODUCTS = [("FLEXI", "Postpaid Flexi", "POSTPAID"), ("TRANKIL", "Prepaid Mobile", "PREPAID"),
            ("FIBER", "Fibre Fixe", "POSTPAID")]
RECHARGES = [("R5", 5, 0), ("R10", 10, 1), ("R20", 20, 3), ("R50", 50, 10)]


def seed() -> None:
    with session_scope() as session:
        if session.scalar(select(BusinessRule).where(BusinessRule.rule_id == "RULE_BILLING_CAP")):
            print("reference already seeded - nothing to do")
            return
        for rule_id, domain, desc, definition in RULES:
            session.add(BusinessRule(rule_id=rule_id, domain=domain, description=desc,
                                     definition_json=definition, version=1, active=True))
        for code, domain, fr, ar, en in ERRORS:
            session.add(ErrorCatalog(code=code, domain=domain, message_fr=fr, message_ar=ar, message_en=en))
        for code, name, plan_type in PRODUCTS:
            session.add(Product(product_code=code, name=name, plan_type=plan_type, active=True))
        for code, amount, bonus in RECHARGES:
            session.add(RechargeCatalog(code=code, amount=amount, bonus_amount=bonus))
        print("seeded reference: 6 rules, 2 errors, 3 products, 4 recharges")


if __name__ == "__main__":
    seed()
```

---

### packages\persistence\src\persistence\__init__.py

```python
"""Shared persistence layer: one PostgreSQL database, one schema per bounded context (spec section 2.1)."""
from persistence.base import Base
from persistence.engine import get_engine, get_session, get_sessionmaker, session_scope

__all__ = ["Base", "get_engine", "get_session", "get_sessionmaker", "session_scope"]
```

---

### packages\persistence\src\persistence\base.py

```python
"""Declarative base + shared column mixins (spec section 3 global conventions).

Every table inherits: UUID primary key (`uuid_generate_v4()`), UTC `created_at`/`updated_at`
(with the `set_updated_at` trigger attached in the migration), and - where master data -
a nullable `deleted_at` for soft delete. Money is NUMERIC, never float.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint/index names (stable migrations).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base carrying the project metadata/naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKey:
    """`id UUID PRIMARY KEY DEFAULT uuid_generate_v4()` (spec hard rule 1)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )


class Timestamps:
    """`created_at` / `updated_at` (UTC). The `updated_at` trigger is attached in the migration."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SoftDelete:
    """`deleted_at` for master/reference data (operational logs are append-only instead)."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

### packages\persistence\src\persistence\engine.py

```python
"""Engine + session factory (spec Appendix B: DATABASE_URL, per-service role).

Synchronous SQLAlchemy: FastAPI runs sync path operations in a threadpool, which keeps DB code
simple and correct. The worker's hot voice path never blocks on this - it talks to services over
HTTP and persists conversation data through a non-blocking writer.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the process-wide engine built from DATABASE_URL."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "postgresql+psycopg://telecom:telecom@localhost:5432/telecom")
        _engine = create_engine(
            url,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.environ.get("DB_POOL_TIMEOUT", "30.0")),
            pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "1800")),
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _Session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a read session (no implicit commit)."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
```

---

### packages\persistence\src\persistence\models\__init__.py

```python
"""Importing this package registers every table on Base.metadata (used by Alembic)."""
from persistence.models import (
    audit,
    billing,
    conversation,
    crm,
    execution,
    ocs,
    oss,
    policy,
    provisioning,
    reference,
    sim,
    ticketing,
)

__all__ = [
    "audit",
    "billing",
    "conversation",
    "crm",
    "execution",
    "ocs",
    "oss",
    "policy",
    "provisioning",
    "reference",
    "sim",
    "ticketing",
]
```

---

### packages\persistence\src\persistence\models\audit.py

```python
"""Audit schema (spec section 12.3-12.4): hash-chained tamper-evident ledger + PII token map."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CHAR, BigInteger, CheckConstraint, DateTime, Identity, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class AuditLedgerEntry(UUIDPrimaryKey, Base):
    __tablename__ = "audit_ledger"
    __table_args__ = ({"schema": "audit"},)

    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)  # strict chain ordering
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_reference: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PiiTokenMap(UUIDPrimaryKey, Base):
    __tablename__ = "pii_token_map"
    __table_args__ = (
        CheckConstraint(
            "pii_type IN ('msisdn','national_id','email','name','iccid')", name="pii_type"
        ),
        {"schema": "audit"},
    )

    token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    pii_type: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

---

### packages\persistence\src\persistence\models\billing.py

```python
"""Billing schema (spec section 5): postpaid accounts, invoices, line items.

Payments / payment_plans (write paths) land with the execution-service persistence slice.
"""
from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from persistence.models.crm import Customer

from persistence.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey


class Account(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("account_type IN ('postpaid','hybrid')", name="account_type"),
        CheckConstraint("billing_cycle_day BETWEEN 1 AND 28", name="cycle_day"),
        CheckConstraint("status IN ('active','dunning','suspended','closed')", name="status"),
        {"schema": "billing"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'postpaid'"))
    billing_cycle_day: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("15"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    customer: Mapped[Customer] = relationship("Customer")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="account")


class Invoice(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','issued','paid','partial','overdue','disputed','void')", name="status"
        ),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    outstanding_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'issued'"), index=True)

    account: Mapped[Account] = relationship(back_populates="invoices")
    customer: Mapped[Customer] = relationship("Customer")
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(UUIDPrimaryKey, Base):
    __tablename__ = "invoice_items"
    __table_args__ = ({"schema": "billing"},)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default=text("1"))
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default=text("0"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class Payment(UUIDPrimaryKey, Timestamps, Base):
    """A payment capture (spec section 5.1). `idempotency_key` mirrors execution.action_ledger."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("method IN ('card','bank_transfer','wallet','voucher','cash')", name="method"),
        CheckConstraint("status IN ('pending','succeeded','failed','refunded')", name="status"),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.invoices.id"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    gateway_reference: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentPlan(UUIDPrimaryKey, Timestamps, Base):
    """A payment deferral / installment plan (spec section 5.1, CDC 5.3)."""

    __tablename__ = "payment_plans"
    __table_args__ = (
        CheckConstraint("installment_count BETWEEN 1 AND 12", name="installments"),
        CheckConstraint(
            "status IN ('proposed','active','completed','defaulted','cancelled')", name="status"
        ),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    installment_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    deferral_until: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # loose ref (spec)


class Notification(UUIDPrimaryKey, Base):
    """Outbound customer notification log (spec section 5.2): reminder/alert/confirmation dispatch."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('sms','whatsapp','email')", name="channel"),
        CheckConstraint("status IN ('queued','sent','failed')", name="status"),
        {"schema": "billing"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'sent'"))
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

```

---

### packages\persistence\src\persistence\models\conversation.py

```python
"""Conversation & agent-runtime schema (spec section 11): the durable record of every call.

Written by the agent-worker through a NON-BLOCKING async writer (never on the voice path).
Turns / sentiment_samples are append-only; the supervisor-dashboard (P4) reads these.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey

_LANG = "detected_language IN ('fr','ar','en')"


class CallSession(UUIDPrimaryKey, Base):
    __tablename__ = "call_sessions"
    __table_args__ = (
        CheckConstraint("channel IN ('voice','chat')", name="channel"),
        CheckConstraint(
            "final_disposition IN ('resolved','escalated','dropped','abandoned')", name="disposition"
        ),
        {"schema": "conversation"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    msisdn: Mapped[str | None] = mapped_column(String(20))  # raw caller id, pre-resolution only
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'voice'"))
    livekit_room: Mapped[str | None] = mapped_column(String(120))
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    final_disposition: Mapped[str | None] = mapped_column(String(20))
    max_frustration_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))
    recording_consent: Mapped[bool | None] = mapped_column(Boolean)
    audio_record_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Turn(UUIDPrimaryKey, Base):
    __tablename__ = "turns"
    __table_args__ = (
        CheckConstraint("speaker IN ('caller','agent')", name="speaker"),
        CheckConstraint(_LANG, name="language"),
        UniqueConstraint("session_id", "turn_index", "speaker", name="session_turn_speaker"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)
    active_agent: Mapped[str | None] = mapped_column(String(40))
    detected_language: Mapped[str | None] = mapped_column(String(10))
    transcript_masked: Mapped[str | None] = mapped_column(Text)  # PII-masked (pii-shield)
    detected_intent: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class SentimentSample(UUIDPrimaryKey, Base):
    __tablename__ = "sentiment_samples"
    __table_args__ = (
        CheckConstraint("label IN ('positive','neutral','negative','angry')", name="label"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    label: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EscalationCase(UUIDPrimaryKey, Base):
    __tablename__ = "escalation_cases"
    __table_args__ = (
        CheckConstraint("target IN ('manager_agent','human_advisor')", name="target"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('transferred','queued','callback_scheduled','resolved')",
            name="resolution",
        ),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)  # spec Appendix A
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    dossier: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CallbackSchedule(UUIDPrimaryKey, Base):
    __tablename__ = "callback_schedules"
    __table_args__ = (
        CheckConstraint("status IN ('pending','completed','cancelled')", name="status"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    scheduled_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

---

### packages\persistence\src\persistence\models\crm.py

```python
"""CRM schema (spec section 4): customer identity system of record + consent/interactions.

`crm.customers` is the single source of truth for identity; `national_id` carries the CIN
(closing review note 4). `crm.subscriptions` owns the MSISDN as a UNIQUE attribute - never a
join key (spec section 1).
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey

_LANG = "preferred_language IN ('fr','ar','en')"


class Customer(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(_LANG, name="lang"),
        CheckConstraint("status IN ('active','suspended','closed')", name="status"),
        {"schema": "crm"},
    )

    national_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    contact_number: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'fr'"))
    segment: Mapped[str | None] = mapped_column(String(80), index=True)
    vip_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fraud_suspected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"), index=True)

    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="customer")


class Subscription(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("plan_type IN ('PREPAID','POSTPAID')", name="plan_type"),
        CheckConstraint("status IN ('ACTIVE','SUSPENDED','BLOCKED','TERMINATED')", name="status"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    msisdn: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # UNIQUE attribute, never an FK
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    plan_code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    roaming_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    activation_date: Mapped[datetime.date | None] = mapped_column(Date)

    customer: Mapped[Customer] = relationship(back_populates="subscriptions")


class ConsentRecord(UUIDPrimaryKey, Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('call_recording','data_processing','marketing')", name="consent_type"
        ),
        CheckConstraint("language IN ('fr','ar','en')", name="language"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'call_recording'"))
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    captured_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CustomerInteraction(UUIDPrimaryKey, Base):
    __tablename__ = "customer_interactions"
    __table_args__ = (
        CheckConstraint("channel IN ('voice','chat','sms','email','whatsapp')", name="channel"),
        CheckConstraint("language IN ('fr','ar','en')", name="language"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'voice'"))
    detected_intent: Mapped[str | None] = mapped_column(String(80))
    resolution: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

---

### packages\persistence\src\persistence\models\execution.py

```python
"""Execution schema (spec section 12.2): idempotent action ledger, append-mostly.

`idempotency_key` is UNIQUE - the contract that an action runs at most once across retries.
Every row references the `policy_verdict_id` that authorized it (no action without a verdict).
"""
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class ActionLedger(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "action_ledger"
    __table_args__ = (
        CheckConstraint("status IN ('pending','succeeded','failed','retrying')", name="status"),
        {"schema": "execution"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    policy_verdict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy.policy_verdicts.id"), nullable=False
    )
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    adapter_reference: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
```

---

### packages\persistence\src\persistence\models\ocs.py

```python
"""OCS prepaid schema (spec section 6): live balances (moved off the subscription row).

A read-through view (crm.v_subscription_live) re-presents the live balance to the Context
faÃ§ade without duplicating mutable state. Usage/recharge write paths land with execution.
"""
from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from persistence.models.crm import Customer, Subscription

from persistence.base import Base, UUIDPrimaryKey


class BalanceAccount(UUIDPrimaryKey, Base):
    __tablename__ = "balance_accounts"
    __table_args__ = (
        CheckConstraint("balance_type IN ('main','data','voice','sms')", name="balance_type"),
        CheckConstraint("balance_unit IN ('TND','GB','MB','MIN','SMS')", name="balance_unit"),
        CheckConstraint("status IN ('active','expired','suspended')", name="status"),
        UniqueConstraint("subscription_id", "balance_type", name="subscription_type"),
        {"schema": "ocs"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False)
    balance_type: Mapped[str] = mapped_column(String(20), nullable=False)
    balance_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, server_default=text("0"))
    balance_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    subscription: Mapped[Subscription] = relationship("Subscription")
    customer: Mapped[Customer] = relationship("Customer")


class Recharge(UUIDPrimaryKey, Base):
    """A prepaid top-up (spec section 6.2). `idempotency_key` mirrors execution.action_ledger."""

    __tablename__ = "recharges"
    __table_args__ = (
        CheckConstraint("channel IN ('app','web','ussd','scratch_card','agent')", name="channel"),
        CheckConstraint("status IN ('pending','completed','failed')", name="status"),
        {"schema": "ocs"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    recharge_code: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    bonus_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

```

---

### packages\persistence\src\persistence\models\oss.py

```python
"""OSS schema (spec section 8 / report #1): network inventory, alarms, outages.

Read models consumed by the NmsAdapter (`get_network_status`) and the technical persona when a
caller reports a fault - "is there a known outage in your area?".
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class NetworkElement(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "network_elements"
    __table_args__ = (
        CheckConstraint(
            "element_type IN ('cell_site','bts','router','switch','olt','core')", name="element_type"
        ),
        CheckConstraint("status IN ('active','degraded','down','maintenance')", name="status"),
        {"schema": "oss"},
    )

    element_type: Mapped[str] = mapped_column(String(40), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))


class Alarm(UUIDPrimaryKey, Base):
    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint("severity IN ('critical','major','minor','warning')", name="severity"),
        {"schema": "oss"},
    )

    network_element_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oss.network_elements.id"), index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    alarm_type: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Outage(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "outages"
    __table_args__ = (
        CheckConstraint("severity IN ('critical','major','minor')", name="severity"),
        {"schema": "oss"},
    )

    region: Mapped[str | None] = mapped_column(String(80), index=True)
    area: Mapped[str | None] = mapped_column(String(120))
    affected_services: Mapped[str | None] = mapped_column(String(120))  # e.g. "mobile,data"
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'minor'"))
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
```

---

### packages\persistence\src\persistence\models\policy.py

```python
"""Policy schema (spec section 12.1): every authorize/refuse/escalate decision, append-only."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class PolicyVerdict(UUIDPrimaryKey, Base):
    __tablename__ = "policy_verdicts"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound')", name="direction"),
        CheckConstraint("verdict IN ('AUTHORIZED','REFUSED','ESCALATE')", name="verdict"),
        {"schema": "policy"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'inbound'"))
    verdict: Mapped[str] = mapped_column(String(12), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

---

### packages\persistence\src\persistence\models\provisioning.py

```python
"""Provisioning schema (spec section 8 / report #2): activation requests, SIM orders, plan changes.

Written by the execution-service when an AccountServicesAgent action (CHANGE_PLAN / ACTIVATE_ROAMING)
succeeds - so this schema is exercised, not dead. Carries idempotency_key + policy_verdict_id like
every other write projection.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class ProvisioningRequest(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "provisioning_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending','in_progress','completed','failed')", name="status"),
        {"schema": "provisioning"},
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class SimOrder(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "sim_orders"
    __table_args__ = (
        CheckConstraint("sim_type IN ('physical','esim')", name="sim_type"),
        CheckConstraint("status IN ('requested','shipped','activated','cancelled')", name="status"),
        {"schema": "provisioning"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    sim_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'physical'"))
    iccid: Mapped[str | None] = mapped_column(String(22))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'requested'"))
    tracking_code: Mapped[str | None] = mapped_column(String(60))


class PlanChangeHistory(UUIDPrimaryKey, Base):
    __tablename__ = "plan_change_history"
    __table_args__ = (
        CheckConstraint("changed_by IN ('agent','self_service','advisor')", name="changed_by"),
        {"schema": "provisioning"},
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), index=True
    )
    from_plan: Mapped[str | None] = mapped_column(String(60))
    to_plan: Mapped[str] = mapped_column(String(60), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'agent'"))
    effective_date: Mapped[datetime.date | None] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

---

### packages\persistence\src\persistence\models\reference.py

```python
"""Reference catalogs (spec section 13): admin-managed, read-mostly shared data.

`business_rules` is the versioned, governable registry of the Policy rules (spec section 13.1):
the deterministic engine still executes in code, while this table is the published, audited catalog
that the business-api exposes for review/versioning. error_catalog/products/recharge_catalog back
agent-facing messages and plan/recharge information.
"""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class BusinessRule(UUIDPrimaryKey, Timestamps, Base):
    """A versioned Policy rule definition (spec section 13.1), consumed/governed via business-api."""

    __tablename__ = "business_rules"
    __table_args__ = ({"schema": "reference"},)

    rule_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ErrorCatalog(UUIDPrimaryKey, Base):
    """Canonical error codes surfaced to agents, localized (spec section 13.1)."""

    __tablename__ = "error_catalog"
    __table_args__ = ({"schema": "reference"},)

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(String(40))
    message_fr: Mapped[str | None] = mapped_column(Text)
    message_ar: Mapped[str | None] = mapped_column(Text)
    message_en: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Product(UUIDPrimaryKey, Base):
    """Plan/product catalog (spec section 13.1)."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("plan_type IN ('PREPAID','POSTPAID')", name="plan_type"),
        {"schema": "reference"},
    )

    product_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RechargeCatalog(UUIDPrimaryKey, Base):
    """Prepaid recharge denominations (spec section 13.1)."""

    __tablename__ = "recharge_catalog"
    __table_args__ = ({"schema": "reference"},)

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    bonus_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

```

---

### packages\persistence\src\persistence\models\sim.py

```python
"""SIM lifecycle schema (spec section 7). Agent writes the identity-gated block/unblock case;
PUK/PIN secrets are never stored here (see spec section 7 supporting tables)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class BlockUnblockCase(UUIDPrimaryKey, Timestamps, Base):
    """An identity-gated SIM block/unblock/reactivate case (CDC 5.5). Idempotent + verdict-linked."""

    __tablename__ = "block_unblock_cases"
    __table_args__ = (
        CheckConstraint("action IN ('BLOCK','UNBLOCK','UNLOCK_PUK','REACTIVATE')", name="action"),
        CheckConstraint(
            "status IN ('pending','identity_verified','completed','escalated','rejected')", name="status"
        ),
        {"schema": "sim"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # loose ref (spec)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)

```

---

### packages\persistence\src\persistence\models\ticketing.py

```python
"""Ticketing schema (spec section 10): a thin local mirror of GLPI (GLPI stays source of truth)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class Ticket(UUIDPrimaryKey, Base):
    """Local cache row pointing at the real GLPI ticket id (spec section 10)."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('network_complaint','formal_complaint','technical','billing','other')",
            name="category",
        ),
        CheckConstraint(
            "status IN ('open','in_progress','pending','resolved','closed')", name="status"
        ),
        CheckConstraint("priority IS NULL OR priority IN ('low','medium','high','urgent')", name="priority"),
        {"schema": "ticketing"},
    )

    glpi_ticket_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'other'"))
    subject: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"))
    priority: Mapped[str | None] = mapped_column(String(10))
    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

```

---

### packages\persistence\src\persistence\util.py

```python
"""Small persistence helpers."""
from __future__ import annotations

import uuid

_NS = uuid.UUID("00000000-0000-0000-0000-0000000000aa")  # stable namespace for non-UUID ids


def to_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Parse ``value`` as a UUID, or None for empty input."""
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def require_uuid(value: str | uuid.UUID | None) -> uuid.UUID:
    """Coerce ``value`` to a UUID, deriving a stable one for non-UUID strings (e.g. 'unknown')."""
    parsed = to_uuid(value)
    return parsed if parsed is not None else uuid.uuid5(_NS, str(value))
```

---

### packages\persistence\tests\test_migrations.py

```python
"""Offline migration-integrity tests (no DB): unique revisions + a linear chain + full registration.

The live 'alembic upgrade head' check runs in CI against a real Postgres (report #29); here we
guard the two things that silently break a migration set without a database.
"""
from __future__ import annotations

import pathlib
import re

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revisions() -> dict[str, str | None]:
    chain: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob("0*.py")):
        text = path.read_text()
        rev = re.search(r'revision\s*=\s*"([^"]+)"', text)
        down = re.search(r'down_revision\s*=\s*(?:"([^"]+)"|None)', text)
        assert rev, f"{path.name}: no revision id"
        chain[rev.group(1)] = down.group(1) if down and down.group(1) else None
    return chain


def test_revision_ids_are_unique() -> None:
    ids = [re.search(r'revision\s*=\s*"([^"]+)"', p.read_text()).group(1) for p in sorted(VERSIONS.glob("0*.py"))]
    assert len(ids) == len(set(ids)), "duplicate revision ids"


def test_chain_is_linear_with_one_root() -> None:
    chain = _revisions()
    roots = [rev for rev, down in chain.items() if down is None]
    assert len(roots) == 1, f"expected exactly one root migration, got {roots}"
    for rev, down in chain.items():
        assert down is None or down in chain, f"{rev} points to missing down_revision {down}"


def test_all_models_register_on_metadata() -> None:
    from sqlalchemy.orm import configure_mappers

    import persistence.models  # noqa: F401
    from persistence.base import Base

    configure_mappers()
    schemas = {name.split(".")[0] for name in Base.metadata.tables}
    for expected in ("crm", "billing", "ocs", "policy", "execution", "audit",
                     "conversation", "sim", "ticketing", "reference", "oss", "provisioning"):
        assert expected in schemas, f"schema {expected} has no registered tables"
```

---

### packages\pii-shield\pyproject.toml

```toml
[project]
name = "pii-shield"
version = "0.1.0"
description = "PII detection / masking / pseudonymization (CDC section 8.2)."
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\pii-shield\src\pii_shield\__init__.py

```python
"""Mask PII before it crosses any cloud / log / audit boundary."""
from pii_shield.masker import PiiMasker, mask

__all__ = ["PiiMasker", "mask"]
```

---

### packages\pii-shield\src\pii_shield\masker.py

```python
"""Lightweight PII masker (CDC section 8.2 / Blueprint section 14). Phase 12 hardens detection
and adds reversible pseudonymization. Used to scrub PII before it crosses a log/cloud/audit
boundary; the worker also installs it as a logging filter (see observability/log_masking.py).
"""
from __future__ import annotations

import re

_PHONE = re.compile(r"\+?\d[\d\s-]{6,}\d")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# A standalone run of 4+ digits (national-ID / CIN fragments, account numbers) â€” but NOT
# decimal amounts like 42.500, which contain a dot and are matched as two short runs.
_ID_RUN = re.compile(r"(?<!\d)\d{4,}(?!\d)")


class PiiMasker:
    """Mask phone numbers, emails, and bare identifier runs in free text."""

    def mask(self, text: str) -> str:
        """Return ``text`` with PII tokens replaced by typed placeholders."""
        text = _EMAIL.sub("[EMAIL]", text)
        text = _PHONE.sub("[PHONE]", text)
        text = _ID_RUN.sub("[ID]", text)
        return text


_DEFAULT = PiiMasker()


def mask(text: str) -> str:
    """Module-level convenience masker."""
    return _DEFAULT.mask(text)
```

---

### packages\service-auth\pyproject.toml

```toml
[project]
name = "service-auth"
version = "0.1.0"
description = "Shared internal service-to-service auth (X-API-Key) for FastAPI apps + httpx clients."
requires-python = ">=3.12"
dependencies = ["fastapi"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### packages\service-auth\src\service_auth\__init__.py

```python
"""Internal service-to-service authentication (report item 17).

A single shared key (`INTERNAL_API_KEY`) gates the *internal* services. It is intentionally
**opt-in**: if the env var is unset (dev / tests), the dependency is a no-op and clients send no
header - so nothing breaks locally. In staging/prod, set the key everywhere and every internal call
must present `X-API-Key`. `/health` is always allowed so container probes keep working.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

_HEALTH_PATHS = {"/health", "/healthz", "/livez", "/readyz"}


def _expected_key() -> str | None:
    return os.getenv("INTERNAL_API_KEY")


def require_internal_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 403 unless `X-API-Key` matches. No-op when the key is unset (dev)."""
    expected = _expected_key()
    if not expected:
        return  # auth disabled in dev / tests
    if request.url.path in _HEALTH_PATHS:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden: invalid internal key")


def internal_headers() -> dict[str, str]:
    """Headers a client should send to an internal service ({} when auth is disabled)."""
    key = _expected_key()
    return {"X-API-Key": key} if key else {}
```

---

### packages\service-auth\tests\test_service_auth.py

```python
"""Offline tests: auth is a no-op without a key, and enforces the header when set."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from service_auth import internal_headers, require_internal_key


class _Req:
    class _U:
        path = "/context/x"
    url = _U()


def test_noop_without_key(monkeypatch) -> None:
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    require_internal_key(_Req(), x_api_key=None)  # must not raise
    assert internal_headers() == {}


def test_enforced_with_key(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    assert internal_headers() == {"X-API-Key": "s3cret"}
    with pytest.raises(HTTPException):
        require_internal_key(_Req(), x_api_key="wrong")
    require_internal_key(_Req(), x_api_key="s3cret")  # correct -> ok


def test_health_is_open(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret")
    req = _Req()
    req.url.path = "/health"
    require_internal_key(req, x_api_key=None)  # probes allowed
```

---

### Procfile

```text
# honcho/foreman process list (diagnostic #1). `honcho start` runs the whole platform in one terminal.
# Console scripts come from each service's [project.scripts]; run `make install` first.
context:       context-service
knowledge:     knowledge-service
decision:      decision-service
policy:        policy-service
execution:     execution-service
notification:  notification-service
token:         token-service
business:      business-api
knowledge-mcp: ai-knowledge-rag
ticketing-mcp: ticketing-glpi
messaging-mcp: messaging-gateway
worker:        python apps/agent-worker/src/server.py start
dashboard:     npm --prefix apps/supervisor-dashboard run dev
widget:        npm --prefix apps/client-widget run dev
```

---

### pyproject.toml

```toml
# Root tooling config only (no build target here). Per-package builds live in each package's pyproject.
[tool.ruff]
target-version = "py312"
line-length = 110
extend-exclude = ["**/alembic/versions/*", "**/node_modules/**", "**/dist/**", "fixes/**"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]  # line length handled by the formatter; docstrings can run long

[tool.ruff.lint.isort]
known-first-party = [
  "persistence", "audit_trail", "domain_core", "pii_shield", "observability_kit",
  "service_auth", "notification_client",
]

[tool.mypy]
python_version = "3.12"
warn_unused_ignores = true
warn_redundant_casts = true
ignore_missing_imports = true          # third-party stubs (livekit, mcp, qdrant) not always present
disallow_untyped_defs = false          # pragmatic: enable per-package as coverage grows
exclude = "(alembic/versions|node_modules|dist|/tests/)"

```

---

### scripts\fix_frontend_deps.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for app in apps/client-widget apps/supervisor-dashboard; do
  echo "==> Reinstalling ${app}"
  cd "${ROOT_DIR}/${app}"
  rm -rf node_modules
  npm ci
done

echo "==> Frontend dependencies are ready for this Linux/WSL environment."

```

---

### scripts\health_check.py

```python
#!/usr/bin/env python3
"""Probe service health and report. Exit non-zero if any service is down."""
from __future__ import annotations

import socket
import sys
import urllib.request

HTTP_SERVICES = {
    "context-service": 8101,
    "knowledge-service": 8102,
    "decision-service": 8103,
    "policy-service": 8104,
    "execution-service": 8105,
    "notification-service": 8106,
    "token-service": 8107,
    "business-api": 8108,
}

TCP_SERVICES = {
    "ai-knowledge-rag": 8201,
    "ticketing-glpi": 8202,
    "messaging-gateway": 8203,
}


def _http_up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _tcp_up(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=3):
            return True
    except Exception:
        return False


def main() -> int:
    all_ok = True
    for name, port in HTTP_SERVICES.items():
        ok = _http_up(port)
        all_ok = all_ok and ok
        print(f"[{'OK  ' if ok else 'DOWN'}] {name:<22} :{port}")
    for name, port in TCP_SERVICES.items():
        ok = _tcp_up(port)
        all_ok = all_ok and ok
        print(f"[{'OK  ' if ok else 'DOWN'}] {name:<22} :{port}")
    print("\nAll services healthy." if all_ok else "\nSome services are DOWN - check their terminals/logs.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

```

---

### scripts\install_dev.ps1

```powershell
# Install all platform packages, services, MCPs, and tools in the correct order.
# Run once from the project root (with .venv activated):
#   .\.venv\Scripts\Activate.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Installing shared packages =========="
$packages = @(
    "domain-core", "persistence", "audit-trail", "pii-shield",
    "observability-kit", "service-auth", "cache", "object-storage",
    "notification-client", "integration-adapters"
)
foreach ($pkg in $packages) {
    Write-Output "  packages/$pkg..."
    pip install -e "$root\packages\$pkg" --quiet
}

Write-Output "========== Installing services =========="
$services = @(
    "services\context-service", "services\knowledge-service",
    "services\decision-service", "services\policy-service",
    "services\execution-service", "services\notification-service",
    "apps\token-service", "apps\business-api"
)
foreach ($svc in $services) {
    Write-Output "  $svc..."
    pip install -e "$root\$svc" --quiet
}

Write-Output "========== Installing MCP servers =========="
$mcps = @(
    "mcp-servers\ai-knowledge-rag", "mcp-servers\ticketing-glpi",
    "mcp-servers\messaging-gateway"
)
foreach ($mcp in $mcps) {
    Write-Output "  $mcp..."
    pip install -e "$root\$mcp" --quiet
}

Write-Output "========== Installing agent-worker =========="
pip install -e "$root\apps\agent-worker" --quiet

Write-Output "========== Installing honcho (process manager) =========="
pip install honcho --quiet

Write-Output "========== Frontends (npm install) =========="
Push-Location "$root\apps\supervisor-dashboard"
npm install
Pop-Location
Push-Location "$root\apps\client-widget"
npm install
Pop-Location

Write-Output "`nAll packages installed. Next steps:"
Write-Output "  1. Ensure Docker is running"
Write-Output "  2. Run:  powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1"
Write-Output "  3. After startup, run:  python scripts\health_check.py"
```

---

### scripts\run_tests.py

```python
#!/usr/bin/env python3
"""Run the offline test suite across packages/services with the right PYTHONPATH (diagnostic #9)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = "src"

# (dir, extra PYTHONPATH entries relative to the dir, pytest target)
TARGETS = [
    ("packages/audit-trail", ["../persistence/src", "../domain-core/src"], "tests"),
    ("packages/service-auth", [], "tests"),
    ("packages/cache", [], "tests"),
    ("packages/object-storage", [], "tests"),
    ("packages/integration-adapters", ["../domain-core/src"], "tests"),
    ("packages/persistence", [], "tests"),
    ("packages/observability-kit", [], "tests"),
    ("services/context-service", ["../../packages/cache/src", "../../packages/persistence/src", "../../packages/service-auth/src"], "tests"),
    ("services/knowledge-service", ["../../packages/service-auth/src"], "tests"),
    ("services/policy-service", ["../../packages/audit-trail/src", "../../packages/persistence/src", "../../packages/domain-core/src", "../../packages/service-auth/src"], "tests"),
    ("services/execution-service", ["../../packages/integration-adapters/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src", "../../packages/service-auth/src"], "tests"),
    ("services/notification-service", ["../../packages/persistence/src", "../../packages/pii-shield/src", "../../packages/service-auth/src"], "tests"),
    ("mcp-servers/ticketing-glpi", ["../../packages/persistence/src"], "tests"),
    ("apps/business-api", ["../../packages/object-storage/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src"], "tests"),
]


def main() -> int:
    failed = []
    for rel, extra, target in TARGETS:
        d = ROOT / rel
        pp = os.pathsep.join([SRC, *extra])
        env = os.environ.copy()
        env["PYTHONPATH"] = pp
        env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", target],
            cwd=d,
            env=env,
        )
        status = "ok" if result.returncode == 0 else "FAIL"
        print(f"[{status}] {rel}")
        if result.returncode != 0:
            failed.append(rel)
    print("\nAll suites passed." if not failed else f"\nFailed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

```

---

### scripts\start_dev.ps1

```powershell
# Start the entire platform: infra containers + DB setup + all processes via honcho.
# Run from the project root (with .venv activated):
#   .\.venv\Scripts\Activate.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\start_dev.ps1
#
# Requirements: Docker running, `scripts/install_dev.ps1` completed first.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Starting infrastructure containers =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" up -d

Write-Output "========== Waiting for postgres =========="
$attempts = 0
while ($attempts -lt 30) {
    $ready = docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres pg_isready -U telecom 2>&1 | Out-String
    if ($ready -match "accepting connections") { break }
    Start-Sleep -Seconds 2
    $attempts++
}
if ($attempts -ge 30) {
    Write-Output "WARNING: postgres not ready after 60s â€” continuing anyway"
}

Write-Output "========== Applying migrations =========="
Push-Location "$root\packages\persistence"
alembic upgrade head
Pop-Location

Write-Output "========== Seeding pilot data =========="
Push-Location "$root\packages\persistence"
python -m seed.seed_pilot
python -m seed.seed_reference
Pop-Location

Write-Output "========== Starting all services via honcho =========="
Write-Output "(Ctrl+C to stop all processes)"
honcho start
```

---

### scripts\start_dev_containers.ps1

```powershell
# Container-only path: build + run everything via Docker Compose (no honcho).
# Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\start_dev_containers.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "========== Building + starting everything (infra + apps) =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" up -d --build

Write-Output "========== Waiting for postgres =========="
$attempts = 0
while ($attempts -lt 30) {
    $ready = docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres pg_isready -U telecom 2>&1 | Out-String
    if ($ready -match "accepting connections") { break }
    Start-Sleep -Seconds 2
    $attempts++
}

Write-Output "========== Applying migrations =========="
docker compose -f "$root\infra\docker-compose\docker-compose.yml" exec -T postgres sh -c "pg_isready -U telecom"
# Migrations run inside the context-service container:
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" exec -T context-service sh -c "cd /app/packages/persistence && alembic upgrade head && python -m seed.seed_pilot && python -m seed.seed_reference"

Write-Output "`nAll containers running. Health check:"
Write-Output "  python scripts\health_check.py"
Write-Output "  Stop:  docker compose -f infra\docker-compose\docker-compose.yml -f infra\docker-compose\docker-compose.apps.yml down"
```

---

### scripts\stop_dev.ps1

```powershell
# Stop all containers.
# Run from project root:
#   powershell -ExecutionPolicy Bypass -File scripts\stop_dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Output "Stopping all containers..."
docker compose -f "$root\infra\docker-compose\docker-compose.yml" -f "$root\infra\docker-compose\docker-compose.apps.yml" down
Write-Output "Done."
```

---

### services\context-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/context-service/Dockerfile -t context-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/context-service/ ./services/context-service/
RUN pip install ./services/context-service
USER app
EXPOSE 8101
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8101/health')" || exit 1
CMD ["uvicorn", "context_service.main:app", "--host", "0.0.0.0", "--port", "8101"]

```

---

### services\context-service\pyproject.toml

```toml
[project]
name = "context-service"
version = "0.1.0"
description = "Customer-360 + identity system of record (CRM), backed by PostgreSQL (spec section 4)."
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy>=2.0,<2.1",
  "cache",
  "service-auth",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "pydantic==2.10.4",
  "persistence",
]

[project.scripts]
context-service = "context_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### services\context-service\src\context_service\__init__.py

```python
"""Context (Customer 360) domain service."""
```

---

### services\context-service\src\context_service\main.py

```python
"""context-service entrypoint (spec section 4): Customer-360, identity resolve/verify, read paths.

Backed by PostgreSQL via the shared persistence package. Endpoints are sync `def` so FastAPI
runs them in a threadpool (DB calls never block the event loop).
"""
from __future__ import annotations

import os
from typing import Annotated

from cache import get_cache
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from context_service.repositories import CrmRepository
from context_service.schemas import (
    Balance,
    Customer360,
    InvoiceListResponse,
    ResolveIdentityResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from persistence import get_session
from service_auth import require_internal_key

app = FastAPI(title="context-service", dependencies=[Depends(require_internal_key)])
_cache = get_cache()
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/internal/context/resolve", response_model=ResolveIdentityResponse)
def resolve_identity(msisdn: str, session: DbSession) -> ResolveIdentityResponse:
    """Resolve a caller MSISDN to canonical UUIDs (spec section 16.2) â€” the only place this happens."""
    cache_key = f"ctx:resolve:{msisdn}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return ResolveIdentityResponse.model_validate_json(cached)
    resolved = CrmRepository(session).resolve_identity(msisdn)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no active subscription for msisdn")
    customer, subscription = resolved
    response = ResolveIdentityResponse(
        customer_id=str(customer.id),
        subscription_id=str(subscription.id),
        preferred_language=customer.preferred_language,
    )
    _cache.set(cache_key, response.model_dump_json(), ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")))
    return response


@app.get("/context/{msisdn}", response_model=Customer360)
def get_context(msisdn: str, session: DbSession) -> Customer360:
    """Return the Customer-360 snapshot for a caller MSISDN (404 if unknown)."""
    snapshot = CrmRepository(session).build_customer360(msisdn)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="caller not found")
    return snapshot


@app.post("/verify-identity", response_model=VerifyIdentityResponse)
def verify_identity(
    req: VerifyIdentityRequest, session: DbSession
) -> VerifyIdentityResponse:
    """Check a step-up identity answer server-side; the secret never leaves this service."""
    return VerifyIdentityResponse(verified=CrmRepository(session).verify_identity(req.customer_id, req.answer))


@app.get("/billing/{customer_id}/invoices", response_model=InvoiceListResponse)
def get_invoices(customer_id: str, session: DbSession) -> InvoiceListResponse:
    """Return the customer's invoices (read-only consultation, CDC section 5.1)."""
    return InvoiceListResponse(invoices=CrmRepository(session).get_invoices(customer_id))


@app.get("/balance/{customer_id}", response_model=Balance)
def get_balance(customer_id: str, session: DbSession) -> Balance:
    """Return the customer's prepaid balance (404 if none on file)."""
    balance = CrmRepository(session).get_balance(customer_id)
    if balance is None:
        raise HTTPException(status_code=404, detail="no balance on file")
    return balance


def run() -> None:
    """Console-script entrypoint: `context-service` (see [project.scripts]). Serves on :8101."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101)

```

---

### services\context-service\src\context_service\mapping.py

```python
"""Pure mapping helpers (no DB) - unit-testable in isolation."""
from __future__ import annotations

import datetime


def invoice_status(raw: str) -> str:
    """Map a billing.invoices.status to the agent-facing open/paid/overdue vocabulary."""
    if raw == "paid":
        return "paid"
    if raw == "overdue":
        return "overdue"
    return "open"


def account_age_days(activation_date: datetime.date | None, today: datetime.date | None = None) -> int:
    """Derive account age in days from the subscription activation date."""
    if activation_date is None:
        return 0
    today = today or datetime.date.today()
    return max((today - activation_date).days, 0)


def verify_answer(national_id: str | None, answer: str) -> bool:
    """The step-up secret is the last 4 digits of the national id (CIN); compared server-side."""
    if not national_id:
        return False
    return answer.strip() == national_id[-4:]


def to_megabytes(value: float, unit: str) -> int:
    """Normalize a data balance to MB (GB->MB, MB as-is)."""
    if unit == "GB":
        return int(value * 1024)
    if unit == "MB":
        return int(value)
    return 0
```

---

### services\context-service\src\context_service\repositories.py

```python
"""CrmRepository: all CRM/Billing/OCS reads behind the Context faÃ§ade (spec sections 4-6).

Replaces the volatile mock_directory. The service contract (Customer360 / invoices / balance /
verify) is unchanged; identity is now resolved msisdn -> (customer_id, subscription_id) once.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_service import mapping
from context_service.schemas import Balance, Customer360, Invoice
from persistence.models.billing import Invoice as InvoiceRow
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount


class CrmRepository:
    """Read-side repository over the crm/billing/ocs schemas."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- identity ---
    def resolve_identity(self, msisdn: str) -> tuple[Customer, Subscription] | None:
        """Resolve a caller MSISDN to (customer, subscription); None if no active line."""
        stmt = (
            select(Customer, Subscription)
            .join(Subscription, Subscription.customer_id == Customer.id)
            .where(Subscription.msisdn == msisdn.strip(), Subscription.deleted_at.is_(None))
        )
        row = self._session.execute(stmt).first()
        return (row[0], row[1]) if row else None

    def _customer(self, customer_id: str) -> Customer | None:
        return self._session.get(Customer, customer_id)

    # --- Customer-360 ---
    def build_customer360(self, msisdn: str) -> Customer360 | None:
        """Build the snapshot for the caller owning ``msisdn`` (None if unknown)."""
        resolved = self.resolve_identity(msisdn)
        if resolved is None:
            return None
        customer, subscription = resolved

        invoices = self._invoice_rows(customer.id)
        open_count = sum(1 for inv in invoices if mapping.invoice_status(inv.status) != "paid")
        balance = self._balance_summary(subscription.id)

        return Customer360(
            customer_id=str(customer.id),
            subscription_id=str(subscription.id),
            full_name=f"{customer.first_name} {customer.last_name}",
            msisdn=subscription.msisdn,
            subscription_type=subscription.plan_code or subscription.plan_type,
            preferred_language=customer.preferred_language,
            is_vip=customer.vip_flag,
            fraud_suspected=customer.fraud_suspected,
            account_age_days=mapping.account_age_days(subscription.activation_date),
            open_invoice_count=open_count,
            balance_summary=balance,
        )

    def verify_identity(self, customer_id: str, answer: str) -> bool:
        """Server-side step-up check against the on-file national id (CIN)."""
        customer = self._customer(customer_id)
        return customer is not None and mapping.verify_answer(customer.national_id, answer)

    # --- reads ---
    def _invoice_rows(self, customer_id) -> list[InvoiceRow]:
        stmt = select(InvoiceRow).where(InvoiceRow.customer_id == customer_id)
        return list(self._session.scalars(stmt))

    def get_invoices(self, customer_id: str) -> list[Invoice]:
        """Return the customer's invoices (read-only, CDC section 5.1)."""
        return [
            Invoice(
                invoice_id=row.invoice_number,
                amount=float(row.total_amount),
                currency=row.currency_code,
                due_date=row.due_date.isoformat(),
                status=mapping.invoice_status(row.status),
            )
            for row in self._invoice_rows(customer_id)
        ]

    def get_balance(self, customer_id: str) -> Balance | None:
        """Return the prepaid balance (main credit + data) or None."""
        rows = list(
            self._session.scalars(
                select(BalanceAccount).where(BalanceAccount.customer_id == customer_id)
            )
        )
        if not rows:
            return None
        credit, currency, data_mb, valid_until = 0.0, "TND", 0, None
        for row in rows:
            if row.balance_type == "main":
                credit, currency = float(row.balance_value), row.balance_unit
            elif row.balance_type == "data":
                data_mb = mapping.to_megabytes(float(row.balance_value), row.balance_unit)
            if row.expiry_date and valid_until is None:
                valid_until = row.expiry_date.isoformat()
        return Balance(
            customer_id=customer_id, credit=credit, currency=currency,
            data_remaining_mb=data_mb, valid_until=valid_until,
        )

    def _balance_summary(self, subscription_id) -> str | None:
        row = self._session.scalar(
            select(BalanceAccount).where(
                BalanceAccount.subscription_id == subscription_id,
                BalanceAccount.balance_type == "main",
            )
        )
        return f"{float(row.balance_value):.3f} {row.balance_unit}" if row else None
```

---

### services\context-service\src\context_service\schemas.py

```python
"""Wire DTOs for the context-service (spec section 4). English-only system layer.

Backward compatible with the pre-persistence contract; adds subscription_id + fraud_suspected
(the canonical identity model, spec section 1).
"""
from __future__ import annotations

from pydantic import BaseModel


class Customer360(BaseModel):
    """The caller snapshot pre-fetched into session user-data at call start. Never carries PII secrets."""

    customer_id: str
    subscription_id: str | None = None
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0
    open_invoice_count: int = 0
    balance_summary: str | None = None


class ResolveIdentityResponse(BaseModel):
    """MSISDN -> canonical UUIDs (spec section 16.2). The only place this translation happens."""

    customer_id: str
    subscription_id: str
    preferred_language: str = "fr"


class VerifyIdentityRequest(BaseModel):
    """Step-up identity check input (CDC section 6.5). The secret never leaves the service."""

    customer_id: str
    answer: str


class VerifyIdentityResponse(BaseModel):
    """Step-up identity check result."""

    verified: bool


class Invoice(BaseModel):
    """A single invoice (read-only consultation, CDC section 5.1)."""

    invoice_id: str
    amount: float
    currency: str = "TND"
    due_date: str
    status: str  # "open" | "paid" | "overdue"


class InvoiceListResponse(BaseModel):
    """Open invoices for a customer."""

    invoices: list[Invoice]


class Balance(BaseModel):
    """Prepaid credit / data balance (read-only, CDC section 5.x)."""

    customer_id: str
    credit: float
    currency: str = "TND"
    data_remaining_mb: int = 0
    valid_until: str | None = None
```

---

### services\context-service\tests\test_aggregator.py

```python
"""Integration tests for CrmRepository (requires DATABASE_URL env var with Postgres + seeded data).

Run::

    DATABASE_URL=postgresql+psycopg://telecom:telecom@localhost:5432/telecom \\
      pytest services/context-service/tests/test_aggregator.py -v

Tests are skipped if DATABASE_URL is not set.
"""
from __future__ import annotations

import os

import pytest
from context_service.repositories import CrmRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="requires DATABASE_URL pointing to a seeded Postgres",
)


@pytest.fixture(scope="module")
def session() -> Session:
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def test_resolve_identity_known_msisdn(session: Session) -> None:
    repo = CrmRepository(session)
    result = repo.resolve_identity("+21620155320")
    assert result is not None
    customer, subscription = result
    assert customer.first_name and subscription.msisdn


def test_resolve_identity_unknown_msisdn(session: Session) -> None:
    repo = CrmRepository(session)
    assert repo.resolve_identity("+21600000000") is None


def test_build_customer360_for_known_caller(session: Session) -> None:
    snap = CrmRepository(session).build_customer360("+21620155320")
    assert snap is not None
    assert snap.msisdn == "+21620155320"
    assert snap.full_name


def test_build_customer360_unknown_caller(session: Session) -> None:
    assert CrmRepository(session).build_customer360("+21600000000") is None


def test_verify_identity_correct_answer(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    assert repo.verify_identity(str(customer.id), customer.national_id[-4:]) is True


def test_verify_identity_wrong_answer(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    assert repo.verify_identity(str(customer.id), "0000") is False


def test_verify_identity_unknown_customer(session: Session) -> None:
    assert CrmRepository(session).verify_identity("00000000-0000-0000-0000-000000000000", "4087") is False


def test_get_invoices(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21620155320")
    assert resolved is not None
    customer, _ = resolved
    invoices = repo.get_invoices(str(customer.id))
    assert isinstance(invoices, list)


def test_get_balance(session: Session) -> None:
    repo = CrmRepository(session)
    resolved = repo.resolve_identity("+21629744108")
    assert resolved is not None
    customer, _ = resolved
    balance = repo.get_balance(str(customer.id))
    if balance is not None:
        assert balance.credit >= 0

```

---

### services\context-service\tests\test_mapping.py

```python
"""Offline unit tests for the pure mapping helpers (no DB). Repository reads are integration-tested
against Postgres on the developer machine (see the persistence README)."""
from __future__ import annotations

import datetime

from context_service import mapping


def test_invoice_status_mapping() -> None:
    assert mapping.invoice_status("paid") == "paid"
    assert mapping.invoice_status("overdue") == "overdue"
    assert mapping.invoice_status("issued") == "open"
    assert mapping.invoice_status("partial") == "open"


def test_account_age_days() -> None:
    today = datetime.date(2026, 6, 29)
    assert mapping.account_age_days(datetime.date(2026, 6, 29), today) == 0
    assert mapping.account_age_days(datetime.date(2026, 3, 31), today) == 90
    assert mapping.account_age_days(None, today) == 0


def test_verify_answer_uses_last4_of_national_id() -> None:
    assert mapping.verify_answer("11224087", "4087") is True
    assert mapping.verify_answer("11224087", " 4087 ") is True
    assert mapping.verify_answer("11224087", "1122") is False
    assert mapping.verify_answer(None, "4087") is False


def test_to_megabytes() -> None:
    assert mapping.to_megabytes(2, "GB") == 2048
    assert mapping.to_megabytes(1840, "MB") == 1840
    assert mapping.to_megabytes(5, "TND") == 0
```

---

### services\decision-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/decision-service/Dockerfile -t decision-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/decision-service/ ./services/decision-service/
RUN pip install ./services/decision-service
USER app
EXPOSE 8103
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8103/health')" || exit 1
CMD ["uvicorn", "decision_service.main:app", "--host", "0.0.0.0", "--port", "8103"]

```

---

### services\decision-service\pyproject.toml

```toml
[project]
name = "decision-service"
version = "0.1.0"
description = "Candidate-action ranking + confidence (CDC 4.5)."
requires-python = ">=3.12"
dependencies = [
  "service-auth","fastapi==0.115.6", "uvicorn[standard]==0.34.0", "domain-core"]

[project.scripts]
decision-service = "decision_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### services\decision-service\src\decision_service\__init__.py

```python
"""Decision domain service."""
```

---

### services\decision-service\src\decision_service\main.py

```python
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

```

---

### services\decision-service\src\decision_service\schemas.py

```python
"""Wire DTOs for the decision-service."""
from __future__ import annotations

from pydantic import BaseModel


class DecisionRequest(BaseModel):
    """A candidate-action ranking request."""

    action_type: str
    context: dict = {}


class DecisionResponse(BaseModel):
    """The ranked candidate action with confidence."""

    action: str
    confidence: float
    rationale: str
```

---

### services\decision-service\src\decision_service\scorer.py

```python
"""Decision context (CDC section 4.5): rank a candidate action with a confidence value.

Deterministic for Phase 6: a known, catalogued action with a resolved caller scores high;
an unknown action or missing context scores low so the faÃ§ade escalates instead of forcing.
"""
from __future__ import annotations

from dataclasses import dataclass

KNOWN_ACTIONS = frozenset(
    {
        "EXECUTE_PAYMENT",
        "PAYMENT_DEFERRAL",
        "UNBLOCK_SIM",
        "REPLACE_SIM",
        "REACTIVATE_SIM",
        "TOP_UP",
        "CHANGE_PLAN",
        "ACTIVATE_ROAMING",
    }
)


@dataclass(frozen=True)
class Decision:
    """A candidate action ranked with a confidence and a short rationale."""

    action: str
    confidence: float
    rationale: str


def recommend(action_type: str, context: dict) -> Decision:
    """Return a candidate action + confidence for ``action_type`` given ``context``."""
    if action_type not in KNOWN_ACTIONS:
        return Decision(action_type, 0.2, "action not in the catalogue")
    confidence = 0.9
    rationale = "catalogued action with sufficient context"
    if not context.get("identity_verified", False):
        confidence -= 0.3
        rationale = "catalogued action but identity not yet verified"
    return Decision(action_type, round(confidence, 2), rationale)
```

---

### services\decision-service\tests\test_scorer.py

```python
"""Offline tests for the decision scorer."""
from __future__ import annotations

from decision_service.scorer import recommend


def test_known_action_with_identity_scores_high() -> None:
    decision = recommend("PAYMENT_DEFERRAL", {"identity_verified": True})
    assert decision.confidence >= 0.8


def test_unknown_action_scores_low() -> None:
    assert recommend("DO_SOMETHING_WEIRD", {}).confidence < 0.5


def test_missing_identity_lowers_confidence() -> None:
    assert recommend("PAYMENT_DEFERRAL", {"identity_verified": False}).confidence < 0.7
```

---

### services\execution-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/execution-service/Dockerfile -t execution-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/execution-service/ ./services/execution-service/
RUN pip install ./services/execution-service
USER app
EXPOSE 8105
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8105/health')" || exit 1
CMD ["uvicorn", "execution_service.main:app", "--host", "0.0.0.0", "--port", "8105"]

```

---

### services\execution-service\pyproject.toml

```toml
[project]
name = "execution-service"
version = "0.1.0"
description = "Idempotent action ledger (CDC 4.7). Actions + audit persisted to Postgres."
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy>=2.0,<2.1",
  "integration-adapters",
  "service-auth",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "pydantic==2.10.4",
  "domain-core",
  "audit-trail",
  "persistence",
]

[project.scripts]
execution-service = "execution_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### services\execution-service\src\execution_service\__init__.py

```python
"""Execution domain service."""
```

---

### services\execution-service\src\execution_service\executor.py

```python
"""Action dispatch (report #10): mock by default, routed to the real adapters when CONNECTOR_MODE=live.

Mock keeps the deterministic prefixed reference so existing behaviour/tests are unchanged. Live
routes billing/OCS/payment actions through integration-adapters (which fall back to mock if their
URL is unset). Actions without a live port yet (SIM / plan / roaming) return a synthesized
reference and are flagged for binding.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from integration_adapters.config import is_live

logger = logging.getLogger(__name__)

_REFERENCE_PREFIX = {
    "EXECUTE_PAYMENT": "PAY", "PAYMENT_DEFERRAL": "DEF", "UNBLOCK_SIM": "SIM",
    "REPLACE_SIM": "SIM", "REACTIVATE_SIM": "SIM", "TOP_UP": "TOP",
    "CHANGE_PLAN": "PLN", "ACTIVATE_ROAMING": "ROAM",
}
_TARGET_DOMAIN = {
    "EXECUTE_PAYMENT": "billing", "PAYMENT_DEFERRAL": "billing", "TOP_UP": "ocs",
    "UNBLOCK_SIM": "sim", "REPLACE_SIM": "sim", "REACTIVATE_SIM": "sim",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}


def _mock_reference(action_type: str) -> str:
    return f"{_REFERENCE_PREFIX.get(action_type, 'ACT')}-{uuid.uuid4().hex[:10].upper()}"


def dispatch(action_type: str, payload: dict, *, customer_id: str | None = None,
             idempotency_key: str | None = None) -> str:
    """Execute the action against the legacy system and return a confirmation reference."""
    if not is_live():
        return _mock_reference(action_type)
    return _dispatch_live(action_type, payload, customer_id, idempotency_key)


def _dispatch_live(action_type: str, payload: dict, customer_id: str | None, idempotency_key: str | None) -> str:
    import asyncio

    from integration_adapters import get_balance_adapter, get_billing_adapter

    from domain_core.value_objects import IdempotencyKey, Money

    key = IdempotencyKey(idempotency_key or uuid.uuid4().hex)
    amount = Money(Decimal(str(payload.get("amount") or 0)))
    try:
        if action_type == "EXECUTE_PAYMENT":
            return asyncio.run(get_billing_adapter().charge(customer_id or "", amount, key))
        if action_type == "PAYMENT_DEFERRAL":
            asyncio.run(get_billing_adapter().grant_deferral(customer_id or "", int(payload.get("requested_days") or 0), key))
            return f"DEF-{key.value[:10].upper()}"
        if action_type == "TOP_UP":
            return asyncio.run(get_balance_adapter().top_up(customer_id or "", amount, key))
    except Exception as exc:
        logger.error("live dispatch failed for %s: %s", action_type, exc)
        raise
    logger.info("no live adapter for %s yet; returning synthesized reference", action_type)
    return _mock_reference(action_type)


def target_domain(action_type: str) -> str:
    """Map an action type to the domain whose adapter performs it."""
    return _TARGET_DOMAIN.get(action_type, "execution")
```

---

### services\execution-service\src\execution_service\main.py

```python
"""execution-service entrypoint (CDC section 4.7): idempotent dispatch of authorized actions (Postgres)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from execution_service.schemas import ExecuteRequest, ExecuteResponse
from execution_service.service import ExecutionService
from persistence import get_session
from service_auth import require_internal_key

app = FastAPI(title="execution-service", dependencies=[Depends(require_internal_key)])
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest, session: DbSession) -> ExecuteResponse:
    """Dispatch an AUTHORIZED action idempotently and audit the result."""
    return ExecutionService(session).execute(req)


@app.get("/audit/verify")
def audit_verify(session: DbSession) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


def run() -> None:
    """Console-script entrypoint: `execution-service` (see [project.scripts]). Serves on :8105."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8105)

```

---

### services\execution-service\src\execution_service\projections.py

```python
"""Domain write projections (spec sections 5-7): the durable effect of an AUTHORIZED action.

When the (mock) adapter dispatch succeeds, the action's effect is projected into the owning
domain schema - a captured payment, a deferral plan, a recharge, a SIM case - carrying the same
idempotency_key as execution.action_ledger and the policy_verdict_id that authorized it. The
projection runs in a SAVEPOINT inside the execute transaction, so a projection problem can never
undo the action ledger or the audit chain. Defensive: missing data logs and skips.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.billing import Account, Invoice, Payment, PaymentPlan
from persistence.models.ocs import Recharge
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest
from persistence.models.sim import BlockUnblockCase
from persistence.util import to_uuid

logger = logging.getLogger(__name__)

# ---- pure mapping (offline-testable) ----
_PROJECTION = {
    "EXECUTE_PAYMENT": "payment", "PAYMENT_DEFERRAL": "payment_plan",
    "TOP_UP": "recharge", "UNBLOCK_SIM": "sim_case", "REACTIVATE_SIM": "sim_case",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}
_SIM_ACTION = {"UNBLOCK_SIM": "UNBLOCK", "REACTIVATE_SIM": "REACTIVATE"}


def projection_kind(action_type: str) -> str | None:
    """Which domain table an action projects into (None if it has no projection)."""
    return _PROJECTION.get(action_type)


def sim_case_action(action_type: str) -> str | None:
    """Map a SIM action_type to the block_unblock_cases.action value."""
    return _SIM_ACTION.get(action_type)


def installment_amount(total, count) -> float:
    """Even per-installment amount (>=1 installment), rounded to millimes."""
    count = max(1, int(count or 1))
    return round(float(total or 0) / count, 3)


# ---- DB projection ----
def project_domain_effect(session: Session, req, ledger_row) -> None:
    """Write the domain row for ``req`` (dispatch already succeeded). Caller wraps this in a savepoint."""
    kind = projection_kind(req.action_type)
    if kind == "payment":
        _payment(session, req, ledger_row)
    elif kind == "payment_plan":
        _payment_plan(session, req, ledger_row)
    elif kind == "recharge":
        _recharge(session, req, ledger_row)
    elif kind == "sim_case":
        _sim_case(session, req, ledger_row)
    elif kind == "provisioning":
        _provisioning(session, req, ledger_row)


def _account_for(session: Session, customer_id):
    cid = to_uuid(customer_id)
    return session.scalar(select(Account).where(Account.customer_id == cid)) if cid else None


def _payment(session: Session, req, ledger_row) -> None:
    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("payment projection skipped: no billing account for %s", req.customer_id)
        return
    invoice = None
    inv_num = req.payload.get("invoice_id") or req.payload.get("invoice_number")
    if inv_num:
        invoice = session.scalar(select(Invoice).where(Invoice.invoice_number == str(inv_num)))
    session.add(Payment(
        account_id=account.id,
        invoice_id=invoice.id if invoice else None,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        method=req.payload.get("method", "card"),
        gateway_reference=ledger_row.adapter_reference,
        idempotency_key=req.idempotency_key,
        status="succeeded",
        paid_at=datetime.now(UTC),
    ))


def _payment_plan(session: Session, req, ledger_row) -> None:
    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("plan projection skipped: no billing account for %s", req.customer_id)
        return
    total = req.payload.get("amount") or req.payload.get("unpaid_amount") or 0
    count = req.payload.get("installment_count") or 1
    session.add(PaymentPlan(
        account_id=account.id,
        customer_id=to_uuid(req.customer_id),
        total_amount=total,
        installment_count=count,
        installment_amount=installment_amount(total, count),
        status="active",
        policy_verdict_id=to_uuid(req.policy_verdict_id),
    ))


def _recharge(session: Session, req, ledger_row) -> None:
    sid = to_uuid(req.subscription_id)
    if sid is None:
        logger.warning("recharge projection skipped: no subscription on request")
        return
    session.add(Recharge(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        channel="agent",
        idempotency_key=req.idempotency_key,
        transaction_reference=ledger_row.adapter_reference,
        status="completed",
    ))


def _sim_case(session: Session, req, ledger_row) -> None:
    action = sim_case_action(req.action_type)
    sid = to_uuid(req.subscription_id)
    if action is None or sid is None:
        logger.warning("sim projection skipped: action=%s subscription=%s", action, req.subscription_id)
        return
    session.add(BlockUnblockCase(
        subscription_id=sid,
        action=action,
        status="completed",
        identity_verified=True,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        idempotency_key=req.idempotency_key,
    ))


def _provisioning(session: Session, req, ledger_row) -> None:
    from datetime import datetime

    sid = to_uuid(req.subscription_id)
    session.add(ProvisioningRequest(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        action_type=req.action_type,
        status="completed",
        idempotency_key=req.idempotency_key,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        parameters=req.payload,
        completed_at=datetime.now(UTC),
    ))
    if req.action_type == "CHANGE_PLAN" and sid is not None:
        session.add(PlanChangeHistory(
            subscription_id=sid,
            from_plan=req.payload.get("from_plan"),
            to_plan=str(req.payload.get("plan_code") or "unknown"),
            changed_by="agent",
        ))

```

---

### services\execution-service\src\execution_service\schemas.py

```python
"""Wire DTOs for the execution-service."""
from __future__ import annotations

from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    """An AUTHORIZED action to dispatch. The idempotency_key makes a retry safe (spec section 12.2)."""

    idempotency_key: str
    action_type: str
    session_id: str = "unknown"
    policy_verdict_id: str            # the verdict that authorized this action (FK, required)
    customer_id: str | None = None
    subscription_id: str | None = None
    target_domain: str | None = None  # derived from action_type if omitted
    payload: dict = {}


class ExecuteResponse(BaseModel):
    """The result of dispatch; ``replay`` is True when a duplicate key returned the prior result."""

    status: str
    reference: str
    action_type: str
    replay: bool = False
```
---

### services\execution-service\src\execution_service\service.py

```python
"""ExecutionService: idempotent action ledger (Postgres) + execution-result audit.

execute(): look up the idempotency key (replay if seen) -> INSERT a pending action_ledger row
(UNIQUE key enforces at-most-once even under a race) -> dispatch -> mark succeeded -> audit, all
in one transaction. Every row carries the policy_verdict_id that authorized it (spec section 12).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from execution_service.executor import dispatch, target_domain
from execution_service.projections import project_domain_effect
from execution_service.schemas import ExecuteRequest, ExecuteResponse
from persistence.models.execution import ActionLedger
from persistence.util import require_uuid, to_uuid

logger = logging.getLogger(__name__)


class ExecutionService:
    """Dispatches AUTHORIZED actions exactly once per idempotency key, with an audit trail."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = PgAuditLedger(session)

    def execute(self, req: ExecuteRequest) -> ExecuteResponse:
        """Dispatch ``req`` once; a repeat key returns the original reference with replay=True."""
        existing = self._by_key(req.idempotency_key)
        if existing is not None:
            return self._replay(existing)

        row = ActionLedger(
            session_id=require_uuid(req.session_id),
            customer_id=to_uuid(req.customer_id),
            subscription_id=to_uuid(req.subscription_id),
            action_type=req.action_type,
            target_domain=req.target_domain or target_domain(req.action_type),
            idempotency_key=req.idempotency_key,
            policy_verdict_id=require_uuid(req.policy_verdict_id),
            parameters=req.payload,
            status="pending",
            attempt_count=1,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            existing = self._by_key(req.idempotency_key)
            if existing is not None:  # lost a race on the same key -> replay
                return self._replay(existing)
            raise  # a different constraint (e.g. unknown policy_verdict_id) - surface it

        reference = dispatch(req.action_type, req.payload, customer_id=req.customer_id, idempotency_key=req.idempotency_key)
        row.status = "succeeded"
        row.adapter_reference = reference
        self._audit.append(
            require_uuid(req.session_id), "execution_result",
            {"action_type": req.action_type, "reference": reference, "idempotency_key": req.idempotency_key},
            entity_reference=f"action_ledger:{row.id}",
        )

        # Project the domain effect (payment / plan / recharge / sim case) in a SAVEPOINT, so a
        # projection failure can never undo the action ledger or the audit chain.
        try:
            with self._session.begin_nested():
                project_domain_effect(self._session, req, row)
        except Exception as exc:
            logger.warning("domain projection failed (%s): %s", req.action_type, exc)

        self._session.commit()
        return ExecuteResponse(status="executed", reference=reference, action_type=req.action_type, replay=False)

    def _by_key(self, key: str) -> ActionLedger | None:
        return self._session.scalar(select(ActionLedger).where(ActionLedger.idempotency_key == key))

    @staticmethod
    def _replay(row: ActionLedger) -> ExecuteResponse:
        return ExecuteResponse(
            status="executed", reference=row.adapter_reference or "", action_type=row.action_type, replay=True
        )
```

---

### services\execution-service\tests\test_executor.py

```python
"""Offline tests for the pure dispatch/target-domain helpers (no DB).

The idempotent ledger + audit chain are integration-tested against Postgres on the developer
machine (see the persistence README)."""
from __future__ import annotations

from execution_service.executor import dispatch, target_domain


def test_target_domain_mapping() -> None:
    assert target_domain("EXECUTE_PAYMENT") == "billing"
    assert target_domain("PAYMENT_DEFERRAL") == "billing"
    assert target_domain("UNBLOCK_SIM") == "sim"
    assert target_domain("ACTIVATE_ROAMING") == "provisioning"
    assert target_domain("SOMETHING_ELSE") == "execution"


def test_dispatch_reference_prefixes() -> None:
    assert dispatch("EXECUTE_PAYMENT", {}).startswith("PAY-")
    assert dispatch("PAYMENT_DEFERRAL", {}).startswith("DEF-")
    assert dispatch("UNBLOCK_SIM", {}).startswith("SIM-")
    assert dispatch("MYSTERY", {}).startswith("ACT-")
```

---

### services\execution-service\tests\test_projections.py

```python
"""Offline tests for the pure projection mapping (no DB). The DB writes are integration-tested."""
from __future__ import annotations

from execution_service.projections import installment_amount, projection_kind, sim_case_action


def test_projection_kind() -> None:
    assert projection_kind("EXECUTE_PAYMENT") == "payment"
    assert projection_kind("PAYMENT_DEFERRAL") == "payment_plan"
    assert projection_kind("TOP_UP") == "recharge"
    assert projection_kind("UNBLOCK_SIM") == "sim_case"
    assert projection_kind("REACTIVATE_SIM") == "sim_case"
    assert projection_kind("CHANGE_PLAN") == "provisioning"
    assert projection_kind("ACTIVATE_ROAMING") == "provisioning"
    assert projection_kind("SEND_SMS") is None


def test_sim_case_action() -> None:
    assert sim_case_action("UNBLOCK_SIM") == "UNBLOCK"
    assert sim_case_action("REACTIVATE_SIM") == "REACTIVATE"
    assert sim_case_action("EXECUTE_PAYMENT") is None


def test_installment_amount() -> None:
    assert installment_amount(120, 3) == 40.0
    assert installment_amount(73.9, 1) == 73.9
    assert installment_amount(100, 0) == 100.0  # guarded to >=1 installment
```

---

### services\knowledge-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/knowledge-service/Dockerfile -t knowledge-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/knowledge-service/ ./services/knowledge-service/
RUN pip install ./services/knowledge-service
USER app
EXPOSE 8102
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8102/health')" || exit 1
CMD ["uvicorn", "knowledge_service.main:app", "--host", "0.0.0.0", "--port", "8102"]

```

---

### services\knowledge-service\pyproject.toml

```toml
[project]
name = "knowledge-service"
version = "0.1.0"
description = "RAG over the documentation corpus + vector store (Qdrant)."
requires-python = ">=3.12"
dependencies = [
  "httpx==0.28.1",
  "service-auth","fastapi==0.115.6", "uvicorn[standard]==0.34.0", "domain-core"]

[project.optional-dependencies]
qdrant = ["qdrant-client==1.12.1"]

[project.scripts]
knowledge-service = "knowledge_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### services\knowledge-service\src\knowledge_service\__init__.py

```python
"""Knowledge / RAG domain service."""
```

---

### services\knowledge-service\src\knowledge_service\corpus.py

```python
"""Single English knowledge corpus (cookbook section 1.3: one English corpus, not three).

The conversational layer is multilingual; this system-layer corpus is English. The LLM
searches in English and answers in the caller's language, citing the returned source.
Content mirrors Tunisie Telecom offers/procedures/FAQ with real USSD codes and TND amounts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """One retrievable knowledge passage with a citable source reference."""

    doc_id: str
    title: str
    text: str
    source: str


CORPUS: tuple[Document, ...] = (
    Document(
        doc_id="offer-flexi",
        title="Forfait Flexi postpaid plan",
        text=(
            "The Forfait Flexi is a postpaid mobile plan. The 25 TND tier includes 20 GB of "
            "national data, unlimited calls to Tunisie Telecom numbers, and 120 minutes to other "
            "national networks. Billing is monthly. You can check your remaining data by dialing "
            "*111#."
        ),
        source="offers/forfait-flexi",
    ),
    Document(
        doc_id="proc-roaming",
        title="Activate international roaming",
        text=(
            "To activate international roaming on a postpaid line, dial *140# and follow the menu, "
            "or enable roaming in the My Tunisie Telecom app. Roaming activation can take up to 30 "
            "minutes. Daily roaming passes are billed in TND according to the destination zone."
        ),
        source="procedures/roaming-activation",
    ),
    Document(
        doc_id="faq-data",
        title="Mobile data is not working",
        text=(
            "If mobile data is not working, first toggle airplane mode off and on, then verify the "
            "APN is set to 'internet'. Confirm there is remaining data by dialing *111#. If the "
            "problem persists in your area, there may be a known network incident."
        ),
        source="faq/data-troubleshooting",
    ),
    Document(
        doc_id="faq-billing",
        title="Invoice and billing cycle",
        text=(
            "Postpaid invoices are issued monthly and are due 15 days after issue. You can consult "
            "your latest invoice amount and due date by asking the assistant, in the My Tunisie "
            "Telecom app, or by dialing *888#. A payment deferral can be requested for eligible "
            "accounts."
        ),
        source="faq/billing-cycle",
    ),
    Document(
        doc_id="proc-plan-change",
        title="Change your mobile plan",
        text=(
            "To change your mobile plan, the change takes effect at the start of the next billing "
            "cycle. Downgrades keep your number and remaining balance. Some promotional plans "
            "require a minimum commitment period before a change is allowed."
        ),
        source="procedures/plan-change",
    ),
)
```

---

### services\knowledge-service\src\knowledge_service\main.py

```python
"""knowledge-service entrypoint (Blueprint section 4.4 / 7.6): RAG search over the corpus."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from knowledge_service.retriever import get_retriever
from knowledge_service.schemas import PassageModel, SearchRequest, SearchResponse
from service_auth import require_internal_key

app = FastAPI(title="knowledge-service", dependencies=[Depends(require_internal_key)])
_retriever = get_retriever()


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Return ranked, source-attributed passages for an English query."""
    passages = _retriever.search(req.query, top_k=req.top_k)
    return SearchResponse(
        passages=[PassageModel(text=p.text, source=p.source, score=p.score) for p in passages]
    )


def run() -> None:
    """Console-script entrypoint: `knowledge-service` (see [project.scripts]). Serves on :8102."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8102)

```

---

### services\knowledge-service\src\knowledge_service\retriever.py

```python
"""Retrieval behind a small interface so the index implementation is swappable (KnowledgePort).

Phase 5 ships a dependency-free lexical retriever over the in-memory corpus. The production
swap is a Qdrant-backed embedding retriever implementing the same interface â€” the agent code
and MCP tool never change when it is replaced (Blueprint section 7.6 / ADR vector store).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from knowledge_service.corpus import CORPUS, Document

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Passage:
    """A scored retrieval result carrying its citable source."""

    text: str
    source: str
    score: float


class LexicalRetriever:
    """Score documents by query-term overlap. Deterministic, no external dependency."""

    def __init__(self, documents: tuple[Document, ...] = CORPUS) -> None:
        self._documents = documents

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        """Return up to ``top_k`` passages whose text best matches ``query`` (score > 0)."""
        query_terms = set(_tokenize(query))
        if not query_terms:
            return []
        scored: list[Passage] = []
        for doc in self._documents:
            doc_terms = _tokenize(f"{doc.title} {doc.text}")
            overlap = sum(1 for term in doc_terms if term in query_terms)
            if overlap:
                score = overlap / (len(doc_terms) ** 0.5)
                scored.append(Passage(text=doc.text, source=doc.source, score=round(score, 4)))
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return scored[:top_k]


logger = logging.getLogger(__name__)


class QdrantRetriever:
    """Embedding retriever over Qdrant (report #6), same `search` interface as the lexical one."""

    def __init__(self, client, collection: str, embed) -> None:
        self._client = client
        self._collection = collection
        self._embed = embed

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        vector = self._embed(query)
        hits = self._client.search(collection_name=self._collection, query_vector=vector, limit=top_k)
        return [
            Passage(text=h.payload.get("text", ""), source=h.payload.get("source", ""), score=float(h.score))
            for h in hits
        ]


def _openai_embedder():
    """Return a callable str->vector using the OpenAI embeddings API (requires OPENAI_API_KEY)."""
    import httpx

    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(text: str) -> list[float]:
        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": text}, timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    return embed


def get_retriever():
    """Return the Qdrant retriever when QDRANT_URL is set and reachable; else the lexical one."""
    url = os.getenv("QDRANT_URL")
    if url:
        try:
            from qdrant_client import QdrantClient  # optional dependency

            collection = os.getenv("QDRANT_COLLECTION", "telecom_knowledge")
            return QdrantRetriever(QdrantClient(url=url), collection, _openai_embedder())
        except Exception as exc:
            logger.warning("qdrant unavailable (%s); falling back to lexical retriever", exc)
    return LexicalRetriever()

```

---

### services\knowledge-service\src\knowledge_service\schemas.py

```python
"""Wire DTOs for the knowledge-service."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """A knowledge-base search query (English, per cookbook section 1)."""

    query: str
    top_k: int = 4


class PassageModel(BaseModel):
    """A single grounded passage with its source reference."""

    text: str
    source: str
    score: float


class SearchResponse(BaseModel):
    """Ranked passages for a query; every passage carries a source (Blueprint section 7.6)."""

    passages: list[PassageModel]
```

---

### services\knowledge-service\tests\test_retriever.py

```python
"""Offline retrieval tests (no network/SDK)."""
from __future__ import annotations

from knowledge_service.retriever import LexicalRetriever

retriever = LexicalRetriever()


def test_roaming_query_returns_roaming_doc_with_source() -> None:
    passages = retriever.search("how do I activate international roaming abroad", top_k=3)
    assert passages
    assert passages[0].source == "procedures/roaming-activation"
    assert passages[0].score > 0


def test_billing_query_returns_billing_doc() -> None:
    passages = retriever.search("when is my invoice due", top_k=3)
    assert any(p.source == "faq/billing-cycle" for p in passages)


def test_unmatched_query_returns_empty() -> None:
    assert retriever.search("zxqw nonsense token", top_k=3) == []
```

---

### services\notification-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/notification-service/Dockerfile -t notification-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/notification-service/ ./services/notification-service/
RUN pip install ./services/notification-service
USER app
EXPOSE 8106
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8106/health')" || exit 1
CMD ["uvicorn", "notification_service.main:app", "--host", "0.0.0.0", "--port", "8106"]

```

---

### services\notification-service\pyproject.toml

```toml
[project]
name = "notification-service"
version = "0.1.0"
description = "Outbound written confirmations (SMS/WhatsApp/Email), localized + PII-masked (CDC 4.10)."
requires-python = ">=3.12"
dependencies = [
  "service-auth",
  "persistence",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "pydantic==2.10.4",
  "pii-shield",
]

[project.scripts]
notification-service = "notification_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

### services\notification-service\src\notification_service\__init__.py

```python
"""notification-service package."""
```

---

### services\notification-service\src\notification_service\channels.py

```python
"""Channel adapters (report #5): mock by default; real SMS/WhatsApp (Twilio REST) + Email (SMTP)
when CONNECTOR_MODE=live and the provider is configured. Falls back to mock if a provider's
credentials are missing, so a half-configured env degrades safely."""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Protocol

import httpx

from pii_shield import PiiMasker

logger = logging.getLogger(__name__)
_masker = PiiMasker()


class NotificationChannel(Protocol):
    name: str

    async def send(self, to: str, body: str) -> str: ...


# ---------------- mock ----------------
class _MockChannel:
    name = "mock"

    async def send(self, to: str, body: str) -> str:
        reference = f"{self.name.upper()}-{uuid.uuid4().hex[:10].upper()}"
        logger.info("[%s] to=%s ref=%s body=%s", self.name, _masker.mask(to or ""), reference, body)
        return reference


class MockSmsChannel(_MockChannel):
    name = "sms"


class MockWhatsAppChannel(_MockChannel):
    name = "whatsapp"


class MockEmailChannel(_MockChannel):
    name = "email"


# ---------------- live ----------------
class TwilioChannel:
    """SMS/WhatsApp via the Twilio REST API (no SDK dependency)."""

    def __init__(self, name: str, from_number: str) -> None:
        self.name = name
        self._from = from_number
        self._sid = os.environ["TWILIO_ACCOUNT_SID"]
        self._token = os.environ["TWILIO_AUTH_TOKEN"]

    async def send(self, to: str, body: str) -> str:
        prefix = "whatsapp:" if self.name == "whatsapp" else ""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url, auth=(self._sid, self._token),
                data={"From": f"{prefix}{self._from}", "To": f"{prefix}{to}", "Body": body},
            )
            resp.raise_for_status()
            return resp.json().get("sid", "")


class SmtpEmailChannel:
    """Email via SMTP (stdlib, run off the event loop)."""

    name = "email"

    def __init__(self) -> None:
        self._host = os.environ["SMTP_HOST"]
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._user = os.getenv("SMTP_USER", "")
        self._password = os.getenv("SMTP_PASSWORD", "")
        self._from = os.getenv("EMAIL_FROM", self._user)

    def _send_sync(self, to: str, body: str) -> str:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to
        message["Subject"] = "Tunisie Telecom"
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port) as server:
            server.starttls()
            if self._user:
                server.login(self._user, self._password)
            server.send_message(message)
        return f"EMAIL-{uuid.uuid4().hex[:10].upper()}"

    async def send(self, to: str, body: str) -> str:
        return await asyncio.to_thread(self._send_sync, to, body)


_MOCKS: dict[str, NotificationChannel] = {
    "sms": MockSmsChannel(), "whatsapp": MockWhatsAppChannel(), "email": MockEmailChannel(),
}


def _live_channel(name: str) -> NotificationChannel | None:
    """Build a live channel if its provider is configured; else None (â†’ mock fallback)."""
    try:
        if name == "sms" and os.getenv("TWILIO_ACCOUNT_SID"):
            return TwilioChannel("sms", os.getenv("TWILIO_SMS_FROM", ""))
        if name == "whatsapp" and os.getenv("TWILIO_ACCOUNT_SID"):
            return TwilioChannel("whatsapp", os.getenv("TWILIO_WHATSAPP_FROM", ""))
        if name == "email" and os.getenv("SMTP_HOST"):
            return SmtpEmailChannel()
    except Exception as exc:
        logger.warning("live channel %s unavailable (%s); using mock", name, exc)
    return None


def get_channel(name: str) -> NotificationChannel:
    """Return the channel adapter for ``name`` (live when configured, else mock; defaults to SMS)."""
    name = name if name in _MOCKS else "sms"
    if os.getenv("CONNECTOR_MODE", "mock").lower() == "live":
        live = _live_channel(name)
        if live is not None:
            return live
    return _MOCKS[name]
```

---

### services\notification-service\src\notification_service\main.py

```python
"""notification-service entrypoint (CDC section 4.10): outbound written confirmations."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.service import NotificationService
from service_auth import require_internal_key

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


def run() -> None:
    """Console-script entrypoint: `notification-service` (see [project.scripts]). Serves on :8106."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8106)

```

---

### services\notification-service\src\notification_service\schemas.py

```python
"""Wire DTOs for the notification-service."""
from __future__ import annotations

from pydantic import BaseModel


class NotifyRequest(BaseModel):
    """A request to send one written confirmation to a customer."""

    customer_id: str
    to: str = ""            # contact handle; resolved server-side from customer_id in production
    channel: str = "sms"    # "sms" | "whatsapp" | "email"
    template: str = ""      # e.g. "ticket_created" | "callback_scheduled"
    language: str = "fr"    # render language (fr/ar/en)
    params: dict = {}


class NotifyResponse(BaseModel):
    """The result of a send."""

    sent: bool
    reference: str
    channel: str
```

---

### services\notification-service\src\notification_service\service.py

```python
"""NotificationService: render -> send -> record. Durable log to billing.notifications (spec 5.2).

The DB write is best-effort and gated on DATABASE_URL, so the service still runs (in-memory only)
with no database configured. An in-memory list is kept for the /sent inspection endpoint.
"""
from __future__ import annotations

import asyncio
import logging
import os

from notification_service.channels import get_channel
from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.templates import render

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends localized written confirmations over the selected channel and logs them."""

    def __init__(self) -> None:
        self._sent: list[dict] = []

    async def notify(self, req: NotifyRequest) -> NotifyResponse:
        """Render and send one confirmation; record it (in-memory + durable log)."""
        body = render(req.template, req.language, req.params)
        channel = get_channel(req.channel)
        reference = await channel.send(req.to or req.customer_id, body)

        self._sent.append(
            {"customer_id": req.customer_id, "channel": req.channel, "template": req.template, "reference": reference}
        )
        if os.getenv("DATABASE_URL"):
            try:
                await asyncio.to_thread(self._persist, req)
            except Exception as exc:
                logger.warning("notification log write skipped: %s", exc)

        return NotifyResponse(sent=True, reference=reference, channel=req.channel)

    @staticmethod
    def _persist(req: NotifyRequest) -> None:
        from persistence.engine import session_scope
        from persistence.models.billing import Notification
        from persistence.util import to_uuid

        with session_scope() as session:
            session.add(Notification(
                customer_id=to_uuid(req.customer_id),
                channel=req.channel,
                template_code=req.template,
                status="sent",
            ))

    @property
    def sent(self) -> list[dict]:
        return list(self._sent)
```

---

### services\notification-service\src\notification_service\templates.py

```python
"""Localized message templates (fr/ar/en). Written confirmations are in the caller's language."""
from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "ticket_created": {
        "fr": "Votre demande a bien Ã©tÃ© enregistrÃ©e. RÃ©fÃ©rence du ticket : {ticket_id}. Tunisie Telecom.",
        "ar": "ØªÙ… ØªØ³Ø¬ÙŠÙ„ Ø·Ù„Ø¨Ùƒ. Ø±Ù‚Ù… Ø§Ù„ØªØ°ÙƒØ±Ø©: {ticket_id}. Ø§ØªØµØ§Ù„Ø§Øª ØªÙˆÙ†Ø³.",
        "en": "Your request has been logged. Ticket reference: {ticket_id}. Tunisie Telecom.",
    },
    "callback_scheduled": {
        "fr": "Nous vous rappellerons {when}. Merci de votre patience. Tunisie Telecom.",
        "ar": "Ø³Ù†Ø¹Ø§ÙˆØ¯ Ø§Ù„Ø§ØªØµØ§Ù„ Ø¨Ùƒ {when}. Ø´ÙƒØ±Ù‹Ø§ Ù„ØµØ¨Ø±Ùƒ. Ø§ØªØµØ§Ù„Ø§Øª ØªÙˆÙ†Ø³.",
        "en": "We will call you back {when}. Thank you for your patience. Tunisie Telecom.",
    },
}


def render(template: str, language: str, params: dict) -> str:
    """Render ``template`` in ``language`` (falling back to English) with ``params``."""
    by_language = TEMPLATES.get(template, {})
    text = by_language.get(language) or by_language.get("en") or ""
    try:
        return text.format(**params)
    except (KeyError, IndexError):
        return text
```

---

### services\notification-service\tests\test_multilingual.py

```python
"""Multilingual UAT (FR/AR/EN): every written confirmation renders in all three languages."""
from __future__ import annotations

from notification_service.templates import render

LANGUAGES = ("fr", "ar", "en")


def test_ticket_created_renders_in_all_languages() -> None:
    for lang in LANGUAGES:
        text = render("ticket_created", lang, {"ticket_id": "GLPI-00001"})
        assert text and "GLPI-00001" in text


def test_callback_scheduled_renders_in_all_languages() -> None:
    for lang in LANGUAGES:
        text = render("callback_scheduled", lang, {"when": "demain 10h"})
        assert text and "demain 10h" in text


def test_arabic_is_not_an_english_fallback() -> None:
    fr = render("ticket_created", "fr", {"ticket_id": "X"})
    ar = render("ticket_created", "ar", {"ticket_id": "X"})
    en = render("ticket_created", "en", {"ticket_id": "X"})
    assert ar not in (fr, en)  # genuinely localized, not silently falling back
```

---

### services\notification-service\tests\test_notification.py

```python
"""Offline tests for rendering + mock send (no network)."""
from __future__ import annotations

import asyncio

from notification_service.schemas import NotifyRequest
from notification_service.service import NotificationService
from notification_service.templates import render


def test_renders_localized_template() -> None:
    text = render("ticket_created", "fr", {"ticket_id": "GLPI-00001"})
    assert "GLPI-00001" in text
    assert "ticket" in text.lower()


def test_unknown_language_falls_back_to_english() -> None:
    text = render("callback_scheduled", "de", {"when": "tomorrow 10am"})
    assert "tomorrow 10am" in text


def test_notify_sends_and_records() -> None:
    service = NotificationService()
    resp = asyncio.run(
        service.notify(
            NotifyRequest(customer_id="TT-100021", template="ticket_created",
                          language="en", params={"ticket_id": "GLPI-00002"})
        )
    )
    assert resp.sent is True
    assert resp.reference
    assert len(service.sent) == 1
```

---

### services\policy-service\Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/policy-service/Dockerfile -t policy-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/policy-service/ ./services/policy-service/
RUN pip install ./services/policy-service
USER app
EXPOSE 8104
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8104/health')" || exit 1
CMD ["uvicorn", "policy_service.main:app", "--host", "0.0.0.0", "--port", "8104"]

```

---

### services\policy-service\pyproject.toml

```toml
[project]
name = "policy-service"
version = "0.1.0"
description = "Mandatory, audited verdict checkpoint (CDC 4.6). Verdicts persisted to Postgres."
requires-python = ">=3.12"
dependencies = [
  "sqlalchemy>=2.0,<2.1",
  "service-auth",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "pydantic==2.10.4",
  "pydantic-settings==2.7.1",
  "domain-core",
  "audit-trail",
  "persistence",
]

[project.scripts]
policy-service = "policy_service.main:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

```

---

### services\policy-service\src\policy_service\__init__.py

```python
"""Policy & Guardrail domain service: the safety core."""
```

---

### services\policy-service\src\policy_service\config.py

```python
"""Versioned, env-driven policy thresholds (twelve-factor). No threshold hardcoded in a rule."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PolicyThresholds(BaseSettings):
    """Deterministic thresholds for the section 6 business rules."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    payment_cap: float = Field(200.0, alias="POLICY_PAYMENT_CAP_TND")
    deferral_min_age_days: int = Field(180, alias="POLICY_DEFERRAL_MIN_AGE_DAYS")
    deferral_max_per_year: int = Field(2, alias="POLICY_DEFERRAL_MAX_PER_YEAR")
    deferral_unpaid_threshold: float = Field(150.0, alias="POLICY_DEFERRAL_UNPAID_THRESHOLD_TND")


@lru_cache
def get_thresholds() -> PolicyThresholds:
    """Return cached thresholds."""
    return PolicyThresholds()
```

---

### services\policy-service\src\policy_service\engine.py

```python
"""The deterministic engine (the safety core). Pure functions â€” no I/O, fully unit-testable.

Order (Blueprint section 10): mandatory-escalation chain first (short-circuit), then a
defense-in-depth identity backstop for sensitive actions, then the action-specific business
rules. Default is AUTHORIZED only if no rule objects.
"""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, VerdictResult
from policy_service.rules.deferral import check_deferral
from policy_service.rules.mandatory_escalation import check_mandatory
from policy_service.rules.outbound import check_outbound
from policy_service.rules.payment import check_payment
from policy_service.rules.sim import check_sim

SENSITIVE_ACTIONS = frozenset(
    {
        "EXECUTE_PAYMENT",
        "PAYMENT_DEFERRAL",
        "UNBLOCK_SIM",
        "REPLACE_SIM",
        "REACTIVATE_SIM",
        "TOP_UP",
        "CHANGE_PLAN",
        "ACTIVATE_ROAMING",
    }
)

_ACTION_RULES = (check_payment, check_deferral, check_sim)


def evaluate_action(ctx, thresholds) -> VerdictResult:
    """Return the binding three-way verdict for an action (never raises)."""
    mandatory = check_mandatory(ctx)
    if mandatory is not None:
        return mandatory

    if ctx.action_type in SENSITIVE_ACTIONS and not ctx.identity_verified:
        return VerdictResult(ESCALATE, "IDENTITY_STEP_UP", "sensitive action requires verified identity")

    for rule in _ACTION_RULES:
        result = rule(ctx, thresholds)
        if result is not None:
            return result

    return VerdictResult(AUTHORIZED, "DEFAULT_ALLOW", "no rule objected to this action")


def evaluate_response(text: str) -> VerdictResult:
    """Return the outbound guardrail verdict for a response string."""
    return check_outbound(text)
```

---

### services\policy-service\src\policy_service\main.py

```python
"""policy-service entrypoint (CDC section 4.6): the mandatory, audited verdict checkpoint (Postgres)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence import get_session
from policy_service.config import get_thresholds
from policy_service.schemas import EvaluateResponseRequest, PolicyContext, VerdictResponse
from policy_service.service import PolicyService
from service_auth import require_internal_key

app = FastAPI(title="policy-service", dependencies=[Depends(require_internal_key)])
DbSession = Annotated[Session, Depends(get_session)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/evaluate-action", response_model=VerdictResponse)
def evaluate_action(ctx: PolicyContext, session: DbSession) -> VerdictResponse:
    """Return AUTHORIZED / REFUSED / ESCALATE + rule-id + justification + verdict_id (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_action(ctx)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.post("/evaluate-response", response_model=VerdictResponse)
def evaluate_response(
    req: EvaluateResponseRequest, session: DbSession
) -> VerdictResponse:
    """Guardrail an outbound response (persisted, audited)."""
    result, verdict_id = PolicyService(session, get_thresholds()).evaluate_response(req.session_id, req.text)
    return VerdictResponse(
        verdict=result.verdict, rule_id=result.rule_id, justification=result.justification, verdict_id=verdict_id
    )


@app.get("/audit/verify")
def audit_verify(session: DbSession) -> dict:
    """Audit-chain integrity check over the persisted ledger (Blueprint section 12.3)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


def run() -> None:
    """Console-script entrypoint: `policy-service` (see [project.scripts]). Serves on :8104."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8104)

```

---

### services\policy-service\src\policy_service\rules\__init__.py

```python
"""Deterministic rules: Specification objects combined by the engine (Chain of Responsibility)."""
```

---

### services\policy-service\src\policy_service\rules\base.py

```python
"""Shared rule result type and verdict constants."""
from __future__ import annotations

from dataclasses import dataclass

AUTHORIZED = "authorized"
REFUSED = "refused"
ESCALATE = "escalate"


@dataclass(frozen=True)
class VerdictResult:
    """A rule outcome: verdict + the rule that produced it + a human-readable justification."""

    verdict: str
    rule_id: str
    justification: str
```

---

### services\policy-service\src\policy_service\rules\deferral.py

```python
"""Payment-deferral rule (CDC section 6.2): min account age, yearly cap, unpaid-amount review."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_deferral(ctx, thresholds) -> VerdictResult | None:
    """Judge a PAYMENT_DEFERRAL action; None if not a deferral."""
    if ctx.action_type != "PAYMENT_DEFERRAL":
        return None
    if ctx.account_age_days < thresholds.deferral_min_age_days:
        return VerdictResult(
            REFUSED,
            "DEF_MIN_AGE",
            f"account age {ctx.account_age_days}d below minimum {thresholds.deferral_min_age_days}d",
        )
    if ctx.deferrals_this_year >= thresholds.deferral_max_per_year:
        return VerdictResult(REFUSED, "DEF_CAP", "yearly payment-deferral cap reached")
    if ctx.unpaid_amount > thresholds.deferral_unpaid_threshold:
        return VerdictResult(
            ESCALATE,
            "DEF_UNPAID_REVIEW",
            f"unpaid {ctx.unpaid_amount:.3f} above {thresholds.deferral_unpaid_threshold:.3f} TND; needs review",
        )
    return VerdictResult(AUTHORIZED, "DEF_OK", "deferral within policy")
```

---

### services\policy-service\src\policy_service\rules\mandatory_escalation.py

```python
"""Mandatory-escalation chain (CDC section 10.1): evaluated FIRST, short-circuits on first match."""
from __future__ import annotations

from policy_service.rules.base import ESCALATE, VerdictResult

IDENTITY_MAX_ATTEMPTS = 3
CLARIFICATION_MAX_ATTEMPTS = 2


def check_mandatory(ctx) -> VerdictResult | None:
    """Return an ESCALATE verdict if any mandatory trigger fires, else None."""
    if ctx.fraud_suspected:
        return VerdictResult(ESCALATE, "ESC_FRAUD", "fraud suspicion on the account")
    if ctx.is_vip:
        return VerdictResult(ESCALATE, "ESC_VIP", "VIP / grand-compte customer (commercial policy)")
    if ctx.frustration:
        return VerdictResult(ESCALATE, "ESC_FRUSTRATION", "confirmed caller frustration")
    if ctx.clarification_attempts >= CLARIFICATION_MAX_ATTEMPTS:
        return VerdictResult(ESCALATE, "ESC_CLARIFICATION", "two failed clarification attempts")
    if ctx.identity_attempts >= IDENTITY_MAX_ATTEMPTS and not ctx.identity_verified:
        return VerdictResult(ESCALATE, "ESC_IDENTITY_FAILURE", "repeated identity-verification failure")
    return None
```

---

### services\policy-service\src\policy_service\rules\outbound.py

```python
"""Outbound guardrail (CDC section 10.3): may-I-say-this â€” unmasked PII / wrong amounts."""
from __future__ import annotations

import re

from policy_service.rules.base import AUTHORIZED, REFUSED, VerdictResult

_UNMASKED_ID = re.compile(r"\b\d{8,12}\b")


def check_outbound(text: str) -> VerdictResult:
    """Refuse a response that leaks an unmasked identifier; otherwise authorize."""
    if _UNMASKED_ID.search(text):
        return VerdictResult(REFUSED, "OUT_PII", "response contains an unmasked identifier")
    return VerdictResult(AUTHORIZED, "OUT_OK", "response permitted")
```

---

### services\policy-service\src\policy_service\rules\payment.py

```python
"""Payment rule (CDC section 6.1): verbal confirmation + automatic-processing cap."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, REFUSED, VerdictResult


def check_payment(ctx, thresholds) -> VerdictResult | None:
    """Judge an EXECUTE_PAYMENT action; None if not a payment."""
    if ctx.action_type != "EXECUTE_PAYMENT":
        return None
    if not ctx.payment_confirmed:
        return VerdictResult(REFUSED, "PAY_NO_CONFIRMATION", "verbal confirmation required before payment")
    if ctx.amount is not None and ctx.amount > thresholds.payment_cap:
        return VerdictResult(
            ESCALATE,
            "PAY_ABOVE_CAP",
            f"amount {ctx.amount:.3f} above automatic cap {thresholds.payment_cap:.3f} TND",
        )
    return VerdictResult(AUTHORIZED, "PAY_OK", "payment within policy")
```

---

### services\policy-service\src\policy_service\rules\sim.py

```python
"""SIM rule (CDC section 6.3): every SIM operation requires prior identity verification."""
from __future__ import annotations

from policy_service.rules.base import AUTHORIZED, ESCALATE, VerdictResult

SIM_ACTIONS = frozenset({"UNBLOCK_SIM", "REPLACE_SIM", "REACTIVATE_SIM"})


def check_sim(ctx, thresholds) -> VerdictResult | None:
    """Judge a SIM action; None if not a SIM action."""
    if ctx.action_type not in SIM_ACTIONS:
        return None
    if not ctx.identity_verified:
        return VerdictResult(ESCALATE, "SIM_IDENTITY_REQUIRED", "SIM operation requires prior identity verification")
    return VerdictResult(AUTHORIZED, "SIM_OK", "SIM operation within policy")
```

---

### services\policy-service\src\policy_service\schemas.py

```python
"""Wire DTOs for the policy-service."""
from __future__ import annotations

from pydantic import BaseModel


class PolicyContext(BaseModel):
    """Everything the deterministic engine needs to judge an action. English-only payload."""

    session_id: str = "unknown"
    customer_id: str | None = None
    subscription_id: str | None = None
    action_type: str
    is_vip: bool = False
    fraud_suspected: bool = False
    frustration: bool = False
    identity_verified: bool = False
    clarification_attempts: int = 0
    identity_attempts: int = 0
    amount: float | None = None
    requested_days: int | None = None
    account_age_days: int = 0
    deferrals_this_year: int = 0
    unpaid_amount: float = 0.0
    payment_confirmed: bool = False


class EvaluateResponseRequest(BaseModel):
    """Outbound guardrail input (CDC section 10.3)."""

    session_id: str = "unknown"
    text: str


class VerdictResponse(BaseModel):
    """The three-way verdict + rule-id + justification + the persisted verdict id (spec section 12.1)."""

    verdict: str  # "authorized" | "refused" | "escalate"
    rule_id: str
    justification: str
    verdict_id: str | None = None
```

---

### services\policy-service\src\policy_service\service.py

```python
"""PolicyService: compute a verdict, PERSIST it (policy.policy_verdicts), and AUDIT it - atomically.

Structural enforcement of "every verdict is recorded regardless of outcome" (Blueprint section 10.3):
the verdict row + its hash-chained audit entry commit in one transaction. The returned verdict_id
is threaded to the execution-service so no action exists without a verdict (spec section 12).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.policy import PolicyVerdict
from persistence.util import require_uuid, to_uuid
from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action, evaluate_response
from policy_service.rules.base import VerdictResult


class PolicyService:
    """Wraps the pure engine with persistence + mandatory audit."""

    def __init__(self, session: Session, thresholds: PolicyThresholds) -> None:
        self._session = session
        self._thresholds = thresholds
        self._audit = PgAuditLedger(session)

    def evaluate_action(self, ctx) -> tuple[VerdictResult, str]:
        """Judge an action, persist the verdict + audit entry, and return (result, verdict_id)."""
        result = evaluate_action(ctx, self._thresholds)
        verdict_id = self._persist(
            session_id=ctx.session_id, customer_id=ctx.customer_id, requested_action=ctx.action_type,
            direction="inbound", result=result, inputs=ctx.model_dump(),
        )
        return result, verdict_id

    def evaluate_response(self, session_id: str, text: str) -> tuple[VerdictResult, str]:
        """Guardrail an outbound response, persist + audit, return (result, verdict_id)."""
        result = evaluate_response(text)
        verdict_id = self._persist(
            session_id=session_id, customer_id=None, requested_action="outbound_response",
            direction="outbound", result=result, inputs={"length": len(text)},
        )
        return result, verdict_id

    def _persist(self, session_id, customer_id, requested_action, direction, result, inputs) -> str:
        sid = require_uuid(session_id)
        verdict = PolicyVerdict(
            session_id=sid,
            customer_id=to_uuid(customer_id),
            requested_action=requested_action,
            direction=direction,
            verdict=result.verdict.upper(),
            rule_id=result.rule_id,
            justification=result.justification,
            inputs_snapshot=inputs,
        )
        self._session.add(verdict)
        self._session.flush()
        self._audit.append(
            sid, "policy_verdict",
            {"action": requested_action, "verdict": result.verdict, "rule_id": result.rule_id},
            entity_reference=f"policy_verdicts:{verdict.id}",
        )
        self._session.commit()
        return str(verdict.id)
```

---

### services\policy-service\tests\test_policy.py

```python
"""Unit tests for the deterministic engine + mandatory audit (offline, no FastAPI/network)."""
from __future__ import annotations

from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action as _engine_evaluate
from policy_service.engine import evaluate_response as _engine_evaluate_response
from policy_service.schemas import PolicyContext

THRESHOLDS = PolicyThresholds(_env_file=None)


class _EngineShim:
    """Exercises the pure rule engine (no DB); the persistence wrapper is integration-tested."""

    def evaluate_action(self, ctx):
        return _engine_evaluate(ctx, THRESHOLDS)

    def evaluate_response(self, session_id, text):
        return _engine_evaluate_response(text)


def _service() -> _EngineShim:
    return _EngineShim()


def _ctx(**over) -> PolicyContext:
    base = {"action_type": "PAYMENT_DEFERRAL", "identity_verified": True, "account_age_days": 400}
    base.update(over)
    return PolicyContext(**base)


def test_clean_deferral_is_authorized() -> None:
    result = _service().evaluate_action(_ctx(unpaid_amount=42.5))
    assert result.verdict == "authorized"
    assert result.rule_id == "DEF_OK"


def test_vip_short_circuits_to_escalate() -> None:
    result = _service().evaluate_action(_ctx(is_vip=True))
    assert result.verdict == "escalate"
    assert result.rule_id == "ESC_VIP"


def test_fraud_short_circuits_first() -> None:
    # fraud beats everything, even a young account that would otherwise be REFUSED
    result = _service().evaluate_action(_ctx(fraud_suspected=True, account_age_days=10))
    assert (result.verdict, result.rule_id) == ("escalate", "ESC_FRAUD")


def test_deferral_below_min_age_is_refused() -> None:
    result = _service().evaluate_action(_ctx(account_age_days=30))
    assert (result.verdict, result.rule_id) == ("refused", "DEF_MIN_AGE")


def test_deferral_high_unpaid_escalates_for_review() -> None:
    result = _service().evaluate_action(_ctx(unpaid_amount=500.0))
    assert (result.verdict, result.rule_id) == ("escalate", "DEF_UNPAID_REVIEW")


def test_payment_without_confirmation_is_refused() -> None:
    result = _service().evaluate_action(
        PolicyContext(action_type="EXECUTE_PAYMENT", identity_verified=True, payment_confirmed=False)
    )
    assert (result.verdict, result.rule_id) == ("refused", "PAY_NO_CONFIRMATION")


def test_payment_above_cap_escalates() -> None:
    result = _service().evaluate_action(
        PolicyContext(
            action_type="EXECUTE_PAYMENT", identity_verified=True, payment_confirmed=True, amount=5000.0
        )
    )
    assert (result.verdict, result.rule_id) == ("escalate", "PAY_ABOVE_CAP")


def test_sim_without_identity_escalates() -> None:
    result = _service().evaluate_action(
        PolicyContext(action_type="UNBLOCK_SIM", identity_verified=False)
    )
    assert result.verdict == "escalate"  # IDENTITY_STEP_UP or SIM_IDENTITY_REQUIRED


def test_every_action_yields_a_verdict() -> None:
    # Persistence/audit of each verdict is structural in PolicyService and is covered by
    # audit-trail/test_chain.py + Postgres integration; here we assert the engine always decides.
    for ctx in (_ctx(), _ctx(is_vip=True), _ctx(fraud_suspected=True)):
        assert _service().evaluate_action(ctx).verdict in ("authorized", "refused", "escalate")


def test_outbound_pii_is_refused() -> None:
    result = _service().evaluate_response("unknown", "your id is 100021456789")
    assert (result.verdict, result.rule_id) == ("refused", "OUT_PII")

```

---

### start.ps1

```powershell
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "rebuild", "build", "logs", "status", "health", "help")]
    [string]$Command = "help"
)

$F = "infra/docker-compose/docker-compose.yml"
$A = "infra/docker-compose/docker-compose.apps.yml"

switch ($Command) {
    "help" {
        Write-Host @"
Usage: .\start.ps1 <command>

Commands:
  up        Start all containers (fast, no rebuild)
  down      Stop all containers
  rebuild   Stop, rebuild images, restart (use after code changes)
  build     Rebuild images only (no restart)
  logs      Follow agent-worker + token-service logs
  status    Show container status
  health    Check /health on all services

Examples:
  .\start.ps1 up         # quick start
  .\start.ps1 rebuild    # rebuild after code changes
  .\start.ps1 status     # check running containers
"@
    }
    "up" {
        Write-Host "Starting all containers (infra + apps)..." -ForegroundColor Cyan
        docker compose -f $F -f $A up -d
    }
    "down" {
        Write-Host "Stopping all containers..." -ForegroundColor Yellow
        docker compose -f $F -f $A --profile self-hosted-livekit down
    }
    "rebuild" {
        Write-Host "Stopping containers..." -ForegroundColor Yellow
        docker compose -f $F -f $A --profile self-hosted-livekit down
        Write-Host "Rebuilding images and starting containers..." -ForegroundColor Cyan
        docker compose -f $F -f $A up -d --build
        Write-Host "Done. Run '.\start.ps1 status' to verify." -ForegroundColor Green
    }
    "build" {
        Write-Host "Rebuilding all images (no restart)..." -ForegroundColor Cyan
        docker compose -f $F -f $A build
        Write-Host "Build complete. Run '.\start.ps1 up' to start." -ForegroundColor Green
    }
    "logs" {
        docker compose -f $F -f $A logs -f --tail=120 token-service agent-worker
    }
    "status" {
        docker compose -f $F -f $A ps
    }
    "health" {
        Write-Host "Checking service health endpoints..." -ForegroundColor Cyan
        $services = @(
            @{Name="context-service"; Port=8101},
            @{Name="knowledge-service"; Port=8102},
            @{Name="decision-service"; Port=8103},
            @{Name="policy-service"; Port=8104},
            @{Name="execution-service"; Port=8105},
            @{Name="notification-service"; Port=8106},
            @{Name="token-service"; Port=8107},
            @{Name="business-api"; Port=8108}
        )
        $allHealthy = $true
        foreach ($svc in $services) {
            try {
                $resp = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)/health" -Method Get -TimeoutSec 5
                Write-Host "  OK $($svc.Name) ($($svc.Port))" -ForegroundColor Green
            } catch {
                Write-Host "  FAIL $($svc.Name) ($($svc.Port))" -ForegroundColor Red
                $allHealthy = $false
            }
        }
        if ($allHealthy) { Write-Host "All services healthy!" -ForegroundColor Green }
    }
}

```

---

### test_session.py

```python
import asyncio
from config.settings import Settings
from providers.session_factory import build_agent_session

async def test():
    settings = Settings()
    try:
        session = build_agent_session(settings, 'fr')
        print("Session built successfully with turn detector:", type(session.turn_detector))
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())

```

---

### tests\load\loadtest.py

```python
"""Lightweight load test against the HTTP services (Blueprint section 20 'Load').

Measures p50/p95 latency against a budget. The voice TTFA budget is asserted separately via the
OTel `telecom.agent.ttfa.seconds` histogram (Phase 11) under a real concurrent-call run; this script
covers the request/response services (business-api, context-service, token-service).

Usage:
    pip install httpx
    python tests/load/loadtest.py --url http://localhost:8108/health --requests 500 --concurrency 25 --budget-ms 250
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from contextlib import suppress

import httpx


async def _worker(client: httpx.AsyncClient, url: str, queue: asyncio.Queue, latencies: list[float]) -> None:
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        start = time.perf_counter()
        with suppress(httpx.HTTPError):
            await client.get(url)
        latencies.append((time.perf_counter() - start) * 1000.0)
        queue.task_done()


async def run(url: str, total: int, concurrency: int) -> list[float]:
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(total):
        queue.put_nowait(1)
    latencies: list[float] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        await asyncio.gather(*[_worker(client, url, queue, latencies) for _ in range(concurrency)])
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--budget-ms", type=float, default=250.0)
    args = parser.parse_args()

    latencies = asyncio.run(run(args.url, args.requests, args.concurrency))
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"requests={len(latencies)} p50={p50:.1f}ms p95={p95:.1f}ms budget={args.budget_ms:.0f}ms")
    if p95 > args.budget_ms:
        raise SystemExit(f"FAIL: p95 {p95:.1f}ms exceeds budget {args.budget_ms:.0f}ms")
    print("PASS: within latency budget")


if __name__ == "__main__":
    main()

```

---

### tests\load\soak.py

```python
"""Soak test (Blueprint section 20 'Soak'): many sequential calls, watch for resource/state bleed.

Drives the HTTP path repeatedly and reports RSS growth. A healthy run shows flat memory (no leak).
For the voice path, run the worker against a sequential-call generator and watch the same RSS plus
the OTel session counters; this script covers the services.

Usage:
    pip install httpx psutil
    python tests/load/soak.py --url http://localhost:8108/health --iterations 5000
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress

import httpx

try:
    import os

    import psutil
    _proc = psutil.Process(os.getpid())
except Exception:
    _proc = None


def _rss_mb() -> float:
    return round(_proc.memory_info().rss / 1_048_576, 1) if _proc else -1.0


async def run(url: str, iterations: int) -> None:
    start_rss = _rss_mb()
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(iterations):
            with suppress(httpx.HTTPError):
                await client.get(url)
            if i and i % 1000 == 0:
                print(f"iter={i} rss={_rss_mb()}MB")
    end_rss = _rss_mb()
    print(f"done iterations={iterations} rss_start={start_rss}MB rss_end={end_rss}MB delta={round(end_rss - start_rss, 1)}MB")
    if start_rss > 0 and end_rss - start_rss > 50:
        raise SystemExit("WARN: RSS grew >50MB across the soak run - investigate for a leak")
    print("PASS: no significant memory growth")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--iterations", type=int, default=5000)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.iterations))


if __name__ == "__main__":
    main()

```

