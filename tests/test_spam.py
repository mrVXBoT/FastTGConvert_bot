"""Tests for the live @SpamBot reply parser (app/services/spam.py)."""

import pytest

from app.services.spam import (
    _looks_like_greeting,
    _parse_spambot_reply,
    check_spam_via_spambot,
)


def _assert(text: str, expected: str) -> None:
    got = _parse_spambot_reply(text)
    assert got == expected, f"expected={expected} got={got} :: {text[:80]}"


def test_clean_replies_are_active() -> None:
    for text in (
        "Good news, no restrictions are currently applied to this account.",
        "No restrictions are currently applied to your account.",
        "I have good news for you: your account is not limited.",
        "Restrictions have been removed. Continue using Telegram as usual.",
        "خبر خوب، هیچ محدودیتی روی حساب شما اعمال نشده است.",
        "好消息，您的账号目前没有任何限制。",
    ):
        _assert(text, "active")


def test_limited_replies_are_spam_not_frozen() -> None:
    # The canonical SpamBot "limited" reply must be spam (appealable), NOT
    # frozen.  This was the bug that mislabelled accounts.
    for text in (
        "This account is limited. If you think this is a mistake, please "
        "contact us via the buttons below.",
        "The account has been limited for sending spam.",
        "This account has been limited by mistake, as it was reported by "
        "other users as spam.",
        "You can only send messages to mutual contacts.",
        "This account is limited for sending unsolicited messages to "
        "non-contacts.",
        "This account is limited for sending unsolicited messages to people "
        "who do not have your number.",
        "Your complaint has been successfully submitted.",
        "Appeal submitted. Our team of reviewers will look into your case.",
        "حساب شما به اشتباه محدود شده است.",
        "账户被限制，如果您认为这是一个错误，请通过下方按钮联系我们。",
    ):
        _assert(text, "spam")


def test_tos_replies_are_frozen() -> None:
    for text in (
        "This account has been blocked for violations of the Terms of "
        "Service.",
        "This account is frozen for violations of the Terms of Service.",
        "Your account has been restricted by the Terms of Service team.",
        "The account is frozen. To appeal, contact the team supervisor.",
        "This account is limited for violations of the Terms of Service.",
        "حساب شما برای نقض قوانین مسدود شده است.",
        "Плохие новости: аккаунт заблокирован за нарушения правил.",
    ):
        _assert(text, "frozen")


def test_banned_replies_are_banned() -> None:
    for text in (
        "This account has been permanently banned.",
        "This phone number has been permanently banned.",
    ):
        _assert(text, "banned")


def test_unrecognised_reply_is_inconclusive() -> None:
    _assert("A random unrecognized reply in Klingon.", "inconclusive")
    _assert("", "inconclusive")


def test_greeting_detection() -> None:
    assert _looks_like_greeting(
        "This is the official Spam Info Bot. I can help you find out if "
        "your account has been limited."
    ) is True
    assert _looks_like_greeting(
        "Good news, no restrictions are currently applied to this account."
    ) is False
    assert _looks_like_greeting("") is False
    assert _looks_like_greeting(None) is False


def test_clean_beats_frozen_word() -> None:
    # A clean reply must never be stolen by a "restriction" substring.
    _assert(
        "Good news, no restrictions are currently applied to this account.",
        "active",
    )


async def test_no_credentials_returns_inconclusive() -> None:
    from pathlib import Path

    status = await check_spam_via_spambot(Path("/nonexistent.session"), [])
    assert status == "inconclusive"


@pytest.mark.asyncio
async def test_deactivated_session_is_banned(tmp_path) -> None:
    """A session that connects but is not authorised is a deactivated/banned
    account, never a corrupt file."""
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    sess = tmp_path / "deact.session"
    sess.write_bytes(b"dummy")
    client = AsyncMock()
    client.connect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=False)
    client.disconnect = AsyncMock()
    with patch("telethon.TelegramClient", return_value=client):
        status = await check_spam_via_spambot(sess, [(12345, "hash")])
    assert status == "banned"


@pytest.mark.asyncio
async def test_auth_key_duplicated_is_banned(tmp_path) -> None:
    """A session whose auth key was force-terminated is a banned/deactivated
    account."""
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from telethon.errors import AuthKeyDuplicatedError

    sess = tmp_path / "dup.session"
    sess.write_bytes(b"dummy")
    client = AsyncMock()
    client.connect = AsyncMock(side_effect=AuthKeyDuplicatedError(request=None))
    client.disconnect = AsyncMock()
    with patch("telethon.TelegramClient", return_value=client):
        status = await check_spam_via_spambot(sess, [(12345, "hash")])
    assert status == "banned"


@pytest.mark.asyncio
async def test_auth_key_unregistered_is_banned(tmp_path) -> None:
    """A session whose auth key is no longer registered server-side is a
    deactivated account."""
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from telethon.errors import AuthKeyUnregisteredError

    sess = tmp_path / "unreg.session"
    sess.write_bytes(b"dummy")
    client = AsyncMock()
    client.connect = AsyncMock(side_effect=AuthKeyUnregisteredError(request=None))
    client.disconnect = AsyncMock()
    with patch("telethon.TelegramClient", return_value=client):
        status = await check_spam_via_spambot(sess, [(12345, "hash")])
    assert status == "banned"


@pytest.mark.asyncio
async def test_api_id_invalid_tries_next_credential(tmp_path) -> None:
    """An invalid api_id is credential-scoped: the next pair is tried and an
    OSError on it ends inconclusive (never a wrong bucket)."""
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from telethon.errors import ApiIdInvalidError

    sess = tmp_path / "api.session"
    sess.write_bytes(b"dummy")

    bad = AsyncMock()
    bad.connect = AsyncMock(side_effect=ApiIdInvalidError(request=None))
    bad.disconnect = AsyncMock()
    net = AsyncMock()
    net.connect = AsyncMock(side_effect=OSError("network"))
    net.disconnect = AsyncMock()
    with patch("telethon.TelegramClient", side_effect=[bad, net]):
        status = await check_spam_via_spambot(sess, [(1, "a"), (2, "b")])
    assert status == "inconclusive"


@pytest.mark.asyncio
async def test_2fa_session_is_inconclusive_not_active(tmp_path) -> None:
    """A session protected by 2FA cannot reach @SpamBot, so it must never be
    reported as clean (active) — that would overclaim a No Restriction status."""
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from telethon.errors import SessionPasswordNeededError

    sess = tmp_path / "2fa.session"
    sess.write_bytes(b"dummy")
    client = AsyncMock()
    client.connect = AsyncMock(side_effect=SessionPasswordNeededError(request=None))
    client.disconnect = AsyncMock()
    with patch("telethon.TelegramClient", return_value=client):
        status = await check_spam_via_spambot(sess, [(12345, "hash")])
    assert status == "inconclusive"
