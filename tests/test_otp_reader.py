import tempfile
from pathlib import Path

import pytest

from app.services.otp_reader import logout_account_session, read_account_otps


@pytest.mark.asyncio
async def test_read_account_otps_empty_credentials() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        session_file = Path(tmp) / "test.session"
        session_file.write_bytes(b"dummy")
        info, result, status = await read_account_otps(session_file, [])
        assert info == {}
        assert result == []
        assert status == "inconclusive"


@pytest.mark.asyncio
async def test_read_account_otps_nonexistent_path() -> None:
    path = Path("/nonexistent/test.session")
    info, result, status = await read_account_otps(path, [(123, "hash")])
    assert info == {}
    assert result == []
    assert status == "inconclusive"


@pytest.mark.asyncio
async def test_read_account_otps_banned_returns_banned() -> None:
    from unittest.mock import AsyncMock, patch

    from telethon import TelegramClient

    with tempfile.TemporaryDirectory() as tmp:
        session_file = Path(tmp) / "banned.session"
        session_file.write_bytes(b"dummy")

        client = AsyncMock()
        client.connect = AsyncMock()
        client.is_user_authorized = AsyncMock(return_value=False)
        client.disconnect = AsyncMock()
        with patch.object(
            TelegramClient, "__init__", lambda *a, **k: None
        ), patch.object(
            TelegramClient, "connect", client.connect
        ), patch.object(
            TelegramClient, "is_user_authorized", client.is_user_authorized
        ), patch.object(
            TelegramClient, "disconnect", client.disconnect
        ):
            info, result, status = await read_account_otps(
                session_file, [(123, "hash")]
            )
        assert status == "banned"
        assert info == {}
        assert result == []


@pytest.mark.asyncio
async def test_logout_account_session_empty_credentials() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        session_file = Path(tmp) / "test.session"
        session_file.write_bytes(b"dummy")
        result = await logout_account_session(session_file, [])
        assert result is False


def test_format_time_ago_seconds() -> None:
    from datetime import datetime, timedelta, timezone

    UTC = timezone.utc  # noqa: UP017

    from app.services.otp_reader import format_time_ago

    now = datetime.now(UTC)
    assert format_time_ago(now - timedelta(seconds=6)) == "6s ago"
    assert format_time_ago(now - timedelta(seconds=45)) == "45s ago"
    assert format_time_ago(now - timedelta(minutes=5)) == "5m ago"
