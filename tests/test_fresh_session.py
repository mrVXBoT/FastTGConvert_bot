"""tests/test_fresh_session.py — Tests for the Fresh Session migration service."""

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def _make_valid_session(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sessions (auth_key BLOB)")
        conn.execute("INSERT INTO sessions VALUES (?)", (b"1" * 256,))


class _FakeMe:
    phone = "+12345678901"
    first_name = "Test"


class _FakeSent:
    phone_code_hash = "hash123"


class _FakeOtpQueue:
    async def get(self):
        return "12345"


@pytest.mark.asyncio
async def test_freshen_single_session_invalid_2fa_password(tmp_path: Path):
    from telethon.errors import (
        PasswordHashInvalidError,
        SessionPasswordNeededError,
    )

    from app.services.fresh_session import freshen_single_session

    sess = tmp_path / "old.session"
    _make_valid_session(sess)

    me = _FakeMe()
    sent = _FakeSent()

    old_client = AsyncMock()
    old_client.connect = AsyncMock()
    old_client.is_user_authorized = AsyncMock(return_value=True)
    old_client.get_me = AsyncMock(return_value=me)
    old_client.on = lambda *a, **k: lambda fn: fn
    old_client.remove_event_handler = AsyncMock()
    old_client.disconnect = AsyncMock()

    new_client = AsyncMock()
    new_client.connect = AsyncMock()
    new_client.send_code_request = AsyncMock(return_value=sent)
    new_client.sign_in = AsyncMock(
        side_effect=[
            SessionPasswordNeededError(request=None),
            PasswordHashInvalidError(request=None),
        ]
    )
    new_client.disconnect = AsyncMock()

    with (
        patch("telethon.TelegramClient", side_effect=[old_client, new_client]),
        patch(
            "app.services.fresh_session.asyncio.Queue", return_value=_FakeOtpQueue()
        ),
    ):
        detail = await freshen_single_session(
            sess, [(123, "hash")], tmp_path, password_2fa="wrong-password"
        )

    assert detail.status == "2fa_required"
    assert "Invalid 2FA password" in detail.message


@pytest.mark.asyncio
async def test_freshen_single_session_otp_success(tmp_path: Path):
    from app.services.fresh_session import freshen_single_session

    sess = tmp_path / "old.session"
    _make_valid_session(sess)

    me = _FakeMe()
    sent = _FakeSent()

    old_client = AsyncMock()
    old_client.connect = AsyncMock()
    old_client.is_user_authorized = AsyncMock(return_value=True)
    old_client.get_me = AsyncMock(return_value=me)
    old_client.on = lambda *a, **k: lambda fn: fn
    old_client.remove_event_handler = AsyncMock()
    old_client.disconnect = AsyncMock()

    new_client = AsyncMock()
    new_client.connect = AsyncMock()
    new_client.send_code_request = AsyncMock(return_value=sent)
    new_client.sign_in = AsyncMock(return_value=None)
    new_client.get_me = AsyncMock(return_value=me)
    new_client.disconnect = AsyncMock()

    with (
        patch("telethon.TelegramClient", side_effect=[old_client, new_client]),
        patch(
            "app.services.fresh_session.asyncio.Queue", return_value=_FakeOtpQueue()
        ),
    ):
        detail = await freshen_single_session(
            sess, [(123, "hash")], tmp_path, password_2fa=None
        )

    assert detail.status == "ok"
    assert "New session created" in detail.message
