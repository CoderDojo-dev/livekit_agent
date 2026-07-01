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