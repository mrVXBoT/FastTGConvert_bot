import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.sessions import SQLiteSession  # type: ignore[import-untyped]

from app.locales import (
    LANGUAGES,
    TDATA_TO_SESSION_MESSAGES,
    TDATA_TO_SESSION_PROMPTS,
)
from app.services.files import UnsafeArchiveError
from app.services.session_to_tdata import convert_session_to_tdata
from app.services.tdata_to_session import (
    convert_tdata_dir_to_sessions,
    extract_zip_tdata_safe,
    find_tdata_dirs,
    process_tdata_to_session_conversion,
)


@pytest.fixture
def dummy_session(tmp_path: Path) -> Path:
    sess = tmp_path / "test.session"
    with sqlite3.connect(sess) as conn:
        conn.execute("CREATE TABLE version (version integer primary key)")
        conn.execute("INSERT INTO version VALUES (7)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address"
            " text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
            (b"\x07" * 256,),
        )
        conn.execute(
            "CREATE TABLE entities (id integer primary key, hash integer,"
            " username text, phone text, name text, date integer)"
        )
        conn.execute(
            "INSERT INTO entities VALUES (55667788, 1, 'testuser',"
            " '1234567', 'Test', 1600000000)"
        )
        conn.execute(
            "CREATE TABLE sent_files (md5_digest blob, file_size integer, type"
            " integer, id integer, hash integer, primary key(md5_digest,"
            " file_size, type))"
        )
        conn.execute(
            "CREATE TABLE update_state (id integer primary key, pts integer,"
            " qts integer, date integer, seq integer)"
        )
    return sess


@pytest.mark.asyncio
async def test_telethon_sqlite_session_full_schema(dummy_session: Path, tmp_path: Path):
    from datetime import UTC, datetime

    from telethon.tl.types import InputDocument  # type: ignore[import-untyped]
    from telethon.tl.types.updates import State  # type: ignore[import-untyped]

    tdata_dir = tmp_path / "tdata"
    converted_td = await convert_session_to_tdata(dummy_session, tdata_dir)
    assert converted_td is True

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    sess_files = await convert_tdata_dir_to_sessions(tdata_dir, out_dir)
    assert len(sess_files) == 1
    sess_file = sess_files[0]
    assert sess_file.exists()

    # Telethon SQLiteSession full schema API verification
    session = SQLiteSession(str(sess_file))
    assert session.dc_id == 2
    assert session.server_address == "149.154.167.50"
    assert session.port == 443
    assert session.auth_key is not None
    assert len(session.auth_key.key) == 256
    assert session.get_update_state(2) is None  # Ensures update_state exists
    expected_state = State(
        pts=10,
        qts=20,
        date=datetime.now(UTC),
        seq=30,
        unread_count=0,
    )
    session.set_update_state(2, expected_state)
    stored_state = session.get_update_state(2)
    assert stored_state is not None
    assert (stored_state.pts, stored_state.qts, stored_state.seq) == (10, 20, 30)
    assert (
        session.get_file(b"md5digest", 100, InputDocument) is None
    )  # Ensures sent_files exists
    ent_rows = session.get_entity_rows_by_id(55667788)
    assert ent_rows is not None
    session.close()


