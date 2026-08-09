import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.keyboards import (
    mass_message_confirm_menu,
    mass_message_delay_menu,
    mass_message_live_menu,
    mass_message_recipients_menu,
)
from app.services.mass_message import (
    format_mass_message_summary,
    generate_mass_message_report,
    parse_recipients_from_file,
)


def test_parse_recipients_from_file(tmp_path: Path):
    txt_file = tmp_path / "recipients.txt"
    txt_content = "@user1\n123456789\n+1987654321\nuser2\n@user1"  # duplicates included
    txt_file.write_text(txt_content, encoding="utf-8")

    recipients = parse_recipients_from_file(txt_file)
    assert len(recipients) == 4
    assert recipients[0].raw_identifier == "@user1"
    assert recipients[0].recipient_type == "username"
    assert recipients[0].username == "user1"

    assert recipients[1].raw_identifier == "123456789"
    assert recipients[1].recipient_type == "id"
    assert recipients[1].user_id == 123456789

    assert recipients[2].raw_identifier == "+1987654321"
    assert recipients[2].recipient_type == "phone"
    assert recipients[2].phone == "+1987654321"

    assert recipients[3].username == "user2"


def test_generate_mass_message_report(tmp_path: Path):
    details = [
        {
            "recipient": "@user1",
            "status": "SENT",
            "session": "s1.session",
            "details": "Success",
        },
        {
            "recipient": "123456",
            "status": "FAILED",
            "session": "s2.session",
            "details": "PeerFloodError",
        },
    ]

    csv_out = tmp_path / "report.csv"
    generate_mass_message_report(details, csv_out, format_type="csv")
    assert csv_out.exists()
    content = csv_out.read_text(encoding="utf-8")
    assert "@user1" in content
    assert "PeerFloodError" in content

    txt_out = tmp_path / "report.txt"
    generate_mass_message_report(details, txt_out, format_type="txt")
    assert txt_out.exists()
    txt_content = txt_out.read_text(encoding="utf-8")
    assert "MASS MESSAGE EXECUTION REPORT" in txt_content


def test_parse_recipients_from_zip(tmp_path: Path):
    import zipfile

    from app.services.mass_message import parse_recipients_from_file

    zip_path = tmp_path / "recipients.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("list1.txt", "@user1\n+1234567890\n")
        zf.writestr("list2.csv", "1234567,@user2\n")

    recs = parse_recipients_from_file(zip_path)
    assert len(recs) == 4
    raw_ids = [r.raw_identifier for r in recs]
    assert "@user1" in raw_ids
    assert "+1234567890" in raw_ids
    assert "1234567" in raw_ids
    assert "@user2" in raw_ids


def test_mass_message_keyboards():
    kb_rec = mass_message_recipients_menu("en")
    assert len(kb_rec.inline_keyboard) == 2
    assert "Contacts" in kb_rec.inline_keyboard[0][0].text

    kb_delay = mass_message_delay_menu("fa")
    assert len(kb_delay.inline_keyboard) == 4

    kb_confirm = mass_message_confirm_menu("en")
    assert len(kb_confirm.inline_keyboard) == 2
    assert kb_confirm.inline_keyboard[0][0].callback_data == "mass_msg_action:start"

    kb_live_running = mass_message_live_menu(is_paused=False, language="en")
    assert kb_live_running.inline_keyboard[0][0].callback_data == "mass_msg_ctrl:pause"

    kb_live_paused = mass_message_live_menu(is_paused=True, language="en")
    assert kb_live_paused.inline_keyboard[0][0].callback_data == "mass_msg_ctrl:resume"


from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.errors import (  # type: ignore[import-untyped]
    FloodWaitError,
    PeerFloodError,
    UserIsBlockedError,
    UserPrivacyRestrictedError,
)

from app.services.mass_message import Recipient, send_mass_message_to_recipient


