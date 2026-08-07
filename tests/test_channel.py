import re
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery
from telethon.types import ChatInvite  # type: ignore[import-untyped]

from app.handlers.files import channel_noop
from app.keyboards import channel_result_menu
from app.locales import CHANNEL_JOIN_PROMPTS, CHANNEL_LEAVE_PROMPTS, CHANNEL_MESSAGES
from app.services.channel import (
    parse_channel_target,
    process_channel_join,
    process_channel_leave,
)


def _create_session(path: Path) -> Path:
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


def test_parse_channel_target():
    assert parse_channel_target("@mychan") == ("mychan", False)
    assert parse_channel_target("https://t.me/mychan") == ("mychan", False)
    assert parse_channel_target("t.me/mychan") == ("mychan", False)
    assert parse_channel_target("https://t.me/+Hash123_45") == ("Hash123_45", True)
    assert parse_channel_target("t.me/joinchat/Hash123_45") == ("Hash123_45", True)


@pytest.mark.asyncio
async def test_process_channel_join_single(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_join(
            dummy_session,
            tmp_path / "out",
            "@testchannel",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0
    assert res.is_zip is False
    assert res.output_path is not None
    assert re.match(r"^Channel_Joined_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_channel_join_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_join(
            zip_path,
            tmp_path / "out",
            "https://t.me/+PrivateInviteHash",
            [(123, "hash")],
        )

    assert res.total == 2
    assert res.success == 2
    assert res.failed == 0
    assert res.is_zip is True
    assert res.output_path is not None
    assert re.match(r"^Channel_Joined_2_[a-f0-9]{6}\.zip$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_channel_leave_single(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "@testchannel",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert re.match(r"^Channel_Left_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_channel_leave_all(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyDialog:
        is_channel = True
        is_group = False
        entity = "channel_entity"

    async def mock_iter_dialogs():
        yield DummyDialog()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "all",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0


@pytest.mark.asyncio
async def test_process_channel_leave_all_partial_failure(
    dummy_session: Path, tmp_path: Path
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyDialog1:
        is_channel = True
        is_group = False
        entity = "channel_ok"

    class DummyDialog2:
        is_channel = True
        is_group = False
        entity = "channel_fail"

    async def mock_iter_dialogs():
        yield DummyDialog1()
        yield DummyDialog2()

    mock_client.iter_dialogs = mock_iter_dialogs

    def side_effect(req):
        if getattr(req, "channel", None) == "channel_fail":
            raise RuntimeError("Cannot leave channel_fail")

    mock_client.side_effect = side_effect
    mock_client.delete_dialog.side_effect = RuntimeError("Delete dialog fail")

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "all",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 0
    assert res.failed == 1


@pytest.mark.asyncio
async def test_process_channel_leave_private_link(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyChat:
        id = 12345

    class DummyInviteAlready:
        chat = DummyChat()

    mock_client.side_effect = lambda req: (
        DummyInviteAlready() if "CheckChatInviteRequest" in type(req).__name__ else None
    )

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "https://t.me/+PrivateInviteHash",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0


@pytest.mark.asyncio
async def test_process_channel_leave_unjoined_private_link(
    dummy_session: Path, tmp_path: Path
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyChatInvite(ChatInvite):
        def __init__(self):
            pass

    mock_client.side_effect = lambda req: (
        DummyChatInvite() if "CheckChatInviteRequest" in type(req).__name__ else None
    )

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "https://t.me/+UnjoinedHash",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0


@pytest.mark.asyncio
async def test_process_channel_leave_normal_group(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyGroupEntity:
        id = 9999

    class DummyGroupDialog:
        is_channel = False
        is_group = True
        entity = DummyGroupEntity()

    async def mock_iter_dialogs():
        yield DummyGroupDialog()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "all",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0


@pytest.mark.asyncio
async def test_process_channel_leave_failure_counts_as_failed(
    dummy_session: Path, tmp_path: Path
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyGroupEntity:
        id = 9999

    class DummyGroupDialog:
        is_channel = True
        is_group = False
        entity = DummyGroupEntity()

    async def mock_iter_dialogs():
        yield DummyGroupDialog()

    mock_client.iter_dialogs = mock_iter_dialogs
    mock_client.side_effect = RuntimeError("Leave Error")
    mock_client.delete_dialog.side_effect = RuntimeError("Leave Error")

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_channel_leave(
            dummy_session,
            tmp_path / "out",
            "all",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 0
    assert res.failed == 1


@pytest.mark.asyncio
async def test_channel_noop_callback():
    callback_mock = AsyncMock(spec=CallbackQuery)
    callback_mock.answer = AsyncMock()
    await channel_noop(callback_mock)
    callback_mock.answer.assert_called_once()


def test_channel_locales_and_keyboards():
    assert len(CHANNEL_JOIN_PROMPTS) == 6
    assert len(CHANNEL_LEAVE_PROMPTS) == 6
    assert len(CHANNEL_MESSAGES) == 6

    kb = channel_result_menu(5, 4, 1, "en")
    assert kb is not None
    assert len(kb.inline_keyboard) == 4
    assert kb.inline_keyboard[3][0].callback_data == "menu:back"
    for lang in ("en", "bn", "hi", "ur", "ar", "zh"):
        msgs = CHANNEL_MESSAGES[lang]
        assert "failed_report" in msgs
        assert "invalid_target" in msgs


@pytest.mark.asyncio
async def test_channel_join_rejects_all_target(tmp_path: Path) -> None:
    from aiogram.types import Message
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.handlers.files import receive_channel_join_target

    engine = create_engine("sqlite:///:memory:")
    from app.db.migration import run_migrations
    from app.db.models import Base
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={"temp_file_path": str(tmp_path / "x.session"), "original_name": "x.session"}
    )
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=1)
    message.text = "all"
    message.answer = AsyncMock()

    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = [(1, "h")]

    with patch(
        "app.handlers.files.process_channel_join"
    ) as process_mock:
        await receive_channel_join_target(message, state, settings, session_factory)

    process_mock.assert_not_called()
    message.answer.assert_awaited_once()
    assert "Invalid target" in message.answer.call_args.args[0]
    assert state.clear.await_count == 0


@pytest.mark.asyncio
async def test_channel_join_rejects_blank_target(tmp_path: Path) -> None:
    from aiogram.types import Message
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.handlers.files import receive_channel_join_target

    engine = create_engine("sqlite:///:memory:")
    from app.db.migration import run_migrations
    from app.db.models import Base
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={"temp_file_path": str(tmp_path / "x.session"), "original_name": "x.session"}
    )
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=1)
    message.text = "   "
    message.answer = AsyncMock()

    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = [(1, "h")]

    with patch(
        "app.handlers.files.process_channel_join"
    ) as process_mock:
        await receive_channel_join_target(message, state, settings, session_factory)

    process_mock.assert_not_called()


@pytest.mark.asyncio
async def test_channel_leave_rejects_blank_target(tmp_path: Path) -> None:
    from aiogram.types import Message
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.handlers.files import receive_channel_leave_target

    engine = create_engine("sqlite:///:memory:")
    from app.db.migration import run_migrations
    from app.db.models import Base
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={"temp_file_path": str(tmp_path / "x.session"), "original_name": "x.session"}
    )
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=1)
    message.text = "a b c"
    message.answer = AsyncMock()

    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = [(1, "h")]

    with patch(
        "app.handlers.files.process_channel_leave"
    ) as process_mock:
        await receive_channel_leave_target(message, state, settings, session_factory)

    process_mock.assert_not_called()
    message.answer.assert_awaited_once()
    assert "Invalid target" in message.answer.call_args.args[0]


def test_channel_emoji_keys_are_mapped() -> None:
    from app.ui.emojis import EmojiRegistry

    assert EmojiRegistry.EMOJI_UNICODE_KEYS["🔗"] == "LINK"
    assert EmojiRegistry.EMOJI_UNICODE_KEYS["🚪"] == "EXIT"
