"""Technical tool facades: data diagnosis, SIM ops, network status.

Local-safe implementations: no NotImplementedError, no silent hangs. Real NMS/OSS adapters
can replace these later behind the same tool contracts.
"""
from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool

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
    """Check whether a known network incident affects the caller's area.

    Reads live incident data from the NMS/OSS service. When the service cannot be reached the
    outcome is "unavailable" - say so honestly rather than telling the caller the network is fine,
    which we would not actually know.

    Args:
        area: The caller's city, area, or neighborhood.
    """
    from clients.nms_client import get_nms_client

    normalized = (area or "").strip()
    if not normalized:
        return {
            "outcome": "needs_area",
            "message": "Ask the caller for their city, area, or neighborhood.",
        }

    status = await get_nms_client().get_network_status(normalized)

    if status.get("status") == "unavailable":
        return {
            "outcome": "unavailable",
            "area": normalized,
            "message": (
                "The network supervision system could not be reached, so no incident check was "
                "possible. Tell the caller honestly that you cannot verify the network right now "
                "and will follow up; do NOT claim the network is fine."
            ),
        }

    outages = status.get("outages") or []
    if not outages:
        return {
            "outcome": "checked",
            "area": normalized,
            "incident_found": False,
            "message": (
                "No known incident affects this area. If the caller still has trouble, run a "
                "diagnostic or open a technical ticket."
            ),
        }

    first = outages[0]
    return {
        "outcome": "checked",
        "area": normalized,
        "incident_found": True,
        "severity": first.get("severity"),
        "affected_services": first.get("affected_services", []),
        "eta": first.get("eta"),
        "outages": outages,
        "message": (
            "A known incident affects this area. Tell the caller it is already identified and "
            "being worked on, mention the affected services and the estimated restoration time "
            "when one is given, and do not open a duplicate ticket for the same outage."
        ),
    }