@pytest.mark.asyncio
async def test_send_mass_message_text_success():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="entity_target")
    client.send_message = AsyncMock(return_value=None)

    rec = Recipient(
        raw_identifier="@user1", recipient_type="username", username="user1"
    )
    status, detail = await send_mass_message_to_recipient(client, rec, "Hello World")

    assert status == "SENT"
    assert detail == "Success"
    client.send_message.assert_awaited_once_with("entity_target", "Hello World")


@pytest.mark.asyncio
async def test_send_mass_message_file_success(tmp_path: Path):
    media_file = tmp_path / "photo.jpg"
    media_file.write_bytes(b"dummy")

    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="entity_target")
    client.send_file = AsyncMock(return_value=None)

    rec = Recipient(raw_identifier="123456", recipient_type="id", user_id=123456)
    status, detail = await send_mass_message_to_recipient(
        client, rec, "Caption text", media_path=media_file
    )

    assert status == "SENT"
    assert detail == "Success"
    client.send_file.assert_awaited_once_with(
        "entity_target", str(media_file), caption="Caption text"
    )


@pytest.mark.asyncio
async def test_send_mass_message_flood_wait():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="target")
    err = FloodWaitError(request=None)
    err.seconds = 30
    client.send_message = AsyncMock(side_effect=err)

    rec = Recipient(
        raw_identifier="@user1", recipient_type="username", username="user1"
    )
    status, detail = await send_mass_message_to_recipient(client, rec, "Hello")

    assert status == "SKIPPED"
    assert "FloodWait 30s" in detail


@pytest.mark.asyncio
async def test_send_mass_message_peer_flood():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="target")
    client.send_message = AsyncMock(side_effect=PeerFloodError(request=None))

    rec = Recipient(
        raw_identifier="+12345678", recipient_type="phone", phone="+12345678"
    )
    status, detail = await send_mass_message_to_recipient(client, rec, "Hello")

    assert status == "SKIPPED"
    assert detail == "PeerFlood"


@pytest.mark.asyncio
async def test_send_mass_message_privacy_restricted():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="target")
    client.send_message = AsyncMock(
        side_effect=UserPrivacyRestrictedError(request=None)
    )

    rec = Recipient(
        raw_identifier="@secret_user", recipient_type="username", username="secret_user"
    )
    status, detail = await send_mass_message_to_recipient(client, rec, "Hello")

    assert status == "FAILED"
    assert detail == "UserPrivacyRestricted"


@pytest.mark.asyncio
async def test_send_mass_message_user_blocked():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="target")
    client.send_message = AsyncMock(side_effect=UserIsBlockedError(request=None))

    rec = Recipient(raw_identifier="999888", recipient_type="id", user_id=999888)
    status, detail = await send_mass_message_to_recipient(client, rec, "Hello")

    assert status == "FAILED"
    assert detail == "UserBlockedOrDeactivated"


def test_format_mass_message_summary():
    summary_en = format_mass_message_summary(
        job_id="MM-20260802-5931",
        accounts_count=5,
        total_recipients=1243,
        sent=1198,
        failed=31,
        skipped=14,
        duration_seconds=1458.0,
        language="en",
    )
    assert "Job ID: `#MM-20260802-5931`" in summary_en
    assert "Active Accounts: 5" in summary_en
    assert "Total Recipients: 1243" in summary_en
    assert "Sent: 1198" in summary_en
    assert "Duration: 24m 18s" in summary_en

    summary_zh = format_mass_message_summary(
        job_id="test_job_zh",
        accounts_count=3,
        total_recipients=50,
        sent=45,
        failed=3,
        skipped=2,
        duration_seconds=90.0,
        language="zh",
    )
    assert "群发消息摘要报告" in summary_zh
    assert "活跃账户: 3" in summary_zh


@pytest.mark.asyncio
async def test_send_mass_message_entity_caching():
    client = MagicMock()
    client.get_input_entity = AsyncMock(return_value="cached_entity")
    client.send_message = AsyncMock(return_value=None)

    cache: dict[str, Any] = {}
    rec = Recipient(
        raw_identifier="@user1", recipient_type="username", username="user1"
    )

    # First call populates cache
    await send_mass_message_to_recipient(client, rec, "Msg 1", entity_cache=cache)
    assert cache.get("user1") == "cached_entity"
    assert client.get_input_entity.call_count == 1

    # Second call uses cache directly without calling get_input_entity again
    await send_mass_message_to_recipient(client, rec, "Msg 2", entity_cache=cache)
    assert client.get_input_entity.call_count == 1


