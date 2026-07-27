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
async def check_network_status(context: RunContext, area: str) -> dict:
    """Check whether a known network incident affects the caller's area.

    Reads live incident data from the NMS/OSS service. When the service cannot be reached the
    outcome is "unavailable" - say so honestly rather than telling the caller the network is fine,
    which we would not actually know.

    Args:
        area: The caller's city, area, or neighborhood.
    """
    from clients.nms_client import get_nms_client

    language = getattr(context.session.userdata, "language", "fr") or "fr"
    # If language is an enum or object, extract the string value
    if hasattr(language, "value"):
        language = language.value
    language = str(language).lower().strip()[:2] if language else "fr"

    normalized = (area or "").strip()
    if not normalized:
        return {
            "outcome": "area_unknown",
            "did_verify": False,
            "message": "Ask the caller for their city, area, or neighborhood.",
        }

    status = await get_nms_client().get_network_status(normalized, language)
    state = status.get("status")

    if state == "unavailable":
        return {
            "outcome": "unavailable",
            "area": normalized,
            "did_verify": False,
            "message": (
                "The network supervision system could not be reached, so NO incident check "
                "was possible. Tell the caller honestly that you cannot verify the network "
                "right now and that you will follow up; do NOT claim the network is fine."
            ),
        }

    if state == "area_unknown":
        suggestions = status.get("suggestions") or []
        return {
            "outcome": "area_unknown",
            "area": normalized,
            "did_verify": False,
            "suggestions": suggestions,
            "message": (
                "This area was NOT recognised, so NOTHING was verified. You must NOT say "
                "the network is fine. Ask the caller to confirm their exact city or "
                "delegation"
                + (
                    f", suggesting one of: {', '.join(suggestions)}."
                    if suggestions
                    else "."
                )
            ),
        }

    if status.get("match") == "approximate":
        return {
            "outcome": "needs_area_confirmation",
            "area_heard": normalized,
            "candidate": status.get("verified_area"),
            "did_verify": False,
            "suggestions": status.get("suggestions") or [],
            "message": (
                "The place name was only matched approximately, so NOTHING is "
                "confirmed. Ask the caller to confirm the candidate area by name "
                "before saying anything about the network. Never say the network "
                "is fine at this stage."
            ),
        }

    outages = status.get("outages") or []
    verified_area = status.get("verified_area") or normalized
    coverage = status.get("coverage")

    if not outages:
        return {
            "outcome": "checked",
            "area": verified_area,
            "did_verify": True,
            "incident_found": False,
            "message": (
                f"Verified against the supervision system for {verified_area}: no active "
                "incident is declared. You MAY tell the caller the network is normal there. "
                "If they still have trouble, run a diagnostic or open a technical ticket."
            ),
        }

    first = outages[0]
    return {
        "outcome": "checked",
        "area": verified_area,
        "did_verify": True,
        "incident_found": True,
        "coverage": coverage,
        "severity": first.get("severity"),
        "cause": first.get("cause"),
        "description": first.get("description"),
        "affected_services": first.get("affected_services", []),
        "eta": first.get("eta"),
        "outages": outages,
        "message": (
            "A known incident affects this area. Explain to the caller in their own "
            "language what is happening using 'description', mention the affected services "
            "and the estimated restoration time when given, and do not open a duplicate "
            "ticket for the same outage. If 'description' is empty, say only that an "
            "incident is identified and being worked on - never invent a cause."
            + (
                " When coverage is 'partial', an incident exists inside the area the caller"
                " named but not necessarily at their exact location: say that an incident is"
                " reported in part of that area and ask which delegation they are in."
                if coverage == "partial"
                else ""
            )
        ),
    }
