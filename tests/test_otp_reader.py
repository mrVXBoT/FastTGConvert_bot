import tempfile
from pathlib import Path

import pytest

from app.services.otp_reader import logout_account_session, read_account_otps


@pytest.mark.asyncio
async def test_read_account_otps_empty_credentials() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        session_file = Path(tmp) / "test.session"
        session_file.write_bytes(b"dummy")
        info, result = await read_account_otps(session_file, [])
        assert info == {}
        assert result == []


@pytest.mark.asyncio
async def test_read_account_otps_nonexistent_path() -> None:
    path = Path("/nonexistent/test.session")
    info, result = await read_account_otps(path, [(123, "hash")])
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
    from datetime import UTC, datetime, timedelta

    from app.services.otp_reader import format_time_ago

    now = datetime.now(UTC)
    assert format_time_ago(now - timedelta(seconds=6)) == "6s ago"
    assert format_time_ago(now - timedelta(seconds=45)) == "45s ago"
    assert format_time_ago(now - timedelta(minutes=5)) == "5m ago"
