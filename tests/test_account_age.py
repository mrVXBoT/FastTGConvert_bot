import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import account_age_noop
from app.keyboards import account_age_result_menu
from app.locales import ACCOUNT_AGE_MESSAGES, ENTER_ACCOUNT_AGE_PROMPT, LANGUAGES
from app.services.account_age import (
    estimate_account_creation,
    fetch_single_account_age,
    format_account_age_report,
    format_registration_report,
    format_registration_report_summary,
    process_account_age_check,
)


def _create_session(path: Path, user_id: int = 123456789) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE version (number integer primary key)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer, server_address text, port integer, auth_key blob)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (1, '127.0.0.1', 80, ?)",
            (b"\x01" * 256,),
        )
        conn.commit()
    return path


@pytest.fixture
def dummy_session(tmp_path: Path) -> Path:
    return _create_session(tmp_path / "test.session")


def test_estimate_account_creation():
    year, month, age_str = estimate_account_creation(150_000_000)
    assert year == 2016
    assert month == 1
    assert "2016" in age_str

    year_large, _month_large, age_large = estimate_account_creation(9_999_999_999)
    assert year_large == 2025
    assert "Estimated after November 2025 (Confidence: Low)" in age_large
    assert "exceeds verified public community dataset limit" in age_large


def test_estimate_account_creation_edge_cases(tmp_path: Path):
    from app.services.account_age import (
        DatasetCorruptError,
        DatasetNotFoundError,
    )

    # 1. Zero ID (min bound)
    _y0, _m0, str0 = estimate_account_creation(0)
    assert "Estimated August 2013" in str0

    # 2. Exact milestone ID match (8559682245 -> 2025-11-11)
    year_exact, month_exact, str_exact = estimate_account_creation(8559682245)
    assert year_exact == 2025
    assert month_exact == 11
    assert "11/11/2025" in str_exact

    # 3. Missing dataset file exception test
    non_existent = tmp_path / "non_existent.json"
    with pytest.raises(DatasetNotFoundError):
        estimate_account_creation(100, dataset_path=non_existent)

    # 4. Corrupt dataset file exception test
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("invalid json content", encoding="utf-8")
    with pytest.raises(DatasetCorruptError):
        estimate_account_creation(100, dataset_path=corrupt_file)

    # 5. Invalid calendar date test (e.g. Feb 30th)
    invalid_date_file = tmp_path / "invalid_date.json"
    invalid_date_file.write_text(
        '[{"id": 100, "date": "2024-02-30"}]', encoding="utf-8"
    )
    with pytest.raises(DatasetCorruptError):
        estimate_account_creation(100, dataset_path=invalid_date_file)

    # 6. Duplicate ID test
    dup_id_file = tmp_path / "dup_id.json"
    dup_id_file.write_text(
        '[{"id": 100, "date": "2020-01-01"}, {"id": 100, "date": "2020-02-01"}]',
        encoding="utf-8",
    )
    with pytest.raises(DatasetCorruptError):
        estimate_account_creation(100, dataset_path=dup_id_file)


