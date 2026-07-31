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


def test_no_stray_characters_before_the_scheme() -> None:
    """The URL must start with the scheme itself: a transport that doubled the braces of an
    f-string would prefix the URL with a literal '{' and urlparse would see an empty scheme."""
    for url in (_messages_url("AC0123456789abcdef"), _account_url("AC0123456789abcdef")):
        assert url.startswith("https://api.twilio.com")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "api.twilio.com"


def test_whatsapp_prefix_is_not_doubled() -> None:
    from notification_service.channels import TwilioChannel

    channel = TwilioChannel("whatsapp", "whatsapp:+21611111111")
    assert channel._address(channel._from, "whatsapp:") == "whatsapp:+21611111111"
