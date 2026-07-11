"""Identity-gated personal billing reads."""
from __future__ import annotations

from clients.context_client import get_context_client
from livekit.agents import RunContext, function_tool

from tools import outcomes
from tools.guards import ensure_identity_verified


async def _verified_customer(context: RunContext):
    user_data = context.session.userdata
    customer = user_data.customer_context
    if customer is None:
        return None, outcomes.escalate(
            "UNKNOWN_CALLER",
            "No customer context is available.",
        )

    if not await ensure_identity_verified(context):
        return None, outcomes.escalate(
            "IDENTITY_REQUIRED",
            "Identity verification is required.",
        )

    return customer, None


@function_tool()
async def get_invoice_summary(context: RunContext) -> dict:
    """Return the verified caller's latest invoice."""
    customer, error = await _verified_customer(context)
    if error:
        return error

    invoices = await get_context_client().get_invoices(customer.customer_id)
    if not invoices:
        return {
            "outcome": "no_open_invoice",
            "message": "No invoice is currently available.",
        }

    latest = invoices[0]
    amount = latest["amount"]
    currency = latest.get("currency", "TND")
    return {
        "outcome": "success",
        "amount_due": amount,
        "currency": currency,
        "due_date": latest["due_date"],
        "status": latest["status"],
        "message": (
            f"Your latest invoice is {amount:.3f} {currency}, "
            f"due on {latest['due_date']}, status {latest['status']}."
        ),
    }


@function_tool()
async def get_balance_summary(context: RunContext) -> dict:
    """Return prepaid balance or postpaid outstanding invoice information."""
    customer, error = await _verified_customer(context)
    if error:
        return error

    if customer.subscription_type.upper() == "PREPAID":
        balance = await get_context_client().get_balance(customer.customer_id)
        if balance is None:
            return {
                "outcome": "no_balance_on_file",
                "message": "No prepaid balance is available.",
            }

        credit = balance["credit"]
        currency = balance.get("currency", "TND")
        data_mb = balance.get("data_remaining_mb", 0)
        return {
            "outcome": "success",
            "account_type": "prepaid",
            "credit": credit,
            "currency": currency,
            "data_remaining_mb": data_mb,
            "message": (
                f"Your prepaid credit is {credit:.3f} {currency}, "
                f"with {data_mb} MB remaining."
            ),
        }

    invoices = await get_context_client().get_invoices(customer.customer_id)
    if not invoices:
        return {
            "outcome": "success",
            "account_type": "postpaid",
            "amount_due": 0.0,
            "currency": "TND",
            "message": "Your postpaid account has no invoice on file.",
        }

    latest = invoices[0]
    amount = latest["amount"]
    currency = latest.get("currency", "TND")
    return {
        "outcome": "success",
        "account_type": "postpaid",
        "amount_due": amount,
        "currency": currency,
        "status": latest["status"],
        "due_date": latest["due_date"],
        "message": (
            f"Your current postpaid invoice is {amount:.3f} {currency}, "
            f"status {latest['status']}."
        ),
    }