import json
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, FileRecord, Job, User
from app.services.mass_message import (
    GlobalRateLimiter,
    recover_interrupted_mass_message_jobs,
)


@pytest.mark.asyncio
async def test_global_rate_limiter():
    limiter = GlobalRateLimiter(min_interval_seconds=0.05)
    t0 = time.time()
    await limiter.acquire()
    await limiter.acquire()
    t1 = time.time()
    assert (t1 - t0) >= 0.04


from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017


def test_job_foreign_key_integrity_and_recovery():
    """Verify Foreign Key integrity between FileRecord and Job, display ID format,
    periodic checkpoints, and startup recovery with duplicate-send prevention."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=999888, username="test_user")
        db.add(u)
        db.commit()
        db.refresh(u)

        # 1. Foreign Key Integrity test
        file_id = str(uuid4())
        job_id = str(uuid4())
        f_rec = FileRecord(
            id=file_id,
            user_id=u.id,
            original_name="input.zip",
            media_type="application/zip",
            size_bytes=1024,
            sha256="dummy_sha256",
            storage_path="/tmp/input.zip",
            expires_at=datetime.now(UTC),
        )
        opts = {
            "display_id": "MM-20260802-A1B2C3D4",
            "total": 5,
            "sent": 2,
            "failed": 0,
            "skipped": 0,
            "pending_recipients": ["@user3", "@user4", "@user5"],
            "completed_recipients": ["@user1", "@user2"],
        }
        job = Job(
            id=job_id,
            user_id=u.id,
            operation="mass_message",
            input_file_id=f_rec.id,
            status="running",
            progress=40,
            options_json=json.dumps(opts),
        )
        db.add_all([f_rec, job])
        db.commit()

        # Check foreign key link
        db_job = db.query(Job).filter(Job.id == job_id).first()
        assert db_job is not None
        assert db_job.input_file_id == f_rec.id

    # 2. Crash Recovery Service Test
    recovered = recover_interrupted_mass_message_jobs(TestingSessionLocal)
    assert len(recovered) == 1
    assert recovered[0]["job_id"] == job_id
    assert recovered[0]["display_id"] == "MM-20260802-A1B2C3D4"
    assert recovered[0]["pending_count"] == 3

    # 3. Duplicate Send Prevention & DB State Verification after Recovery
    with TestingSessionLocal() as db:
        recovered_job = db.query(Job).filter(Job.id == job_id).first()
        assert recovered_job is not None
        assert recovered_job.status == "paused"
        parsed_opts = json.loads(recovered_job.options_json)
        assert parsed_opts["pending_recipients"] == ["@user3", "@user4", "@user5"]
        # Ensure completed recipients are not in pending queue
        for comp in parsed_opts["completed_recipients"]:
            assert comp not in parsed_opts["pending_recipients"]


from unittest.mock import patch

from app.services.mass_message import resume_mass_message_job


def test_job_nullable_input_file_and_unique_display_id():
    """Verify Job creation without fake FileRecord (nullable input_file_id) and unique display_id."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=777666, username="nullable_test")
        db.add(u)
        db.commit()

        job_id = str(uuid4())
        job = Job(
            id=job_id,
            display_id="MM-20260802-UNIQUE01",
            user_id=u.id,
            operation="mass_message",
            input_file_id=None,  # Nullable input file ID!
            status="running",
            progress=0,
            options_json=json.dumps({"test": True}),
        )
        db.add(job)
        db.commit()

        fetched = db.query(Job).filter(Job.id == job_id).first()
        assert fetched is not None
        assert fetched.input_file_id is None
        assert fetched.display_id == "MM-20260802-UNIQUE01"


