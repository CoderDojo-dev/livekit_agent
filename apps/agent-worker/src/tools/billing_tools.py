"""Read-only billing tools (CDC section 5.1). No policy check — read-only, not sensitive.

Sensitive billing write paths (payment, deferral) live in billing_agent.py / Phase 7 and run
the Decision -> Policy -> Execution façade. These tools only read, via the context-service.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from clients.context_client import get_context_client


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