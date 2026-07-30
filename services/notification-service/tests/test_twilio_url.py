"""The Twilio URL must use single-brace f-string interpolation, not double braces."""
import pathlib


def test_twilio_url_uses_single_braces() -> None:
    here = pathlib.Path(__file__).resolve().parent
    src = (here.parent / "src" / "notification_service" / "channels.py").read_text(encoding="utf-8")
    assert "{{https://api.twilio.com" not in src
    assert "{self._sid}" in src
    assert "{{self._sid}}" not in src


def test_whatsapp_prefix_is_not_doubled() -> None:
    from notification_service.channels import TwilioChannel

    channel = TwilioChannel("whatsapp", "whatsapp:+21611111111")
    assert channel._address(channel._from, "whatsapp:") == "whatsapp:+21611111111"
