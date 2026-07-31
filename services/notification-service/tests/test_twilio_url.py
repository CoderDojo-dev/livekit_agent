"""The Twilio REST URL must be a URL, not a string that merely contains one."""
from urllib.parse import urlparse

from notification_service.channels import _account_url, _messages_url


def test_messages_url_is_parseable() -> None:
    sid = "AC0123456789abcdef"
    parsed = urlparse(_messages_url(sid))

    assert parsed.scheme == "https"
    assert parsed.netloc == "api.twilio.com"
    assert "AC0123456789abcdef" in parsed.path


def test_account_url_is_parseable() -> None:
    sid = "AC0123456789abcdef"
    parsed = urlparse(_account_url(sid))

    assert parsed.scheme == "https"
    assert parsed.netloc == "api.twilio.com"
    assert parsed.path.endswith(f"/Accounts/{sid}.json")


def test_whatsapp_prefix_is_not_doubled() -> None:
    from notification_service.channels import TwilioChannel

    channel = TwilioChannel("whatsapp", "whatsapp:+21611111111")
    assert channel._address(channel._from, "whatsapp:") == "whatsapp:+21611111111"
