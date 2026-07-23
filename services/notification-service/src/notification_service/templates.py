"""Localized message templates (fr/ar/en). Written confirmations are in the caller's language."""
from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "advisor_callback": {
        "fr": ("Escalade : {full_name} ({msisdn}) demande un rappel. "
               "Motif : {reason}. Domaine : {skill_tag}. Tunisie Telecom."),
        "ar": ("تصعيد: {full_name} ({msisdn}) يطلب معاودة الاتصال. "
               "السبب: {reason}. المجال: {skill_tag}. اتصالات تونس."),
        "en": ("Escalation: {full_name} ({msisdn}) requested a callback. "
               "Reason: {reason}. Area: {skill_tag}. Tunisie Telecom."),
    },
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
    "ticket_resolved": {
        "fr": "Votre ticket {ticket_id} a été résolu. Merci de votre confiance. Tunisie Telecom.",
        "ar": "تم حل تذكرتك {ticket_id}. شكرا لثقتك. اتصالات تونس.",
        "en": "Your ticket {ticket_id} has been resolved. Thank you for your trust. Tunisie Telecom.",
    },
    "ticket_updated": {
        "fr": "Votre ticket {ticket_id} a été mis à jour. Consultez votre espace client. Tunisie Telecom.",
        "ar": "تم تحديث تذكرتك {ticket_id}. تحقق من مساحة العميل الخاصة بك. اتصالات تونس.",
        "en": "Your ticket {ticket_id} has been updated. Check your customer portal. Tunisie Telecom.",
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