@pytest.mark.asyncio
async def test_single_tdata_folder_with_multiple_accounts(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    mock_acc1 = MagicMock()
    mock_acc1.authKey.key = b"\x05" * 256
    mock_acc1.authKey.dcId = 2
    mock_acc1.UserId = 111111

    mock_acc2 = MagicMock()
    mock_acc2.authKey.key = b"\x06" * 256
    mock_acc2.authKey.dcId = 4
    mock_acc2.UserId = 222222

    mock_tdesktop = MagicMock()
    mock_tdesktop.isLoaded.return_value = True
    mock_tdesktop.accountsCount = 2
    mock_tdesktop.accounts = [mock_acc1, mock_acc2]

    with patch("opentele.td.TDesktop", return_value=mock_tdesktop):
        sess_files = await convert_tdata_dir_to_sessions(tmp_path, out_dir)
        assert len(sess_files) == 2
        names = [f.name for f in sess_files]
        assert "session_111111.session" in names
        assert "session_222222.session" in names


@pytest.mark.asyncio
async def test_tdata_without_user_id_skips_account(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    mock_account = MagicMock()
    mock_account.authKey.key = b"\x05" * 256
    mock_account.authKey.dcId = 2
    mock_account.UserId = None  # No valid user ID

    mock_tdesktop = MagicMock()
    mock_tdesktop.isLoaded.return_value = True
    mock_tdesktop.accountsCount = 1
    mock_tdesktop.accounts = [mock_account]

    with patch("opentele.td.TDesktop", return_value=mock_tdesktop):
        sess_files = await convert_tdata_dir_to_sessions(tmp_path, out_dir)
        assert len(sess_files) == 0


@pytest.mark.asyncio
async def test_process_tdata_to_session_zip_single(dummy_session: Path, tmp_path: Path):
    tdata_dir = tmp_path / "tdata"
    await convert_session_to_tdata(dummy_session, tdata_dir)

    zip_in = tmp_path / "tdata_input.zip"
    with zipfile.ZipFile(zip_in, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in tdata_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"tdata/{f.relative_to(tdata_dir)}")

    out_dir = tmp_path / "outbox"
    res = await process_tdata_to_session_conversion(zip_in, out_dir)

    assert res.total == 1
    assert res.converted == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.name == "session_55667788.session"
    assert res.is_zip is False


@pytest.mark.asyncio
async def test_multi_account_tdata_count_accuracy(dummy_session: Path, tmp_path: Path):
    td1 = tmp_path / "acc1" / "tdata"
    td2 = tmp_path / "acc2" / "tdata"
    await convert_session_to_tdata(dummy_session, td1)

    sess2 = tmp_path / "test2.session"
    with sqlite3.connect(sess2) as conn:
        conn.execute("CREATE TABLE version (version integer primary key)")
        conn.execute("INSERT INTO version VALUES (7)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address"
            " text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (4, '149.154.167.51', 443, ?, 0)",
            (b"\x08" * 256,),
        )
        conn.execute(
            "CREATE TABLE entities (id integer primary key, hash integer,"
            " username text, phone text, name text, date integer)"
        )
        conn.execute(
            "INSERT INTO entities VALUES (99887766, 1, 'user2',"
            " '7654321', 'Test2', 1600000000)"
        )

    await convert_session_to_tdata(sess2, td2)

    zip_in = tmp_path / "multi_tdata.zip"
    with zipfile.ZipFile(zip_in, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in td1.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"account1/tdata/{f.relative_to(td1)}")
        for f in td2.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"account2/tdata/{f.relative_to(td2)}")

    out_dir = tmp_path / "outbox_multi"
    res = await process_tdata_to_session_conversion(zip_in, out_dir)

    assert res.total == 2
    assert res.converted == 2
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.suffix == ".zip"
    assert res.is_zip is True


def test_find_tdata_dirs(tmp_path: Path):
    d1 = tmp_path / "dir1" / "tdata"
    d1.mkdir(parents=True)
    (d1 / "key_datas").write_bytes(b"data")

    d2 = tmp_path / "dir2" / "nested" / "tdata"
    d2.mkdir(parents=True)
    (d2 / "key_datas").write_bytes(b"data")

    found = find_tdata_dirs(tmp_path)
    assert len(found) == 2
    assert d1 in found
    assert d2 in found


def test_extract_zip_tdata_safe_zip_slip(tmp_path: Path):
    zip_path = tmp_path / "slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "evil")

    target = tmp_path / "extracted"
    with pytest.raises(UnsafeArchiveError, match="zip_unsafe_path"):
        extract_zip_tdata_safe(zip_path, target)


def test_extract_zip_tdata_safe_too_many_members(tmp_path: Path):
    zip_path = tmp_path / "too_many.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i in range(15):
            zf.writestr(f"file_{i}.txt", "content")

    target = tmp_path / "extracted"
    with (
        patch("app.services.tdata_to_session.MAX_ZIP_MEMBERS", 10),
        pytest.raises(UnsafeArchiveError, match="zip_too_many_members"),
    ):
        extract_zip_tdata_safe(zip_path, target)


def test_extract_zip_tdata_safe_uncompressed_limit(tmp_path: Path):
    zip_path = tmp_path / "uncompressed_large.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("big.txt", b"0" * 1000)

    target = tmp_path / "extracted"
    with (
        patch("app.services.tdata_to_session.MAX_ZIP_UNCOMPRESSED_BYTES", 500),
        pytest.raises(UnsafeArchiveError, match="zip_uncompressed_limit"),
    ):
        extract_zip_tdata_safe(zip_path, target)


def test_extract_zip_tdata_safe_suspicious_ratio(tmp_path: Path):
    zip_path = tmp_path / "suspicious_ratio.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy.txt", "dummy")

    zi = zipfile.ZipInfo("ratio.txt")
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.file_size = 100000
    zi.compress_size = 100

    target = tmp_path / "extracted"
    with (
        patch.object(zipfile.ZipFile, "infolist", return_value=[zi]),
        patch.object(zipfile.ZipFile, "extract"),
        patch("app.services.tdata_to_session.MAX_COMPRESSION_RATIO", 50),
        pytest.raises(UnsafeArchiveError, match="zip_suspicious_ratio"),
    ):
        extract_zip_tdata_safe(zip_path, target)


