import re
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import clean_chat_noop
from app.keyboards import clean_chat_choice_menu, clean_chat_result_menu
from app.locales import (
    CLEAN_CHAT_MESSAGES,
    CLEAN_CHAT_MODE_LABELS,
    CLEAN_CHAT_MODE_PROMPT,
    CLEAN_CHAT_SELECTION_ACTIONS,
    ENTER_CLEAN_CHAT_PROMPT,
)
from app.services.clean_chat import (
    clean_session_chats,
    process_clean_chat,
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


@pytest.mark.asyncio
async def test_clean_session_chats_dms(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyDialogUser:
        is_user = True
        is_group = False
        is_channel = False
        entity = "user_entity"
        input_entity = "input_user"

    class DummyDialogGroup:
        is_user = False
        is_group = True
        is_channel = False
        entity = "group_entity"
        input_entity = "input_group"

    class DummyBotEntity:
        bot = True

    class DummyDialogBot:
        is_user = True
        is_group = False
        is_channel = False
        entity = DummyBotEntity()
        input_entity = "input_bot"

    async def mock_iter_dialogs():
        yield DummyDialogUser()
        yield DummyDialogBot()
        yield DummyDialogGroup()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(dummy_session, [(123, "hash")], mode="dms")

    assert res is True
    mock_client.delete_dialog.assert_awaited_once_with("user_entity", revoke=False)


@pytest.mark.asyncio
async def test_clean_session_chats_combines_dms_and_bots(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyUserEntity:
        bot = False

    class DummyBotEntity:
        bot = True

    class DummyDialog:
        is_user = True
        is_group = False
        is_channel = False

        def __init__(self, entity: object) -> None:
            self.entity = entity
            self.input_entity = entity

    async def mock_iter_dialogs():
        yield DummyDialog(DummyUserEntity())
        yield DummyDialog(DummyBotEntity())

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(
            dummy_session,
            [(123, "hash")],
            mode={"dms", "bots"},
        )

    assert res is True
    assert mock_client.delete_dialog.await_count == 2


@pytest.mark.asyncio
async def test_clean_session_chats_groups(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyDialogGroup:
        is_user = False
        is_group = True
        is_channel = False
        entity = "group_entity"
        input_entity = "input_group"

    async def mock_iter_dialogs():
        yield DummyDialogGroup()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(dummy_session, [(123, "hash")], mode="groups")

    assert res is True
    mock_client.delete_dialog.assert_awaited_once_with("group_entity", revoke=False)


@pytest.mark.asyncio
async def test_clean_session_chats_groups_excludes_broadcast_channels(
    dummy_session: Path,
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyBroadcastEntity:
        broadcast = True

    class DummyBroadcastDialog:
        is_user = False
        is_group = False
        is_channel = True
        entity = DummyBroadcastEntity()
        input_entity = "input_broadcast"

    async def mock_iter_dialogs():
        yield DummyBroadcastDialog()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(dummy_session, [(123, "hash")], mode="groups")

    assert res is True
    mock_client.assert_not_awaited()
    mock_client.delete_dialog.assert_not_awaited()


@pytest.mark.asyncio
async def test_clean_session_chats_all_removes_dms_and_channels(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyUserDialog:
        is_user = True
        is_group = False
        is_channel = False
        entity = "user_entity"
        input_entity = "input_user"

    class DummyChannelEntity:
        broadcast = True

    class DummyChannelDialog:
        is_user = False
        is_group = False
        is_channel = True
        entity = DummyChannelEntity()
        input_entity = "input_channel"

    async def mock_iter_dialogs():
        yield DummyUserDialog()
        yield DummyChannelDialog()

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(dummy_session, [(123, "hash")], mode="all")

    assert res is True
    assert mock_client.delete_dialog.await_count == 2
    assert mock_client.delete_dialog.await_args_list[0].args == ("user_entity",)
    assert mock_client.delete_dialog.await_args_list[0].kwargs == {"revoke": False}
    assert mock_client.delete_dialog.await_args_list[1].args == (
        DummyChannelDialog.entity,
    )
    assert mock_client.delete_dialog.await_args_list[1].kwargs == {"revoke": False}


@pytest.mark.asyncio
async def test_clean_session_chats_partial_failure_is_failed(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyGroupDialog:
        is_user = False
        is_group = True
        is_channel = False

        def __init__(self, identifier: str) -> None:
            self.entity = identifier
            self.input_entity = identifier

    async def mock_iter_dialogs():
        yield DummyGroupDialog("group_ok")
        yield DummyGroupDialog("group_failed")

    async def delete_dialog(entity, *, revoke):
        if entity == "group_failed":
            raise RuntimeError("history deletion failed")

    mock_client.iter_dialogs = mock_iter_dialogs
    mock_client.delete_dialog.side_effect = delete_dialog

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clean_session_chats(dummy_session, [(123, "hash")], mode="all")

    assert res is False


@pytest.mark.asyncio
async def test_clean_session_chats_rejects_invalid_mode(dummy_session: Path):
    with pytest.raises(ValueError, match="invalid_clean_chat_selection"):
        await clean_session_chats(dummy_session, [(123, "hash")], mode="invalid")

    with pytest.raises(ValueError, match="invalid_clean_chat_selection"):
        await clean_session_chats(dummy_session, [(123, "hash")], mode=set())


@pytest.mark.asyncio
async def test_process_clean_chat_single(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    async def mock_iter_dialogs():
        if False:
            yield None

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_clean_chat(
            dummy_session,
            tmp_path / "out",
            mode={"dms", "bots"},
            credentials=[(123, "hash")],
        )

    assert res.total == 1
    assert res.cleaned == 1
    assert res.failed == 0
    assert res.is_zip is False
    assert res.output_path is not None
    assert re.match(r"^Clean_Chat_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_clean_chat_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    async def mock_iter_dialogs():
        if False:
            yield None

    mock_client.iter_dialogs = mock_iter_dialogs

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_clean_chat(
            zip_path,
            tmp_path / "out",
            mode="all",
            credentials=[(123, "hash")],
        )

    assert res.total == 2
    assert res.cleaned == 2
    assert res.failed == 0
    assert res.is_zip is True
    assert res.output_path is not None
    assert re.match(r"^Clean_Chat_2_[a-f0-9]{6}\.zip$", res.output_path.name)


@pytest.mark.asyncio
async def test_clean_chat_noop_callback():
    callback_mock = AsyncMock(spec=CallbackQuery)
    callback_mock.answer = AsyncMock()
    await clean_chat_noop(callback_mock)
    callback_mock.answer.assert_called_once()


def test_clean_chat_locales_and_keyboards():
    assert len(ENTER_CLEAN_CHAT_PROMPT) == 6
    assert len(CLEAN_CHAT_MODE_PROMPT) == 6
    assert len(CLEAN_CHAT_MODE_LABELS) == 6
    assert len(CLEAN_CHAT_SELECTION_ACTIONS) == 6
    assert len(CLEAN_CHAT_MESSAGES) == 6

    choice_kb = clean_chat_choice_menu("en", selected={"dms", "channels"})
    assert choice_kb is not None
    assert len(choice_kb.inline_keyboard) == 5
    assert choice_kb.inline_keyboard[0][0].text.startswith("✅")
    assert choice_kb.inline_keyboard[0][1].text.startswith("▫️")
    assert choice_kb.inline_keyboard[1][0].text.startswith("▫️")
    assert choice_kb.inline_keyboard[1][1].text.startswith("✅")
    assert choice_kb.inline_keyboard[3][0].callback_data == "clean_chat_confirm"
    assert choice_kb.inline_keyboard[4][0].callback_data == "action:cancel"

    res_kb = clean_chat_result_menu(5, 4, 1, "en")
    assert res_kb is not None
    assert len(res_kb.inline_keyboard) == 3
