"""tests/test_force_join.py — Force-join unified service, middleware and admin add-flow tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TelegramUser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base
from app.db.repositories import add_admin_user, add_force_join_channel, upsert_user
from app.middlewares.force_join import ForceJoinMiddleware
from app.services.force_join import get_active_force_join_channels


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    return sessionmaker(bind=engine)


def make_settings(required: str = "") -> Settings:
    return Settings(required_channels=required)


def member_with(status: str) -> MagicMock:
    member = MagicMock()
    member.status = status
    return member


def test_get_active_force_join_channels_merges_db_and_env(db_session_factory) -> None:
    with db_session_factory() as session:
        add_force_join_channel(session, channel_id="@dbenabled", title="DB Enabled")
        add_force_join_channel(session, channel_id="@dbdisabled", title="DB Disabled")
        from app.db.repositories import toggle_force_join_channel

        toggle_force_join_channel(session, "@dbdisabled")

    settings = make_settings(required="@dbenabled, @envchannel, @dbdisabled")

    with db_session_factory() as session:
        channels = get_active_force_join_channels(session, settings)

    # DB-active first, then env-only; duplicates and DB-inactive excluded
    assert channels == ["@dbenabled", "@envchannel"]


def test_get_active_force_join_channels_empty(db_session_factory) -> None:
    settings = make_settings(required="")
    with db_session_factory() as session:
        assert get_active_force_join_channels(session, settings) == []


@pytest.mark.asyncio
async def test_middleware_blocks_non_member(db_session_factory) -> None:
    user_id = 111222333
    with db_session_factory() as session:
        upsert_user(session, user_id, "free_user")

    middleware = ForceJoinMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=user_id, is_bot=False, first_name="Free")
    msg.text = "hello"
    msg.answer = AsyncMock()

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=member_with(ChatMemberStatus.LEFT))

    data = {
        "settings": make_settings(required="@FastTGConvert"),
        "session_factory": db_session_factory,
        "bot": bot,
    }

    result = await middleware(handler_mock, msg, data)

    assert result is None
    handler_mock.assert_not_called()
    msg.answer.assert_awaited_once()
    assert "@FastTGConvert" in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_middleware_allows_member(db_session_factory) -> None:
    user_id = 444555666
    with db_session_factory() as session:
        upsert_user(session, user_id, "member")

    middleware = ForceJoinMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=user_id, is_bot=False, first_name="Member")
    msg.text = "hello"
    msg.answer = AsyncMock()

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=member_with(ChatMemberStatus.MEMBER))

    data = {
        "settings": make_settings(required="@FastTGConvert"),
        "session_factory": db_session_factory,
        "bot": bot,
    }

    result = await middleware(handler_mock, msg, data)

    assert result == "executed"
    handler_mock.assert_awaited_once()
    msg.answer.assert_not_called()


@pytest.mark.asyncio
async def test_middleware_allows_admin_bypass(db_session_factory) -> None:
    admin_id = 777888999
    with db_session_factory() as session:
        upsert_user(session, admin_id, "admin")
        add_admin_user(session, admin_id, role="SUPPORT")

    middleware = ForceJoinMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=admin_id, is_bot=False, first_name="Admin")
    msg.text = "hello"

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=member_with(ChatMemberStatus.LEFT))

    data = {
        "settings": make_settings(required="@FastTGConvert"),
        "session_factory": db_session_factory,
        "bot": bot,
    }

    result = await middleware(handler_mock, msg, data)

    assert result == "executed"
    handler_mock.assert_awaited_once()
    bot.get_chat_member.assert_not_called()


@pytest.mark.asyncio
async def test_middleware_allows_membership_check_callback(db_session_factory) -> None:
    user_id = 111333555
    with db_session_factory() as session:
        upsert_user(session, user_id, "checker")

    middleware = ForceJoinMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TelegramUser(id=user_id, is_bot=False, first_name="Checker")
    cb.data = "membership:check:en"
    cb.answer = AsyncMock()

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=member_with(ChatMemberStatus.LEFT))

    data = {
        "settings": make_settings(required="@FastTGConvert"),
        "session_factory": db_session_factory,
        "bot": bot,
    }

    result = await middleware(handler_mock, cb, data)

    assert result == "executed"
    handler_mock.assert_awaited_once()
    bot.get_chat_member.assert_not_called()


@pytest.mark.asyncio
async def test_middleware_bypasses_when_no_channels(db_session_factory) -> None:
    user_id = 222333444
    with db_session_factory() as session:
        upsert_user(session, user_id, "nobody")

    middleware = ForceJoinMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=user_id, is_bot=False, first_name="Nobody")
    msg.text = "hello"

    data = {
        "settings": make_settings(required=""),
        "session_factory": db_session_factory,
        "bot": MagicMock(),
    }

    result = await middleware(handler_mock, msg, data)

    assert result == "executed"
    handler_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_add_channel_input_validates_chat(db_session_factory) -> None:
    from app.admin.handlers.force_join import process_add_channel_input
    from app.admin.states import AddForceJoinState

    state = AsyncMock(spec=AddForceJoinState)
    state.clear = AsyncMock()

    message = MagicMock(spec=Message)
    message.reply = AsyncMock()
    message.from_user = TelegramUser(id=999, is_bot=False, first_name="Admin")
    message.text = "@mychannel"

    bot = MagicMock()
    chat = MagicMock(spec=Chat)
    chat.username = "mychannel"
    chat.title = "My Channel"
    chat.invite_link = None
    bot.get_chat = AsyncMock(return_value=chat)

    with patch("app.admin.handlers.force_join.add_force_join_channel") as add_mock:
        add_mock.return_value._previously_existed = False
        await process_add_channel_input(message, state, db_session_factory, bot)

    add_mock.assert_called_once()
    args = add_mock.call_args.kwargs
    assert args["channel_id"] == "@mychannel"
    assert args["username"] == "mychannel"
    assert args["channel_type"] == "public"
    assert args["title"] == "My Channel"


@pytest.mark.asyncio
async def test_process_add_channel_input_rejects_unreachable_chat(db_session_factory) -> None:
    from app.admin.handlers.force_join import process_add_channel_input
    from app.admin.states import AddForceJoinState

    state = AsyncMock(spec=AddForceJoinState)
    state.clear = AsyncMock()

    message = MagicMock(spec=Message)
    message.reply = AsyncMock()
    message.from_user = TelegramUser(id=999, is_bot=False, first_name="Admin")
    message.text = "-1009999999999"

    bot = MagicMock()
    bot.get_chat = AsyncMock(side_effect=TelegramBadRequest(method="getChat", message="chat not found"))

    with patch("app.admin.handlers.force_join.add_force_join_channel") as add_mock:
        await process_add_channel_input(message, state, db_session_factory, bot)

    add_mock.assert_not_called()
    message.reply.assert_awaited_once()
    assert "not found" in message.reply.call_args.args[0].lower()


def test_membership_menu_private_channel_uses_invite_link() -> None:
    from app.keyboards import membership_menu

    menu = membership_menu(
        ("-100123456789",), "en", {"-100123456789": "https://t.me/+abcdef"}
    )
    row = menu.inline_keyboard[0]
    assert row[0].url == "https://t.me/+abcdef"
    assert row[1].callback_data == "membership:check:en"


def test_membership_menu_private_channel_without_link_keeps_check() -> None:
    from app.keyboards import membership_menu

    menu = membership_menu(("-100123456789",), "en")
    assert menu.inline_keyboard[0][0].url is None
    assert menu.inline_keyboard[0][0].callback_data == "membership:check:en"
