import asyncio
import csv
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.locales import CHECK_CONTACTS_MESSAGES, CHECK_CONTACTS_PROMPTS
from app.services.contacts_checker import (
    ContactsCheckCancelled,
    ContactsCheckResult,
    ContactsProgress,
    check_session_contacts_live,
    check_session_contacts_offline,
    extract_accounts_safe,
    extract_zip_sessions_safe,
    process_contacts_check,
)
from app.services.files import UnsafeArchiveError


def _valid_session(path: Path, with_contacts: bool = True) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sessions (auth_key BLOB)")
        conn.execute(
            "INSERT INTO sessions VALUES (?)", (b"valid_key_1234567890_123456",)
        )
        if with_contacts:
            conn.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, phone TEXT)")
            conn.execute("INSERT INTO contacts VALUES (1, '+123456789')")


def _ok_client(contacts_count: int = 3) -> AsyncMock:
    """Mocked Telethon client returning a healthy account (read-only check)."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    clean_msg = type(
        "Msg",
        (),
        {
            "out": False,
            "id": 99,
            "message": "Good news, no restrictions are placed on your account.",
        },
    )()
    client.get_messages = AsyncMock(return_value=[clean_msg])
    client.send_message = AsyncMock(return_value=type("SentMsg", (), {"id": 1})())
    contacts_res = type("ContactsRes", (), {"contacts": list(range(contacts_count))})()
    me_res = type(
        "MeRes",
        (),
        {
            "users": [
                type(
                    "User",
                    (),
                    {
                        "phone": "+123456",
                        "username": "alice",
                        "first_name": "Alice",
                        "last_name": "A",
                        "premium": True,
                        "dc_id": 2,
                    },
                )()
            ]
        },
    )()
    # Call order: GetContacts -> GetUsers(profile)
    client.side_effect = [contacts_res, me_res]
    return client


@pytest.mark.asyncio
async def test_process_contacts_check_single_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "test.session"
        _valid_session(sess_file)

        res = await process_contacts_check(sess_file, tmp_path / "outbox")
        assert res.checked == 1
        assert res.ok == 0
        assert res.inconclusive == 1
        assert len(res.zip_paths) == 1
        zip_path, status, count = res.zip_paths[0]
        assert status == "inconclusive"
        assert count == 1
        assert zip_path.name.startswith("Check_contacts_Error_1_")
        assert zip_path.exists()
        assert res.report_path is not None
        assert res.report_path.name.startswith("contacts_report_")

        with zipfile.ZipFile(zip_path) as zf:
            assert "test.session" in zf.namelist()

        with res.report_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[0] == [
            "#",
            "File",
            "Status",
            "Contacts",
            "Phone",
            "Username",
            "First Name",
            "Last Name",
            "Premium",
            "DC",
            "Note",
        ]
        assert rows[1][1] == "test.session"
        assert rows[1][2] == "Error"
        assert rows[1][3] == ""


@pytest.mark.asyncio
async def test_process_contacts_check_single_upload_uses_original_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Disk path carries the `-<uuid>` temp name; outputs must use the
        # user's original upload name instead.
        sess_file = tmp_path / "787c6fda56944d6a9385340e6a98b82f.session"
        _valid_session(sess_file)

        res = await process_contacts_check(
            sess_file, tmp_path / "outbox", original_name="+12167587713.session"
        )

        assert res.checked == 1
        assert len(res.zip_paths) == 1
        zip_path = res.zip_paths[0][0]
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == ["+12167587713.session"]
        with res.report_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[1][1] == "+12167587713.session"


@pytest.mark.asyncio
async def test_process_contacts_check_invalid_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "invalid.session"
        sess_file.write_bytes(b"not a sqlite db")

        res = await process_contacts_check(sess_file, tmp_path / "outbox")
        assert res.checked == 1
        assert res.ok == 0
        assert res.invalid == 1
        assert len(res.zip_paths) == 1
        assert res.zip_paths[0][0].name.startswith("Check_contacts_Invalid_1_")
        assert res.report_path is not None


def test_check_session_contacts_offline_standard_session_without_contacts_table() -> (
    None
):
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "std_telethon.session"
        _valid_session(sess_file, with_contacts=False)

        is_ok, count = check_session_contacts_offline(sess_file)
        assert is_ok is True
        assert count == 0


def test_check_session_contacts_offline_missing_auth_key_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "no_auth.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute("INSERT INTO sessions VALUES (?)", (b"",))

        is_ok, count = check_session_contacts_offline(sess_file)
        assert is_ok is False
        assert count == 0


@pytest.mark.asyncio
async def test_live_check_unauthorized_no_2fa_is_banned() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "unauth.session"
        _valid_session(sess_file)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client.disconnect = AsyncMock()
        mock_client.side_effect = None
        pwd_res = type("PwdRes", (), {"current_algo": None})()
        mock_client.return_value = pwd_res

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(sess_file, [(12345, "hash")])
            assert status == "banned"

            res = await process_contacts_check(
                sess_file, Path(tmp) / "outbox", credentials=[(12345, "hash")]
            )
            assert res.checked == 1
            assert res.banned == 1
            assert res.ok == 0


@pytest.mark.asyncio
async def test_live_check_unauthorized_with_2fa_is_two_fa() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "twofa.session"
        _valid_session(sess_file)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client.disconnect = AsyncMock()
        mock_client.side_effect = None
        pwd_res = type("PwdRes", (), {"current_algo": object()})()
        mock_client.return_value = pwd_res

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(sess_file, [(12345, "hash")])
            assert status == "2fa"

            res = await process_contacts_check(
                sess_file, Path(tmp) / "outbox", credentials=[(12345, "hash")]
            )
            assert res.two_fa == 1


@pytest.mark.asyncio
async def test_live_check_auth_key_duplicated_is_banned() -> None:
    from telethon.errors import AuthKeyDuplicatedError

    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "dup.session"
        _valid_session(sess_file)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(
            side_effect=AuthKeyDuplicatedError(request=None)
        )

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(sess_file, [(12345, "h")])
            assert status == "banned"


@pytest.mark.asyncio
async def test_live_check_phone_banned_is_banned() -> None:
    from telethon.errors import PhoneNumberBannedError

    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "phone_banned.session"
        _valid_session(sess_file)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(
            side_effect=PhoneNumberBannedError(request=None)
        )

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(sess_file, [(12345, "h")])
            assert status == "banned"


@pytest.mark.asyncio
async def test_live_check_auth_key_invalid_is_invalid() -> None:
    from telethon.errors import AuthKeyInvalidError

    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "stale.session"
        _valid_session(sess_file)

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=AuthKeyInvalidError(request=None))

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(sess_file, [(12345, "h")])
            assert status == "invalid"


@pytest.mark.asyncio
async def test_live_check_transient_error_tries_next_credential_and_succeeds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "test.session"
        sess_file.write_bytes(b"dummy")

        mock_client_fail = AsyncMock()
        mock_client_fail.connect = AsyncMock(side_effect=OSError("Network down"))
        mock_client_fail.disconnect = AsyncMock()

        mock_client_ok = _ok_client(contacts_count=3)

        with patch(
            "telethon.TelegramClient", side_effect=[mock_client_fail, mock_client_ok]
        ):
            status, info = await check_session_contacts_live(
                sess_file, [(111, "h1"), (222, "h2")]
            )
            assert status == "ok"
            assert info is not None
            assert info.contacts_count == 3
            assert info.username == "alice"
            assert info.premium is True
            assert info.dc_id == 2


@pytest.mark.asyncio
async def test_live_check_all_credentials_transient_is_inconclusive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "flaky.session"
        sess_file.write_bytes(b"dummy")

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=OSError("Network down"))
        mock_client.disconnect = AsyncMock()

        with patch("telethon.TelegramClient", return_value=mock_client):
            status, _ = await check_session_contacts_live(
                sess_file, [(111, "h1"), (222, "h2")]
            )
            assert status == "inconclusive"

            # Structurally invalid file + transient network → invalid.
            res = await process_contacts_check(
                sess_file, Path(tmp) / "outbox", credentials=[(111, "h1")]
            )
            assert res.invalid == 1
            assert res.inconclusive == 0


@pytest.mark.asyncio
async def test_live_check_read_rejected_is_restricted() -> None:
    """A limitation error while reading contacts reports Restricted."""

    class _RestrictedClient:
        def __init__(self) -> None:
            self.connect = AsyncMock()
            self.is_user_authorized = AsyncMock(return_value=True)
            self.disconnect = AsyncMock()

        async def __call__(self, _req):
            from telethon.errors import PeerFloodError

            raise PeerFloodError(request=None)

    with (
        patch("telethon.TelegramClient", return_value=_RestrictedClient()),
        tempfile.TemporaryDirectory() as tmp,
    ):
        sess_file = Path(tmp) / "restricted.session"
        sess_file.write_bytes(b"dummy")
        status, _ = await check_session_contacts_live(sess_file, [(12345, "h")])
        assert status == "limited"

        res = await process_contacts_check(
            sess_file, Path(tmp) / "outbox", credentials=[(12345, "h")]
        )
        assert res.limited == 1
        assert res.ok == 0


@pytest.mark.asyncio
async def test_live_check_ok_requires_no_write_probe() -> None:
    """Read access alone makes an account Healthy (no write probe involved)."""
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "healthy.session"
        sess_file.write_bytes(b"dummy")

        client = AsyncMock()
        client.connect = AsyncMock()
        client.is_user_authorized = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        contacts_res = type("ContactsRes", (), {"contacts": [1, 2]})()
        me_res = type(
            "MeRes",
            (),
            {
                "users": [
                    type(
                        "User",
                        (),
                        {
                            "phone": "+123456",
                            "username": "user1",
                            "first_name": "U",
                            "last_name": "",
                            "premium": False,
                            "dc_id": 2,
                        },
                    )()
                ]
            },
        )()
        clean_msg = type(
            "Msg",
            (),
            {
                "out": False,
                "id": 100,
                "message": "Good news, no restrictions are placed on your account.",
            },
        )()
        client.get_messages = AsyncMock(return_value=[clean_msg])
        client.send_message = AsyncMock(return_value=type("SentMsg", (), {"id": 2})())
        client.side_effect = [contacts_res, me_res]

        with patch("telethon.TelegramClient", return_value=client):
            status, info = await check_session_contacts_live(sess_file, [(12345, "h")])
            assert status == "ok"
            assert info is not None
            assert info.contacts_count == 2


@pytest.mark.asyncio
async def test_spambot_probe_returns_limited_when_spambot_reports_restriction() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "spambot_limited.session"
        sess_file.write_bytes(b"dummy")

        client = AsyncMock()
        client.connect = AsyncMock()
        client.is_user_authorized = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()

        contacts_res = type("ContactsRes", (), {"contacts": [1, 2]})()
        me_res = type(
            "MeRes",
            (),
            {
                "users": [
                    type(
                        "User",
                        (),
                        {
                            "phone": "+123456",
                            "username": "user",
                            "first_name": "U",
                            "last_name": "",
                            "premium": False,
                            "dc_id": 2,
                        },
                    )()
                ]
            },
        )()
        client.side_effect = [contacts_res, me_res]

        spambot_msg = type(
            "Msg",
            (),
            {
                "out": False,
                "id": 100,
                "message": "Dear user, your account is limited for sending unsolicited messages.",
            },
        )()
        client.get_messages = AsyncMock(return_value=[spambot_msg])
        client.send_message = AsyncMock(return_value=type("SentMsg", (), {"id": 2})())

        with patch("telethon.TelegramClient", return_value=client):
            status, info = await check_session_contacts_live(sess_file, [(12345, "h")])
            assert status == "limited"
            assert info is None


def test_contacts_localization_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        assert lang in CHECK_CONTACTS_PROMPTS
        assert lang in CHECK_CONTACTS_MESSAGES
        msgs = CHECK_CONTACTS_MESSAGES[lang]
        assert "checking" in msgs
        assert "cancelled" in msgs


@pytest.mark.asyncio
async def test_process_contacts_check_zip_with_siblings_keeps_them_together() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "accounts.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("123.session", b"dummy session data")
            z.writestr("123.json", b'{"account": 123}')
            z.writestr("456.session", b"dummy session data 2")

        res = await process_contacts_check(zip_file, tmp_path / "outbox")
        assert res.checked == 2
        zip_path, _status, _count = res.zip_paths[0]
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "123.session" in names
            assert "123.json" in names


@pytest.mark.asyncio
async def test_extract_zip_sessions_safe_preserves_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "plain.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("a/123.session", b"x")
            z.writestr("note.txt", b"y")
        target = tmp_path / "out"
        target.mkdir()
        files = extract_zip_sessions_safe(zip_file, target)
        assert len(files) == 1
        assert files[0].name == "123.session"


@pytest.mark.asyncio
async def test_extract_zip_sessions_safe_dedupes_duplicates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "dup.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("a/123.session", b"x")
            z.writestr("b/123.session", b"y")
            z.writestr("c/123.session", b"z")
        target = tmp_path / "out"
        target.mkdir()
        files = extract_zip_sessions_safe(zip_file, target)
        assert {f.name for f in files} == {
            "123.session",
            "123_1.session",
            "123_2.session",
        }


@pytest.mark.asyncio
async def test_extract_accounts_safe_preserves_names_and_dedupes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "accounts.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("a/123.session", b"s-a")
            z.writestr("a/123.json", b"j-a")
            z.writestr("b/123.session", b"s-b")
        target = tmp_path / "out"
        target.mkdir()
        extracted = extract_accounts_safe(zip_file, target)
        names = {p.name for ex in extracted for p, _ in ex.files}
        assert "123.session" in names
        assert "123.json" in names
        assert "123_1.session" in names
        sessions = [ex.session_path.name for ex in extracted]
        assert sessions == ["123.session", "123_1.session"]


@pytest.mark.asyncio
async def test_process_contacts_check_zip_no_sessions_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "no_sessions.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("notes.txt", b"no sessions here")

        with pytest.raises(UnsafeArchiveError) as exc_info:
            await process_contacts_check(zip_file, tmp_path / "outbox")
        assert exc_info.value.code == "zip_no_sessions"


@pytest.mark.asyncio
async def test_process_contacts_check_zip_slip_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("../session.session", b"dummy")

        with pytest.raises(UnsafeArchiveError) as exc_info:
            await process_contacts_check(zip_file, tmp_path / "outbox")
        assert exc_info.value.code in ("zip_unsafe_path", "zip_slip")


@pytest.mark.asyncio
async def test_process_contacts_check_too_many_members_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "too_many.zip"
        with patch("app.services.contacts_checker.MAX_ZIP_MEMBERS", 2):
            with zipfile.ZipFile(zip_file, "w") as z:
                z.writestr("1.session", b"a")
                z.writestr("2.session", b"b")
                z.writestr("3.session", b"c")

            with pytest.raises(UnsafeArchiveError) as exc_info:
                await process_contacts_check(zip_file, tmp_path / "outbox")
            assert exc_info.value.code in ("zip_too_many_members", "too_many_members")


@pytest.mark.asyncio
async def test_process_contacts_check_zip_bomb_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "zip_bomb.zip"
        with patch("app.services.contacts_checker.MAX_ZIP_UNCOMPRESSED_BYTES", 10):
            with zipfile.ZipFile(zip_file, "w") as z:
                z.writestr("large.session", b"0" * 100)

            with pytest.raises(UnsafeArchiveError) as exc_info:
                await process_contacts_check(zip_file, tmp_path / "outbox")
            assert exc_info.value.code in ("zip_uncompressed_limit", "zip_bomb")


@pytest.mark.asyncio
async def test_process_contacts_check_temp_dir_cleaned_on_exception() -> None:
    from unittest.mock import MagicMock

    mock_tmp_instance = MagicMock()
    mock_tmp_instance.name = tempfile.mkdtemp()
    mock_tmp_instance.cleanup = MagicMock()

    with tempfile.TemporaryDirectory() as real_tmp:
        tmp_path = Path(real_tmp)
        zip_file = tmp_path / "invalid.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("../bad.session", b"dummy")

        with (
            patch("tempfile.TemporaryDirectory", return_value=mock_tmp_instance),
            pytest.raises(UnsafeArchiveError),
        ):
            await process_contacts_check(zip_file, tmp_path / "outbox")

        assert mock_tmp_instance.cleanup.called is True


@pytest.mark.asyncio
async def test_process_contacts_check_progress_and_cancel() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_files = []
        for idx in range(4):
            sess_file = tmp_path / f"s{idx}.session"
            _valid_session(sess_file)
            sess_files.append(sess_file)

        zip_file = tmp_path / "many.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            for idx, sess in enumerate(sess_files):
                z.writestr(f"s{idx}.session", sess.read_bytes())

        cancel_event = asyncio.Event()
        progress = ContactsProgress()

        with patch(
            "app.services.contacts_checker.check_session_contacts_offline",
            side_effect=[(True, 1), (True, 2), (True, 3), (True, 4)],
        ):
            res = await process_contacts_check(
                zip_file,
                tmp_path / "outbox",
                progress=progress,
                cancel_event=cancel_event,
            )
        assert res.checked == 4
        assert progress.total == 4
        assert progress.done == 4

        # Cancelling mid-run raises ContactsCheckCancelled.
        cancel_event = asyncio.Event()

        def _set_after_one(path: object) -> tuple[bool, int]:
            cancel_event.set()
            return True, 1

        progress = ContactsProgress()
        with (
            patch(
                "app.services.contacts_checker.check_session_contacts_offline",
                side_effect=_set_after_one,
            ),
            pytest.raises(ContactsCheckCancelled),
        ):
            await process_contacts_check(
                zip_file,
                tmp_path / "outbox2",
                progress=progress,
                cancel_event=cancel_event,
                concurrency=1,
            )
        assert progress.done == 1


@pytest.mark.asyncio
async def test_process_contacts_check_invariant_holds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "test.session"
        _valid_session(sess_file)

        res = await process_contacts_check(sess_file, tmp_path / "outbox")
        assert (
            res.ok
            + res.limited
            + res.two_fa
            + res.banned
            + res.invalid
            + res.inconclusive
            == res.checked
        )
        ContactsCheckResult(
            checked=1,
            ok=1,
            limited=0,
            two_fa=0,
            banned=0,
            invalid=0,
            inconclusive=0,
        )


def test_extract_accounts_safe_groups_siblings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "accounts.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("folder/1.session", b"x")
            z.writestr("folder/1.json", b"{}")
            z.writestr("folder/2.session", b"y")
        target = tmp_path / "out"
        target.mkdir()
        accounts = extract_accounts_safe(zip_file, target)
        assert len(accounts) == 2
        names = {orig for acc in accounts for _p, orig in acc.files}
        assert "folder/1.session" in names
        assert "folder/1.json" in names
