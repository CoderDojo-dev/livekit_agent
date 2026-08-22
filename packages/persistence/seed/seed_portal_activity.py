"""Seed the customer portal's Requests and Activity surfaces with a realistic history.

WHY THIS EXISTS
---------------
Every endpoint the portal reads works, and has worked: `me_reads.requests`, `.conversations`,
`.conversation_detail`, `.callbacks` and `.notifications` all return real rows through the real
projections, and the agent's own `create_support_ticket` path (GLPI -> `mirror_create` ->
`ticketing.tickets`) demonstrably lands rows a signed-in customer can see.

The problem was never the pipeline. It was COVERAGE. `seed_pilot` inserts three customers with
their lines, invoices and balances and stops there, so:

  - only the customer who happened to be used for live agent testing had any tickets at all, and
    every one of them was `open` — the Requests screen's "Resolved" tab was empty by construction;
  - the other two pilot customers had no tickets, no callbacks, no notifications and no payments,
    so whichever of them you signed in as, Requests and Activity were four empty states;
  - the callbacks that did exist carried `reason = NULL`, which the Activity list renders as an
    em dash — a row that says nothing.

This seed gives all three customers a history that exercises every branch the two screens can
render: all five ticket statuses, all five categories, all four dispositions, all three callback
statuses, all three notification channels and statuses, every payment method, and conversations
with REAL turn rows so the transcript, the cadence strip and the turn-density bars have something
true to draw.

WHAT IT IS NOT
--------------
It is not mock data in the sense of fake plumbing: every row goes through the ORM into the same
tables the agent writes at runtime, and is read back through the same projections. Delete a row
here and the screen loses it; open a real ticket on a call and it appears alongside these. The
only thing "seeded" is that a human did not have to hold twenty conversations to produce it.

IDEMPOTENT, and deliberately never on a TIMESTAMP. Every time in this file is derived from
`NOW`, so a guard that compares timestamps matches nothing on the second run and the whole block
inserts itself again. Each insert is therefore guarded on a genuinely stable identity:
`glpi_ticket_id`, `livekit_room`, `idempotency_key`, or — where the table has no natural key —
the tuple that is unique within a customer's spec list ((customer, reason, status) for callbacks,
(customer, channel, template, status) for notifications).

    DATABASE_URL=... python -m seed.seed_portal_activity
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.billing import Account, Invoice, Notification, Payment
from persistence.models.conversation import CallbackSchedule, CallSession, Turn
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import Recharge
from persistence.models.ticketing import Ticket

NOW = datetime.now(UTC)

# Reference prefix for everything this script writes, so a seeded ticket is distinguishable from
# an agent-created GLPI-<n> one at a glance and in a WHERE clause.
SEED_PREFIX = "PS"


def _ago(days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


def _ahead(days: float = 0, hours: float = 0) -> datetime:
    return NOW + timedelta(days=days, hours=hours)


# ---------------------------------------------------------------------------------------------
# Tickets
#
# Five statuses and five categories across the three customers, with subjects written in the
# customer's own preferred language — the agent files a ticket in the language the call was held
# in, so a history that is all French for an Arabic-speaking caller would be the wrong shape.
# ---------------------------------------------------------------------------------------------
TICKETS: dict[str, list[dict]] = {
    "11224087": [  # Amine — fr, postpaid
        {
            "ref": "PS-1001", "category": "billing", "priority": "high", "status": "in_progress",
            "subject": "Facture d'avril plus élevée que d'habitude",
            "opened": _ago(days=9, hours=3), "changed": _ago(days=1, hours=2),
        },
        {
            "ref": "PS-1002", "category": "network_complaint", "priority": "urgent",
            "status": "pending",
            "subject": "Coupures répétées le soir à Tunis centre",
            "opened": _ago(days=6, hours=8), "changed": _ago(days=2),
        },
        {
            "ref": "PS-1003", "category": "technical", "priority": "medium", "status": "resolved",
            "subject": "Configuration APN après changement de téléphone",
            "opened": _ago(days=24), "changed": _ago(days=21, hours=5),
        },
        {
            "ref": "PS-1004", "category": "formal_complaint", "priority": "high",
            "status": "closed",
            "subject": "Réclamation formelle — délai de rétablissement",
            "opened": _ago(days=58), "changed": _ago(days=44),
        },
    ],
    "33449912": [  # Yousra — ar, prepaid, VIP
        {
            "ref": "PS-2001", "category": "technical", "priority": "high", "status": "open",
            "subject": "الإنترنت بطيء جدا في المساء",
            "opened": _ago(days=2, hours=4), "changed": _ago(days=2, hours=4),
        },
        {
            "ref": "PS-2002", "category": "billing", "priority": "medium",
            "status": "in_progress",
            "subject": "رصيد لم يُضف بعد التعبئة",
            "opened": _ago(days=5), "changed": _ago(hours=20),
        },
        {
            "ref": "PS-2003", "category": "other", "priority": "low", "status": "resolved",
            "subject": "تغيير لغة المكالمات إلى العربية",
            "opened": _ago(days=31), "changed": _ago(days=30, hours=2),
        },
    ],
    "55662256": [  # Karim — en, fibre, overdue
        {
            "ref": "PS-3001", "category": "technical", "priority": "urgent", "status": "open",
            "subject": "Fibre box offline since Tuesday morning",
            "opened": _ago(days=1, hours=6), "changed": _ago(days=1, hours=6),
        },
        {
            "ref": "PS-3002", "category": "billing", "priority": "high", "status": "pending",
            "subject": "Dispute on the overdue April invoice",
            "opened": _ago(days=11), "changed": _ago(days=3, hours=9),
        },
        {
            "ref": "PS-3003", "category": "network_complaint", "priority": "medium",
            "status": "resolved",
            "subject": "Slow upload speeds on the home line",
            "opened": _ago(days=40), "changed": _ago(days=36),
        },
        {
            "ref": "PS-3004", "category": "other", "priority": "low", "status": "closed",
            "subject": "Request for a paper copy of the contract",
            "opened": _ago(days=75), "changed": _ago(days=70),
        },
    ],
}


# ---------------------------------------------------------------------------------------------
# Conversations
#
# Each entry produces a call_sessions row AND its turns. The turns matter: the portal's transcript,
# its cadence strip and the per-row turn-density bars all read `conversation.turns`, so a session
# with no turns renders as a conversation that apparently contained no words.
#
# Transcripts are written as the pii-shield would leave them — already masked — because that is
# what the column stores (`transcript_masked`).
# ---------------------------------------------------------------------------------------------
CONVERSATIONS: dict[str, list[dict]] = {
    "11224087": [
        {
            "room": "ps-amine-001", "started": _ago(days=1, hours=2), "duration": 214,
            "disposition": "resolved", "language": "fr",
            "turns": [
                ("caller", "TriageAgent", "Bonjour, ma facture d'avril me semble trop élevée."),
                ("agent", "TriageAgent", "Bonjour. Je regarde votre facture d'avril tout de suite."),
                ("agent", "BillingAgent", "Votre facture d'avril est de 42,500 dinars, contre 31,200 en mars."),
                ("caller", "BillingAgent", "D'où vient la différence ?"),
                ("agent", "BillingAgent", "Un hors-forfait de 11,300 dinars pour des appels internationaux le 14 avril."),
                ("caller", "BillingAgent", "D'accord, c'était moi. Est-ce que je peux étaler le paiement ?"),
                ("agent", "BillingAgent", "Oui. J'ouvre une demande pour un échelonnement sur deux mois."),
                ("caller", "BillingAgent", "Parfait, merci beaucoup."),
            ],
        },
        {
            "room": "ps-amine-002", "started": _ago(days=6, hours=9), "duration": 168,
            "disposition": "escalated", "language": "fr",
            "turns": [
                ("caller", "TriageAgent", "J'ai des coupures tous les soirs depuis une semaine."),
                ("agent", "TriageAgent", "Je vérifie s'il y a un incident connu sur votre zone."),
                ("agent", "TechnicalAgent", "Il y a bien une saturation signalée à Tunis centre le soir."),
                ("caller", "TechnicalAgent", "Et ça va durer combien de temps ?"),
                ("agent", "TechnicalAgent", "Je ne peux pas vous donner de délai fiable, je passe le dossier à un spécialiste."),
                ("agent", "ManagerAgent", "Bonjour, je prends le relais sur votre dossier."),
            ],
        },
        {
            "room": "ps-amine-003", "started": _ago(days=21, hours=4), "duration": 96,
            "disposition": "resolved", "language": "fr",
            "turns": [
                ("caller", "TriageAgent", "Je viens de changer de téléphone et je n'ai plus internet."),
                ("agent", "TriageAgent", "Je vais vous renvoyer les paramètres APN par message."),
                ("agent", "TechnicalAgent", "C'est envoyé. Redémarrez le téléphone après l'avoir enregistré."),
                ("caller", "TechnicalAgent", "Ça marche, merci."),
            ],
        },
        {
            "room": "ps-amine-004", "started": _ago(days=34), "duration": 41,
            "disposition": "abandoned", "language": "fr",
            "turns": [
                ("caller", "TriageAgent", "Allo ? Je vous entends mal."),
                ("agent", "TriageAgent", "Je vous entends. En quoi puis-je vous aider ?"),
            ],
        },
    ],
    "33449912": [
        {
            "room": "ps-yousra-001", "started": _ago(hours=20), "duration": 132,
            "disposition": "resolved", "language": "ar",
            "turns": [
                ("caller", "TriageAgent", "عبيت رصيد اليوم الصباح وما وصلش."),
                ("agent", "TriageAgent", "نتثبت في آخر عملية تعبئة على خطك."),
                ("agent", "BillingAgent", "التعبئة بـ 20 دينار وصلت وتسجلت على الخط متاعك."),
                ("caller", "BillingAgent", "أما الرصيد يبان 7 دينار برك."),
                ("agent", "BillingAgent", "الفرق راهو استهلاك انترنت. نبعثلك التفصيل بالرسالة."),
                ("caller", "BillingAgent", "برشا برشا، شكرا."),
            ],
        },
        {
            "room": "ps-yousra-002", "started": _ago(days=3, hours=7), "duration": 88,
            "disposition": "resolved", "language": "ar",
            "turns": [
                ("caller", "TriageAgent", "نحب نبدل لغة المكالمات للعربية."),
                ("agent", "TriageAgent", "تم. المكالمات الجاية باش تبدا بالعربية."),
                ("caller", "TriageAgent", "شكرا."),
            ],
        },
        {
            "room": "ps-yousra-003", "started": _ago(days=12), "duration": 57,
            "disposition": "dropped", "language": "ar",
            "turns": [
                ("caller", "TriageAgent", "الانترنت بطيء برشا في الليل."),
                ("agent", "TriageAgent", "نتثبت في الشبكة متاع منطقتك."),
            ],
        },
    ],
    "55662256": [
        {
            "room": "ps-karim-001", "started": _ago(days=1, hours=7), "duration": 245,
            "disposition": "escalated", "language": "en",
            "turns": [
                ("caller", "TriageAgent", "My fibre box has been offline since Tuesday morning."),
                ("agent", "TriageAgent", "Let me check the line status for your address."),
                ("agent", "TechnicalAgent", "The line is showing as down at the exchange, not at your box."),
                ("caller", "TechnicalAgent", "So it is on your side. When will it be fixed?"),
                ("agent", "TechnicalAgent", "I cannot give you a reliable time from here."),
                ("caller", "TechnicalAgent", "This is the third day. I want someone who can."),
                ("agent", "ManagerAgent", "I am taking over your case now and I will arrange a callback."),
                ("caller", "ManagerAgent", "Thank you, that is what I needed."),
            ],
        },
        {
            "room": "ps-karim-002", "started": _ago(days=11, hours=2), "duration": 187,
            "disposition": "resolved", "language": "en",
            "turns": [
                ("caller", "TriageAgent", "I want to dispute the April invoice."),
                ("agent", "TriageAgent", "I will pull it up and open a dispute for you."),
                ("agent", "BillingAgent", "April is 73,900 dinars and is currently marked overdue."),
                ("caller", "BillingAgent", "I was not connected for half of that month."),
                ("agent", "BillingAgent", "Understood. I have opened a billing dispute with that reason."),
                ("caller", "BillingAgent", "Good. Will the late fee be held?"),
                ("agent", "BillingAgent", "The account is held from further dunning while the dispute is open."),
            ],
        },
        {
            "room": "ps-karim-003", "started": _ago(days=36, hours=5), "duration": 121,
            "disposition": "resolved", "language": "en",
            "turns": [
                ("caller", "TriageAgent", "Upload speeds on the home line are very slow."),
                ("agent", "TechnicalAgent", "I have re-provisioned the profile on your line."),
                ("caller", "TechnicalAgent", "It looks better now, thanks."),
            ],
        },
    ],
}


# ---------------------------------------------------------------------------------------------
# Callbacks — the Activity screen's "Calls" tab.
#
# Every one carries a `reason`: the list renders the reason as the row's headline, and a NULL
# reason produces a row whose only content is an em dash.
# ---------------------------------------------------------------------------------------------
CALLBACKS: dict[str, list[dict]] = {
    "11224087": [
        {"when": _ahead(days=1, hours=3), "status": "pending", "reason": "billing",
         "window": "Weekdays 09:00–12:00", "attempts": 0},
        {"when": _ago(days=5), "status": "completed", "reason": "technical",
         "window": "Afternoons", "attempts": 1, "note": "Reached the customer; APN settings resent."},
        {"when": _ago(days=19), "status": "cancelled", "reason": "billing",
         "window": "Mornings", "attempts": 2, "note": "Customer resolved it on the app before we called."},
    ],
    "33449912": [
        {"when": _ahead(hours=20), "status": "pending", "reason": "technical",
         "window": "بعد الخامسة مساء", "attempts": 0},
        {"when": _ago(days=9), "status": "completed", "reason": "other",
         "window": "Mornings", "attempts": 1, "note": "Language preference confirmed with the customer."},
    ],
    "55662256": [
        {"when": _ahead(hours=4), "status": "pending", "reason": "technical",
         "window": "Any time today", "attempts": 1},
        {"when": _ago(days=12), "status": "completed", "reason": "billing",
         "window": "Weekdays 14:00–17:00", "attempts": 1, "note": "Dispute reference given to the customer."},
    ],
}


# ---------------------------------------------------------------------------------------------
# Notifications — the Activity screen's "Messages" tab and the topbar tray.
#
# Only template codes the portal's copy deck can name are used (copy.notificationTemplates);
# anything else renders as the generic fallback and teaches the reader nothing.
# ---------------------------------------------------------------------------------------------
NOTIFICATIONS: dict[str, list[dict]] = {
    "11224087": [
        {"channel": "whatsapp", "template": "ticket_update", "status": "sent", "at": _ago(days=1, hours=1)},
        {"channel": "sms", "template": "invoice_ready", "status": "sent", "at": _ago(days=4)},
        {"channel": "email", "template": "payment_received", "status": "sent", "at": _ago(days=7, hours=6)},
        {"channel": "sms", "template": "callback_scheduled", "status": "queued", "at": _ago(hours=5)},
        {"channel": "whatsapp", "template": "payment_failed", "status": "failed",
         "at": _ago(days=14), "failure": "Recipient has not opted in to WhatsApp business messages"},
    ],
    "33449912": [
        {"channel": "sms", "template": "payment_received", "status": "sent", "at": _ago(hours=19)},
        {"channel": "whatsapp", "template": "ticket_created", "status": "sent", "at": _ago(days=2, hours=3)},
        {"channel": "sms", "template": "callback_scheduled", "status": "queued", "at": _ago(hours=2)},
        {"channel": "email", "template": "invoice_ready", "status": "failed",
         "at": _ago(days=22), "failure": "Mailbox full"},
    ],
    "55662256": [
        {"channel": "email", "template": "invoice_ready", "status": "sent", "at": _ago(days=1, hours=4)},
        {"channel": "sms", "template": "payment_failed", "status": "sent", "at": _ago(days=3)},
        {"channel": "whatsapp", "template": "ticket_update", "status": "sent", "at": _ago(days=1, hours=5)},
        {"channel": "sms", "template": "callback_scheduled", "status": "queued", "at": _ago(hours=3)},
        {"channel": "email", "template": "plan_changed", "status": "sent", "at": _ago(days=48)},
    ],
}


# Payments — Billing's payments section. Every method the CHECK constraint allows.
PAYMENTS: dict[str, list[dict]] = {
    "11224087": [
        {"amount": 31.200, "method": "card", "status": "succeeded", "at": _ago(days=36)},
        {"amount": 29.800, "method": "wallet", "status": "succeeded", "at": _ago(days=67)},
        {"amount": 42.500, "method": "bank_transfer", "status": "pending", "at": _ago(days=2)},
    ],
    "55662256": [
        {"amount": 68.400, "method": "card", "status": "succeeded", "at": _ago(days=62)},
        {"amount": 73.900, "method": "card", "status": "failed", "at": _ago(days=9)},
        {"amount": 20.000, "method": "cash", "status": "succeeded", "at": _ago(days=4)},
    ],
}


# Recharges — Services' top-ups list, prepaid only.
RECHARGES: dict[str, list[dict]] = {
    "33449912": [
        {"amount": 20.000, "bonus": 2.000, "channel": "app", "status": "completed", "at": _ago(hours=21)},
        {"amount": 10.000, "bonus": 0.000, "channel": "ussd", "status": "completed", "at": _ago(days=8)},
        {"amount": 30.000, "bonus": 5.000, "channel": "agent", "status": "completed", "at": _ago(days=17)},
        {"amount": 5.000, "bonus": 0.000, "channel": "scratch_card", "status": "failed", "at": _ago(days=25)},
    ],
}


def _customers(session) -> dict[str, Customer]:
    """National id -> Customer, for the three pilot rows this script extends."""
    found: dict[str, Customer] = {}
    for national_id in set(TICKETS) | set(CONVERSATIONS):
        customer = session.scalar(select(Customer).where(Customer.national_id == national_id))
        if customer is not None:
            found[national_id] = customer
    return found


def _first_subscription(session, customer: Customer) -> Subscription | None:
    return session.scalar(
        select(Subscription).where(Subscription.customer_id == customer.id)
        .order_by(Subscription.activation_date.asc())
    )


def seed() -> None:  # noqa: C901 - a seed is a list of inserts; splitting it hides the shape
    counts = {k: 0 for k in
              ("tickets", "sessions", "turns", "callbacks", "notifications", "payments", "recharges")}

    with session_scope() as session:
        customers = _customers(session)
        if not customers:
            print("no pilot customers found - run `python -m seed.seed_pilot` first")
            return

        for national_id, customer in customers.items():
            subscription = _first_subscription(session, customer)

            # ---- tickets -------------------------------------------------------------------
            for spec in TICKETS.get(national_id, []):
                if session.scalar(select(Ticket).where(Ticket.glpi_ticket_id == spec["ref"])):
                    continue
                session.add(Ticket(
                    glpi_ticket_id=spec["ref"],
                    customer_id=customer.id,
                    subscription_id=subscription.id if subscription else None,
                    category=spec["category"],
                    subject=spec["subject"],
                    status=spec["status"],
                    priority=spec["priority"],
                    created_at=spec["opened"],
                    updated_at=spec["changed"],
                    last_synced_at=spec["changed"],
                ))
                counts["tickets"] += 1

            # ---- conversations + their turns ------------------------------------------------
            for spec in CONVERSATIONS.get(national_id, []):
                if session.scalar(
                    select(CallSession).where(CallSession.livekit_room == spec["room"])
                ):
                    continue
                started: datetime = spec["started"]
                call = CallSession(
                    customer_id=customer.id,
                    subscription_id=subscription.id if subscription else None,
                    msisdn=subscription.msisdn if subscription else None,
                    channel="voice",
                    livekit_room=spec["room"],
                    start_time=started,
                    end_time=started + timedelta(seconds=spec["duration"]),
                    duration_seconds=spec["duration"],
                    final_disposition=spec["disposition"],
                    recording_consent=False,
                    created_at=started,
                )
                session.add(call)
                # The turns need the session's id, and the unique constraint is
                # (session_id, turn_index, speaker) — so flush once and index from zero.
                session.flush()
                counts["sessions"] += 1

                # Turns are spread across the call's real duration rather than stamped
                # identically: the cadence strip positions each tick by when it happened, and a
                # conversation whose turns all share one timestamp collapses to a single mark.
                step = spec["duration"] / max(len(spec["turns"]), 1)
                for index, (speaker, agent, text_) in enumerate(spec["turns"]):
                    session.add(Turn(
                        session_id=call.id,
                        turn_index=index,
                        speaker=speaker,
                        active_agent=agent,
                        detected_language=spec["language"],
                        transcript_masked=text_,
                        created_at=started + timedelta(seconds=step * index),
                    ))
                    counts["turns"] += 1

            # ---- callbacks -------------------------------------------------------------------
            # Guarded on (customer, reason, status), NOT on scheduled_time: every timestamp here
            # is derived from `NOW`, so a time-based guard matches nothing on the second run and
            # the whole block inserts itself again. The triple is unique within each customer's
            # spec list, and if a REAL callback of the same kind already exists the seed correctly
            # stands aside rather than piling a synthetic twin on top of it.
            for spec in CALLBACKS.get(national_id, []):
                when: datetime = spec["when"]
                exists = session.scalar(
                    select(CallbackSchedule).where(
                        CallbackSchedule.customer_id == customer.id,
                        CallbackSchedule.reason == spec["reason"],
                        CallbackSchedule.status == spec["status"],
                    )
                )
                if exists:
                    continue
                session.add(CallbackSchedule(
                    customer_id=customer.id,
                    subscription_id=subscription.id if subscription else None,
                    scheduled_time=when,
                    status=spec["status"],
                    reason=spec["reason"],
                    preferred_window=spec["window"],
                    attempts=spec["attempts"],
                    outcome_note=spec.get("note"),
                    completed_at=when if spec["status"] == "completed" else None,
                    created_at=when - timedelta(days=1),
                    updated_at=when,
                ))
                counts["callbacks"] += 1

            # ---- notifications ---------------------------------------------------------------
            # Same reasoning as the callbacks above: (customer, channel, template, status) is the
            # stable identity, created_at is not.
            for spec in NOTIFICATIONS.get(national_id, []):
                at: datetime = spec["at"]
                exists = session.scalar(
                    select(Notification).where(
                        Notification.customer_id == customer.id,
                        Notification.channel == spec["channel"],
                        Notification.template_code == spec["template"],
                        Notification.status == spec["status"],
                    )
                )
                if exists:
                    continue
                sent = spec["status"] == "sent"
                session.add(Notification(
                    customer_id=customer.id,
                    channel=spec["channel"],
                    template_code=spec["template"],
                    status=spec["status"],
                    # The CHECK constraint allows a failure reason only on a failed row.
                    failure_reason=spec.get("failure") if spec["status"] == "failed" else None,
                    sent_at=at if sent else None,
                    created_at=at,
                ))
                counts["notifications"] += 1

            # ---- payments --------------------------------------------------------------------
            account = session.scalar(select(Account).where(Account.customer_id == customer.id))
            if account is not None:
                invoice = session.scalar(select(Invoice).where(Invoice.customer_id == customer.id))
                for index, spec in enumerate(PAYMENTS.get(national_id, [])):
                    key = f"{SEED_PREFIX}-pay-{national_id}-{index}"
                    if session.scalar(select(Payment).where(Payment.idempotency_key == key)):
                        continue
                    settled = spec["status"] == "succeeded"
                    session.add(Payment(
                        account_id=account.id,
                        invoice_id=invoice.id if invoice else None,
                        customer_id=customer.id,
                        amount=spec["amount"],
                        currency_code="TND",
                        method=spec["method"],
                        status=spec["status"],
                        idempotency_key=key,
                        gateway_reference=f"{SEED_PREFIX}{national_id[-4:]}{index:02d}",
                        paid_at=spec["at"] if settled else None,
                        created_at=spec["at"],
                    ))
                    counts["payments"] += 1

            # ---- recharges -------------------------------------------------------------------
            if subscription is not None:
                for index, spec in enumerate(RECHARGES.get(national_id, [])):
                    key = f"{SEED_PREFIX}-rec-{national_id}-{index}"
                    if session.scalar(select(Recharge).where(Recharge.idempotency_key == key)):
                        continue
                    session.add(Recharge(
                        subscription_id=subscription.id,
                        customer_id=customer.id,
                        amount=spec["amount"],
                        bonus_amount=spec["bonus"],
                        channel=spec["channel"],
                        status=spec["status"],
                        idempotency_key=key,
                        created_at=spec["at"],
                    ))
                    counts["recharges"] += 1

    summary = ", ".join(f"{value} {name}" for name, value in counts.items() if value)
    print(f"portal activity seeded: {summary or 'nothing new (already seeded)'}")


if __name__ == "__main__":
    seed()
