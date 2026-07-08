"""Technical tool facades: data diagnosis, SIM ops, network status.

Local-safe implementations: no NotImplementedError, no silent hangs. Real NMS/OSS adapters
can replace these later behind the same tool contracts.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from clients.context_client import get_context_client
from tools import outcomes
from tools.guarded_action import execute_guarded_action
from tools.guards import ensure_identity_verified


@function_tool()
async def diagnose_data_issue(context: RunContext) -> dict:
    """Check basic account signals for a data/connectivity complaint."""
    user_data = context.session.userdata
    customer = user_data.customer_context
    if customer is None:
        return {
            "outcome": "unavailable",
            "message": (
                "I can't see an active line for this number yet. "
                "Ask the caller to confirm the line or escalate."
            ),
        }

    balance = await get_context_client().get_balance(customer.customer_id)
    return {
        "outcome": "diagnosed",
        "customer_id": customer.customer_id,
        "subscription_type": customer.subscription_type,
        "balance": balance,
        "message": (
            "Basic line context was checked. If balance is missing or the issue persists, "
            "offer to create a technical ticket."
        ),
    }


@function_tool()
async def unblock_sim_pin(context: RunContext) -> dict:
    """Unblock the caller's SIM/PIN. Identity-gated, then Decision -> Policy -> Execution."""
    if not await ensure_identity_verified(context):
        return outcomes.escalate("IDENTITY_REQUIRED", "identity not verified")
    return await execute_guarded_action(context, "UNBLOCK_SIM", {})


@function_tool()
async def check_network_status(area: str) -> dict:
    """Read-only known-incident lookup for local/dev. Replace with NMS adapter later."""
    normalized = (area or "").strip()
    if not normalized:
        return {
            "outcome": "needs_area",
            "message": "Ask the caller for their city, area, or neighborhood.",
        }

    return {
        "outcome": "checked",
        "area": normalized,
        "incident_found": False,
        "message": (
            "No known incident is available in the local pilot data for this area. "
            "If the caller still has trouble, create a technical ticket."
        ),
    }
