"""Localized message templates (fr/ar/en). Written confirmations are in the caller's language."""
from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "ticket_created": {
        "fr": "Votre demande a bien été enregistrée. Référence du ticket : {ticket_id}. Tunisie Telecom.",
        "ar": "تم تسجيل طلبك. رقم التذكرة: {ticket_id}. اتصالات تونس.",
        "en": "Your request has been logged. Ticket reference: {ticket_id}. Tunisie Telecom.",
    },
    "callback_scheduled": {
        "fr": "Nous vous rappellerons {when}. Merci de votre patience. Tunisie Telecom.",
        "ar": "سنعاود الاتصال بك {when}. شكرًا لصبرك. اتصالات تونس.",
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