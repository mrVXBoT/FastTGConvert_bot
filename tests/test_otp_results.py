from app.otp_results import OTPAccountResult, OTPCode, render_otp_account


def test_render_otp_account_with_new_codes() -> None:
    result = OTPAccountResult(
        current=1,
        total=1,
        user="Test User",
        phone="+10000000000",
        username="@test_user",
        codes=(OTPCode(code="12345", age="6s ago"),),
        since_last_check=True,
    )

    text = render_otp_account(result)
    assert "Account 1/1" in text
    assert "New OTP Codes (since last check)" in text
    assert "🔑 <code>12345</code>" in text
    assert "⏱ 6s ago" in text
    assert "📨 Telegram" in text


def test_render_otp_account_escapes_dynamic_values() -> None:
    result = OTPAccountResult(
        current=1,
        total=1,
        user="<b>name</b>",
        phone="<phone>",
        username="<username>",
        codes=(OTPCode(code="<code>", age="<age>", source="<source>"),),
    )

    text = render_otp_account(result)
    assert "&lt;b&gt;name&lt;/b&gt;" in text
    assert "&lt;code&gt;" in text
    assert "<phone>" not in text