def test_tdata_to_session_locales_completeness():
    for lang in LANGUAGES:
        assert lang in TDATA_TO_SESSION_PROMPTS
        assert lang in TDATA_TO_SESSION_MESSAGES
        msgs = TDATA_TO_SESSION_MESSAGES[lang]
        assert "converting" in msgs
        assert "done" in msgs
        assert "no_valid_tdata" in msgs


@pytest.mark.asyncio
async def test_tdata_to_session_handler_flow(dummy_session: Path, tmp_path: Path):
    from app.handlers.files import process_tdata_to_session_file

    tdata_dir = tmp_path / "tdata"
    await convert_session_to_tdata(dummy_session, tdata_dir)

    zip_in = tmp_path / "input.zip"
    with zipfile.ZipFile(zip_in, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in tdata_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"tdata/{f.relative_to(tdata_dir)}")

    message = AsyncMock()
    message.from_user.id = 12345
    message.document.file_name = "input.zip"
    message.document.file_size = zip_in.stat().st_size

    bot = AsyncMock()
    bot.download = AsyncMock(
        side_effect=lambda file, destination, **kwargs: destination.write_bytes(
            zip_in.read_bytes()
        )
    )

    state = AsyncMock()
    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.max_upload_bytes = 100 * 1024 * 1024

    status_msg = AsyncMock()
    message.answer.return_value = status_msg

    session_factory = MagicMock()
    db_session = MagicMock()
    session_factory.return_value.__enter__.return_value = db_session

    await process_tdata_to_session_file(message, bot, state, settings, session_factory)

    assert status_msg.edit_text.called
    assert message.answer_document.called
    state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_tdata_to_session_handler_cleanup_on_send_error(
    dummy_session: Path, tmp_path: Path
):
    from app.handlers.files import process_tdata_to_session_file

    tdata_dir = tmp_path / "tdata"
    await convert_session_to_tdata(dummy_session, tdata_dir)

    zip_in = tmp_path / "input.zip"
    with zipfile.ZipFile(zip_in, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in tdata_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f"tdata/{f.relative_to(tdata_dir)}")

    message = AsyncMock()
    message.from_user.id = 12345
    message.document.file_name = "input.zip"
    message.document.file_size = zip_in.stat().st_size
    message.answer_document.side_effect = RuntimeError("Telegram API send failed")

    bot = AsyncMock()
    bot.download = AsyncMock(
        side_effect=lambda file, destination, **kwargs: destination.write_bytes(
            zip_in.read_bytes()
        )
    )

    state = AsyncMock()
    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.max_upload_bytes = 100 * 1024 * 1024

    status_msg = AsyncMock()
    message.answer.return_value = status_msg

    session_factory = MagicMock()
    db_session = MagicMock()
    session_factory.return_value.__enter__.return_value = db_session

    await process_tdata_to_session_file(message, bot, state, settings, session_factory)

    # State cleared and status updated on exception
    state.clear.assert_called_once()
    outbox_files = list((tmp_path / "outbox").glob("*"))
    assert len(outbox_files) == 0