@pytest.mark.asyncio
async def test_fetch_single_account_age(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyMe:
        id = 350_000_000
        phone = "989123456789"
        first_name = "Alice"
        username = "alicesmith"

    mock_client.get_me.return_value = DummyMe()

    class DummyMsg:
        import datetime

        date = datetime.datetime(2017, 4, 15, 10, 0, 0, tzinfo=datetime.UTC)

    mock_client.get_messages.return_value = [DummyMsg()]

    with patch("telethon.TelegramClient", return_value=mock_client):
        info = await fetch_single_account_age(dummy_session, [(123, "hash")])

    assert info is not None
    assert info.user_id == 350_000_000
    assert info.phone == "989123456789"
    assert info.username == "alicesmith"
    assert info.first_name == "Alice"
    assert "2017" in info.creation_estimate
    assert info.exact_creation_date == "2017-04-15"


@pytest.mark.asyncio
async def test_process_account_age_check(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyMe:
        id = 150_000_000
        phone = "989123456789"
        first_name = "Bob"
        username = "bobjones"

    mock_client.get_me.return_value = DummyMe()
    mock_client.get_messages.return_value = []

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_account_age_check(dummy_session, [(123, "hash")])

    assert res.total == 1
    assert res.checked == 1
    assert res.failed == 0
    assert len(res.accounts) == 1
    assert res.accounts[0].user_id == 150_000_000


@pytest.mark.asyncio
async def test_fetch_single_account_age_rpc_error_retries_next_credential(
    dummy_session: Path,
):
    """RPCError on the first credential must not abort the loop; the next
    credential pair should still be tried."""
    from telethon.errors import RPCError

    class DummyMe:
        id = 350_000_000
        phone = "989123456789"
        first_name = "Alice"
        username = "alicesmith"

    call_count = 0

    def client_factory(*args: object, **kwargs: object):
        nonlocal call_count
        call_count += 1
        client = AsyncMock()
        if call_count == 1:
            async def fail_connect():
                raise RPCError(request=None, message="boom")

            client.connect = fail_connect
        else:
            client.is_user_authorized.return_value = True
            client.get_me.return_value = DummyMe()
            client.get_messages.return_value = []
            client.session.dc_id = 2
        return client

    with patch("telethon.TelegramClient", side_effect=client_factory):
        info = await fetch_single_account_age(
            dummy_session, [(111, "hash1"), (222, "hash2")]
        )

    assert call_count == 2
    assert info is not None
    assert info.user_id == 350_000_000


@pytest.mark.asyncio
async def test_account_age_noop_callback():
    cb = AsyncMock(spec=CallbackQuery)
    cb.answer = AsyncMock()
    await account_age_noop(cb)
    cb.answer.assert_called_once()


def test_account_age_locales_and_keyboards():
    for lang in LANGUAGES:
        assert lang in ENTER_ACCOUNT_AGE_PROMPT
        assert lang in ACCOUNT_AGE_MESSAGES
        assert ACCOUNT_AGE_MESSAGES[lang]["fetching"]
        assert ACCOUNT_AGE_MESSAGES[lang]["report_title"]

    kb = account_age_result_menu(5, 4, 1, "en")
    assert len(kb.inline_keyboard) == 4


def test_format_account_age_report(dummy_session: Path):
    from app.services.account_age import AccountAgeInfo, AccountAgeResult

    info = AccountAgeInfo(
        session_name="test.session",
        user_id=8656186825,
        phone="244921908295",
        username="jamie2559",
        first_name="Jamie",
        last_name="Austin",
        is_premium=False,
        dc_id=4,
        creation_estimate="~ 28/4/2026\nEstimated 28 Apr 2026 (3 months ago)",
        exact_creation_date=None,
    )
    res = AccountAgeResult(total=1, checked=1, failed=0, accounts=(info,))
    msgs = ACCOUNT_AGE_MESSAGES["en"]

    formatted = format_account_age_report(res, msgs)
    assert "Jamie Austin" in formatted
    assert "8656186825" in formatted
    assert "@jamie2559" in formatted
    assert "❌ No" in formatted
    assert "🇳🇱 DC4" in formatted
    assert "Estimated Account Age" in formatted
    assert "Community Dataset" in formatted


def test_account_age_report_flag_premium_enrichment():
    from app.services.account_age import AccountAgeInfo, AccountAgeResult

    info = AccountAgeInfo(
        session_name="s1.session",
        user_id=8745840188,
        phone="07047848725",
        username="",
        first_name="User",
        last_name="",
        is_premium=False,
        dc_id=4,
        creation_estimate="~ 2026",
    )
    res = AccountAgeResult(total=1, checked=1, failed=0, accounts=(info,))
    msgs = ACCOUNT_AGE_MESSAGES["en"]

    text = format_account_age_report(res, msgs)
    assert "🇳🇱 DC4" in text

    from app.ui import EmojiRegistry

    previous_flags = dict(EmojiRegistry._flag_ids)
    EmojiRegistry.load_flag_pack()
    try:
        enriched = EmojiRegistry.enrich_flags(text)
        assert (
            '<tg-emoji emoji-id="5294241847445566691">🇳🇱</tg-emoji> DC4'
            in enriched
        )
        again = EmojiRegistry.enrich_flags(enriched)
        assert again == enriched
    finally:
        EmojiRegistry._flag_ids = previous_flags


def test_account_age_pagination_keyboard():
    from app.services.account_age import AccountAgeInfo, AccountAgeResult

    acc1 = AccountAgeInfo(
        "s1.session", 100, "111", "user1", "U1", "", False, 1, "~ 2020"
    )
    acc2 = AccountAgeInfo(
        "s2.session", 200, "222", "user2", "U2", "", True, 2, "~ 2021"
    )
    acc3 = AccountAgeInfo(
        "s3.session", 300, "333", "user3", "U3", "", False, 3, "~ 2022"
    )
    accs = (acc1, acc2, acc3)
    res = AccountAgeResult(total=3, checked=3, failed=0, accounts=accs)
    msgs = ACCOUNT_AGE_MESSAGES["en"]

    p0 = format_account_age_report(res, msgs, page=0)
    assert "Accounts (1/3)" in p0
    assert "U1" in p0

    p1 = format_account_age_report(res, msgs, page=1)
    assert "Accounts (2/3)" in p1
    assert "U2" in p1

    kb_small = account_age_result_menu(3, 3, 0, "en", page=1, total_pages=3)
    assert len(kb_small.inline_keyboard) == 5
    nav = kb_small.inline_keyboard[0]
    assert any("Prev" in b.text for b in nav)
    assert any("Next" in b.text for b in nav)

    kb_large = account_age_result_menu(10, 10, 0, "en", page=2, total_pages=10)
    assert len(kb_large.inline_keyboard) == 5
    nav_large = kb_large.inline_keyboard[0]
    assert nav_large[0].text == "⏮"
    assert nav_large[-1].text == "⏭"


def test_format_registration_report_summary():
    from app.services.account_age import AccountAgeInfo, AccountAgeResult

    acc1 = AccountAgeInfo(
        session_name="a.session",
        user_id=100,
        phone="111",
        username="user1",
        first_name="U1",
        last_name="",
        is_premium=False,
        dc_id=1,
        creation_estimate="~ 2020",
        exact_creation_date="2026-07-22",
    )
    acc2 = AccountAgeInfo(
        session_name="b.session",
        user_id=200,
        phone="222",
        username="user2",
        first_name="U2",
        last_name="",
        is_premium=False,
        dc_id=2,
        creation_estimate="~ 2021",
        exact_creation_date="2026-07-30",
    )
    acc3 = AccountAgeInfo(
        session_name="c.session",
        user_id=300,
        phone="333",
        username="user3",
        first_name="U3",
        last_name="",
        is_premium=False,
        dc_id=3,
        creation_estimate="~ 2022",
        exact_creation_date="2026-07-30",
    )
    res = AccountAgeResult(total=3, checked=3, failed=0, accounts=(acc1, acc2, acc3))

    text = format_registration_report_summary(res)
    assert "Registration Time Query Complete" in text
    assert "Total: 3" in text
    assert "Success: 3" in text
    assert "2026-07-22: 1" in text
    assert "2026-07-30: 2" in text
    assert "See detailed report in files below" in text


def test_format_registration_report_buckets_and_failures():
    from app.services.account_age import AccountAgeInfo, AccountAgeResult

    acc1 = AccountAgeInfo(
        session_name="a.session",
        user_id=100,
        phone="111",
        username="user1",
        first_name="U1",
        last_name="",
        is_premium=False,
        dc_id=1,
        creation_estimate="~ 2020",
        exact_creation_date="2019-05-12",
        registration_source="telegram_chat",
        registration_common_groups=3,
    )
    acc2 = AccountAgeInfo(
        session_name="b.session",
        user_id=200,
        phone="222",
        username="",
        first_name="U2",
        last_name="",
        is_premium=False,
        dc_id=2,
        creation_estimate="~ 2021",
        exact_creation_date="2019-05-12",
        registration_source="saved_messages",
        registration_common_groups=0,
    )
    acc3 = AccountAgeInfo(
        session_name="c.session",
        user_id=300,
        phone="333",
        username="user3",
        first_name="U3",
        last_name="",
        is_premium=True,
        dc_id=3,
        creation_estimate="~ 2018",
        exact_creation_date="2017-11-03",
        registration_source="estimation",
        registration_common_groups=1,
    )
    res = AccountAgeResult(
        total=5,
        checked=3,
        failed=2,
        accounts=(acc1, acc2, acc3),
        failure_entries=(
            ("d.session", "Account unauthorized or expired"),
            ("e.session", "Invalid or corrupted session file"),
        ),
    )

    text = format_registration_report(res)
    assert "Total Accounts: 5" in text
    assert "Success: 3" in text
    assert "Failed: 2" in text
    assert "📅 2019-05-12 | 2 accounts" in text
    assert "📅 2017-11-03 | 1 account" in text
    assert "File: a.session" in text
    assert "Common Groups: 3" in text
    assert "From @Telegram official chat" in text
    assert "Failed accounts:" in text
    assert "File: d.session" in text
    assert "Error: Account unauthorized or expired" in text

    empty = AccountAgeResult(
        total=2,
        checked=0,
        failed=2,
        accounts=(),
        failure_entries=(("f.session", "Account unauthorized or expired"),),
    )
    empty_text = format_registration_report(empty)
    assert "No accounts in the report." in empty_text
    assert "File: f.session" in empty_text


def test_build_outputs_zips(tmp_path: Path):
    import zipfile

    from app.services.account_age import (
        AccountAgeInfo,
        AccountAgeResult,
        _build_outputs,
    )

    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    out.mkdir()
    (work / "a.session").write_bytes(b"\x01" * 8)
    (work / "b.session").write_bytes(b"\x02" * 8)
    (work / "c.session").write_bytes(b"\x03" * 8)
    (work / "d.session").write_bytes(b"\x04" * 8)
    (work / "e.session").write_bytes(b"\x05" * 8)

    acc1 = AccountAgeInfo(
        "a.session", 100, "111", "u1", "U1", "", False, 1, "~ 2020",
        exact_creation_date="2026-07-22",
    )
    acc2 = AccountAgeInfo(
        "b.session", 200, "222", "u2", "U2", "", False, 2, "~ 2021",
        exact_creation_date="2026-07-30",
    )
    acc3 = AccountAgeInfo(
        "c.session", 300, "333", "u3", "U3", "", False, 3, "~ 2022",
        exact_creation_date="2026-07-30",
    )
    res = AccountAgeResult(
        total=5,
        checked=3,
        failed=2,
        accounts=(acc1, acc2, acc3),
        failure_entries=(
            ("d.session", "Account unauthorized or expired"),
            ("e.session", "Invalid or corrupted session file"),
        ),
    )
    session_files = [
        work / "a.session",
        work / "b.session",
        work / "c.session",
        work / "d.session",
        work / "e.session",
    ]

    report_path, classified_zip, failed_zip = _build_outputs(
        work, res, session_files, out
    )

    assert report_path is not None and report_path.exists()
    assert "Total Accounts: 5" in report_path.read_text(encoding="utf-8")

    assert classified_zip is not None and classified_zip.exists()
    with zipfile.ZipFile(classified_zip) as archive:
        names = sorted(archive.namelist())
        assert names == [
            "2026-07-22/a.session",
            "2026-07-30/b.session",
            "2026-07-30/c.session",
        ]

    assert failed_zip is not None and failed_zip.exists()
    with zipfile.ZipFile(failed_zip) as archive:
        names = set(archive.namelist())
        assert "d.session" in names
        assert "e.session" in names
        assert "failed_reasons.txt" in names
        reasons = archive.read("failed_reasons.txt").decode("utf-8")
        assert "d.session | Account unauthorized or expired" in reasons
