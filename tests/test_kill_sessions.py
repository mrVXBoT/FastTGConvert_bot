from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.kill_sessions import (
    kill_single_session_others,
    process_kill_sessions,
)


@pytest.mark.asyncio
async def test_kill_single_session_invalid_sqlite(tmp_path: Path):
    bad_sess = tmp_path / "corrupt.session"
    bad_sess.write_text("not sqlite")

    st, msg = await kill_single_session_others(bad_sess, [(123, "hash")])
    assert st == "invalid_sqlite"
    assert "Invalid SQLite" in msg


@pytest.mark.asyncio
async def test_kill_single_session_fresh_forbidden(tmp_path: Path):
    from telethon.errors import (  # type: ignore[import-untyped]
        FreshResetAuthorisationForbiddenError,
    )

    fake_sess = tmp_path / "valid.session"

    # Create dummy sqlite database structure with auth_key
    import sqlite3

    with sqlite3.connect(fake_sess) as conn:
        conn.execute("CREATE TABLE sessions (auth_key BLOB)")
        conn.execute("INSERT INTO sessions VALUES (?)", (b"1" * 256,))

    mock_client = AsyncMock()
    mock_client.connect = AsyncMock()
    mock_client.is_user_authorized = AsyncMock(return_value=True)
    mock_client.side_effect = FreshResetAuthorisationForbiddenError(request=None)
    mock_client.disconnect = AsyncMock()

    with patch("telethon.TelegramClient", return_value=mock_client):
        st, msg = await kill_single_session_others(fake_sess, [(123, "hash")])
        assert st == "fresh_forbidden"
        assert "24h" in msg


@pytest.mark.asyncio
async def test_kill_single_session_success(tmp_path: Path):
    fake_sess = tmp_path / "valid.session"

    import sqlite3

    with sqlite3.connect(fake_sess) as conn:
        conn.execute("CREATE TABLE sessions (auth_key BLOB)")
        conn.execute("INSERT INTO sessions VALUES (?)", (b"1" * 256,))

    mock_client = AsyncMock(return_value=True)
    mock_client.connect = AsyncMock()
    mock_client.is_user_authorized = AsyncMock(return_value=True)
    mock_client.disconnect = AsyncMock()

    with patch("telethon.TelegramClient", return_value=mock_client):
        st, msg = await kill_single_session_others(fake_sess, [(123, "hash")])
        assert st == "ok"
        assert "Successfully" in msg


@pytest.mark.asyncio
async def test_process_kill_sessions_zip(tmp_path: Path):
    import zipfile

    sess1 = tmp_path / "s1.session"
    sess2 = tmp_path / "s2.session"
    import sqlite3

    for s in (sess1, sess2):
        with sqlite3.connect(s) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute("INSERT INTO sessions VALUES (?)", (b"1" * 256,))

    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(sess1, arcname="s1.session")
        zf.write(sess2, arcname="s2.session")

    mock_client = AsyncMock(return_value=True)
    mock_client.connect = AsyncMock()
    mock_client.is_user_authorized = AsyncMock(return_value=True)
    mock_client.disconnect = AsyncMock()

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_kill_sessions(zip_path, [(123, "hash")])
        assert res.total == 2
        assert res.killed == 2
        assert res.failed == 0
        assert len(res.details) == 2