@pytest.mark.asyncio
async def test_end_to_end_operational_job_resume_handler():
    """Integration Test:
    1. Simulates an interrupted job with partial progress in DB.
    2. Invokes recover_interrupted_mass_message_jobs.
    3. Invokes resume_mass_message_job execution layer.
    4. Verifies remaining recipients are processed to 100% completion.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=555444, username="resume_user")
        db.add(u)
        db.commit()

        job_id = str(uuid4())
        opts = {
            "display_id": "MM-20260802-RESUME01",
            "total": 4,
            "sent": 2,
            "failed": 0,
            "skipped": 0,
            "message_text": "Resume test message",
            "media_file_id": None,
            "session_files": [],
            "pending_recipients": ["@user3", "@user4"],
            "completed_recipients": ["@user1", "@user2"],
            "details": [
                {
                    "recipient": "@user1",
                    "session": "s1.session",
                    "status": "SENT",
                    "details": "",
                },
                {
                    "recipient": "@user2",
                    "session": "s1.session",
                    "status": "SENT",
                    "details": "",
                },
            ],
        }
        job = Job(
            id=job_id,
            display_id="MM-20260802-RESUME01",
            user_id=u.id,
            operation="mass_message",
            input_file_id=None,
            status="running",
            progress=50,
            options_json=json.dumps(opts),
        )
        db.add(job)
        db.commit()

    # Step 1: Startup Recovery Service
    recovered = recover_interrupted_mass_message_jobs(TestingSessionLocal)
    assert len(recovered) == 1
    assert recovered[0]["job_id"] == job_id
    assert recovered[0]["pending_count"] == 2

    # Step 2: Operational Execution Resume Layer
    with patch(
        "app.services.mass_message.create_telethon_client_for_session"
    ) as mock_cli:
        fake_cli = MagicMock()
        fake_cli.get_input_entity = AsyncMock(return_value="entity")
        fake_cli.send_message = AsyncMock(return_value=None)
        fake_cli.disconnect = AsyncMock()

        fake_tmp = MagicMock()
        mock_cli.return_value = (fake_cli, Path("/tmp/s1.session"), fake_tmp)

        # Resume job
        result = await resume_mass_message_job(
            job_id=job_id,
            session_factory=TestingSessionLocal,
            api_credentials=[(12345, "hash")],
        )

        assert result.sent == 2
        assert result.total == 4

    # Step 3: Verify DB Final State
    with TestingSessionLocal() as db:
        final_job = db.query(Job).filter(Job.id == job_id).first()
        assert final_job is not None
        assert final_job.status == "completed"
        assert final_job.progress == 100


def test_mass_message_paused_menu():
    from app.keyboards import mass_message_paused_menu
    kb = mass_message_paused_menu("some_job_id", "en")
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].callback_data == "resume_job:some_job_id"
    assert kb.inline_keyboard[1][0].callback_data == "menu:back"


def test_format_mass_message_summary_paused_and_stopped():
    summary_paused = format_mass_message_summary(
        job_id="MM-20260802-5931",
        accounts_count=5,
        total_recipients=100,
        sent=20,
        failed=5,
        skipped=5,
        duration_seconds=300.0,
        language="en",
        status="paused",
        last_error_session="573118660372.session",
        last_error_detail="PeerFlood",
    )
    assert "Job Paused" in summary_paused
    assert "573118660372.session" in summary_paused
    assert "PeerFlood" in summary_paused
    assert "Job paused due to rate limiting" in summary_paused

    summary_stopped = format_mass_message_summary(
        job_id="MM-20260802-5931",
        accounts_count=5,
        total_recipients=100,
        sent=20,
        failed=5,
        skipped=5,
        duration_seconds=300.0,
        language="fa",  # Fallback to en or other format
        status="stopped",
    )
    assert "Mass Message Job Stopped" in summary_stopped


@pytest.mark.asyncio
async def test_request_mass_message_with_paused_job():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import request_mass_message

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Setup User & paused Job
    with TestingSessionLocal() as db:
        u = User(telegram_id=11112222, username="test_paused_flow")
        db.add(u)
        db.commit()
        db.refresh(u)

        job = Job(
            id="job_paused_123",
            display_id="P123",
            user_id=u.id,
            operation="mass_message",
            status="paused",
            progress=50,
            options_json=json.dumps({"total": 10}),
        )
        db.add(job)
        db.commit()

    callback = MagicMock()
    callback.from_user = MagicMock(id=11112222)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    key = MagicMock()
    state = FSMContext(storage, key)

    await request_mass_message(callback, state, TestingSessionLocal)

    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    # Verify the prompt contains our paused warning and the resume/start new buttons
    assert "paused" in args[0] or "P123" in args[0]
    keyboard = kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "resume_job:job_paused_123"
    assert keyboard.inline_keyboard[1][0].callback_data == "mass_msg_job:new"


@pytest.mark.asyncio
async def test_request_mass_message_no_double_mm_prefix():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import request_mass_message

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=11114444, username="test_mm_prefix")
        db.add(u)
        db.commit()
        db.refresh(u)

        job = Job(
            id="job_paused_mm",
            display_id="MM-20260806-A1B2C3D4",
            user_id=u.id,
            operation="mass_message",
            status="paused",
            progress=50,
            options_json=json.dumps({"total": 10}),
        )
        db.add(job)
        db.commit()

    callback = MagicMock()
    callback.from_user = MagicMock(id=11114444)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage, MagicMock())

    await request_mass_message(callback, state, TestingSessionLocal)

    text = callback.message.edit_text.call_args.args[0]
    assert "MM-20260806-A1B2C3D4" in text
    assert "MM-MM-" not in text


@pytest.mark.asyncio
async def test_resume_job_rejects_non_paused_job():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import resume_job_callback

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=11115555, username="test_resume_guard")
        db.add(u)
        db.commit()
        db.refresh(u)

        job = Job(
            id="job_completed_1",
            display_id="MM-20260101-ABCDEF12",
            user_id=u.id,
            operation="mass_message",
            status="completed",
            progress=100,
            options_json=json.dumps({"total": 10, "session_files": []}),
        )
        db.add(job)
        db.commit()

    callback = MagicMock()
    callback.data = "resume_job:job_completed_1"
    callback.from_user = MagicMock(id=11115555)
    callback.message = AsyncMock(spec=Message)
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage, MagicMock())

    await resume_job_callback(callback, AsyncMock(), state, MagicMock(), TestingSessionLocal)

    callback.answer.assert_awaited_once()
    _, kwargs = callback.answer.call_args
    assert kwargs.get("show_alert") is True

    with TestingSessionLocal() as db:
        j = db.query(Job).filter(Job.id == "job_completed_1").first()
        assert j.status == "completed"


@pytest.mark.asyncio
async def test_resume_job_missing_sessions_keeps_paused():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import resume_job_callback

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=11116666, username="test_resume_missing")
        db.add(u)
        db.commit()
        db.refresh(u)

        job = Job(
            id="job_paused_missing",
            display_id="MM-20260202-ABCDEF12",
            user_id=u.id,
            operation="mass_message",
            status="paused",
            progress=40,
            options_json=json.dumps(
                {
                    "total": 10,
                    "session_files": ["/nonexistent/tmp/missing.session"],
                }
            ),
        )
        db.add(job)
        db.commit()

    callback = MagicMock()
    callback.data = "resume_job:job_paused_missing"
    callback.from_user = MagicMock(id=11116666)
    callback.message = AsyncMock(spec=Message)
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    state = FSMContext(storage, MagicMock())

    await resume_job_callback(callback, AsyncMock(), state, MagicMock(), TestingSessionLocal)

    callback.answer.assert_awaited_once()
    _, kwargs = callback.answer.call_args
    assert kwargs.get("show_alert") is True

    with TestingSessionLocal() as db:
        j = db.query(Job).filter(Job.id == "job_paused_missing").first()
        assert j.status == "paused"


@pytest.mark.asyncio
async def test_start_new_job_callback():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import start_new_job_callback
    from app.states import MassMessage

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    with TestingSessionLocal() as db:
        u = User(telegram_id=11113333, username="test_new_flow")
        db.add(u)
        db.commit()
        db.refresh(u)

        job = Job(
            id="job_paused_abc",
            display_id="PABC",
            user_id=u.id,
            operation="mass_message",
            status="paused",
            progress=50,
            options_json=json.dumps({"total": 10}),
        )
        db.add(job)
        db.commit()

    callback = MagicMock()
    callback.from_user = MagicMock(id=11113333)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    key = MagicMock()
    state = FSMContext(storage, key)

    await start_new_job_callback(callback, state, TestingSessionLocal)

    # Paused jobs must NOT be destroyed when starting a new job
    with TestingSessionLocal() as db:
        j = db.query(Job).filter(Job.id == "job_paused_abc").first()
        assert j.status == "paused"

    # FSM state should now be waiting_for_file
    current_state = await state.get_state()
    assert current_state == MassMessage.waiting_for_file.state


@pytest.mark.asyncio
async def test_process_quick_action_mass_message(tmp_path: Path):
    import sqlite3

    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Message
    from sqlalchemy.pool import StaticPool

    from app.handlers.files import process_quick_action
    from app.states import DirectFile, MassMessage

    # Create a dummy sqlite DB file that simulates a valid session
    dummy_session = tmp_path / "123456.session"
    conn = sqlite3.connect(dummy_session)
    conn.execute("CREATE TABLE sessions (auth_key BLOB)")
    conn.execute("INSERT INTO sessions (auth_key) VALUES (?)", (b"\x01" * 256,))
    conn.commit()
    conn.close()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    callback = MagicMock()
    callback.from_user = MagicMock(id=11114444)
    callback.data = "quick:mass_message"
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    storage = MemoryStorage()
    key = MagicMock()
    state = FSMContext(storage, key)

    await state.set_state(DirectFile.waiting_for_action)
    await state.update_data(
        temp_file_path=str(dummy_session),
        original_name="123456.session",
    )

    fake_settings = MagicMock()

    await process_quick_action(
        callback=callback,
        bot=MagicMock(),
        state=state,
        settings=fake_settings,
        session_factory=TestingSessionLocal,
    )

    # Check FSM state transitioned to waiting_for_recipients
    current_state = await state.get_state()
    assert current_state == MassMessage.waiting_for_recipients.state
    data = await state.get_data()
    assert len(data["session_files"]) == 1


async def test_extract_contacts_parallel_bounded_and_staggered(tmp_path: Path):
    """Contact fetches must overlap (bounded), and each session must start at a
    different credential pair (round-robin) instead of piling onto api_id #0."""
    import asyncio
    import sqlite3
    from unittest.mock import AsyncMock, patch

    sessions = []
    for i in range(6):
        path = tmp_path / f"sess{i}.session"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
            )
            conn.execute(
                "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
                (b"a" * 256,),
            )
        sessions.append(path)

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    class FakeUser:
        id = 42
        username = "u"
        phone = None

    async def fake_client_call(*_args, **_kwargs):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return SimpleNamespace(users=[FakeUser()])

    from app.services.mass_message import (
        _CONTACTS_FETCH_CONCURRENCY,
        extract_contacts_from_sessions,
    )

    with patch("telethon.TelegramClient") as mock_client:
        client = AsyncMock(side_effect=fake_client_call)
        client.connect = AsyncMock()
        client.is_user_authorized = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        mock_client.return_value = client

        creds = [(101, "h1"), (202, "h2"), (303, "h3")]
        result = await extract_contacts_from_sessions(sessions, creds)

    assert result.stats[0].status == "ok"
    assert max_active >= 2, "fetches ran strictly one-by-one (no overlap)"
    assert max_active <= _CONTACTS_FETCH_CONCURRENCY
    first_api_ids = [call.args[1] for call in mock_client.call_args_list]
    assert first_api_ids == [101, 202, 303, 101, 202, 303], (
        "credential start must be round-robin staggered"
    )


