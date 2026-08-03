"""tests/test_feature_gate_middleware.py — Unit tests for FeatureGateMiddleware (VIP vs Free access enforcement)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery
from aiogram.types import User as TelegramUser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base
from app.db.repositories import (
    add_admin_user,
    grant_user_vip,
    toggle_feature_access_level,
    upsert_user,
)
from app.middlewares.feature_gate import FeatureGateMiddleware


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    return sessionmaker(bind=engine)


@pytest.mark.asyncio
async def test_normal_user_allowed_on_free_feature(db_session_factory) -> None:
    normal_user_id = 111222333
    with db_session_factory() as session:
        upsert_user(session, normal_user_id, "normal_user")

    middleware = FeatureGateMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TelegramUser(id=normal_user_id, is_bot=False, first_name="Normal")
    cb.data = "tool:session_check"
    cb.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": db_session_factory,
    }

    result = await middleware(handler_mock, cb, data)
    assert result == "executed"
    handler_mock.assert_called_once()


@pytest.mark.asyncio
async def test_normal_user_blocked_on_vip_feature(db_session_factory) -> None:
    normal_user_id = 444555666
    with db_session_factory() as session:
        upsert_user(session, normal_user_id, "free_user")
        toggle_feature_access_level(session, "session_check")  # Makes session_check VIP_ONLY

    middleware = FeatureGateMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg_mock = AsyncMock()
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TelegramUser(id=normal_user_id, is_bot=False, first_name="FreeUser")
    cb.data = "tool:session_check"
    cb.message = msg_mock
    cb.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": db_session_factory,
    }

    result = await middleware(handler_mock, cb, data)
    assert result is None
    handler_mock.assert_not_called()
    cb.answer.assert_called_once()
    msg_mock.edit_text.assert_called_once()
    assert "VIP" in msg_mock.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_vip_user_allowed_on_vip_feature(db_session_factory) -> None:
    vip_user_id = 777888999
    with db_session_factory() as session:
        u = upsert_user(session, vip_user_id, "vip_user")
        grant_user_vip(session, u.telegram_id, months=1)
        toggle_feature_access_level(session, "read_otp")  # Makes read_otp VIP_ONLY

    middleware = FeatureGateMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TelegramUser(id=vip_user_id, is_bot=False, first_name="VipUser")
    cb.data = "tool:read_otp"
    cb.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": db_session_factory,
    }

    result = await middleware(handler_mock, cb, data)
    assert result == "executed"
    handler_mock.assert_called_once()


@pytest.mark.asyncio
async def test_admin_bypasses_vip_feature_restriction(db_session_factory) -> None:
    admin_id = 999111222
    with db_session_factory() as session:
        upsert_user(session, admin_id, "admin_user")
        add_admin_user(session, admin_id, role="ADMIN")
        toggle_feature_access_level(session, "mass_message")  # Makes mass_message VIP_ONLY

    middleware = FeatureGateMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = TelegramUser(id=admin_id, is_bot=False, first_name="AdminUser")
    cb.data = "tool:mass_message"
    cb.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": db_session_factory,
    }

    result = await middleware(handler_mock, cb, data)
    assert result == "executed"
    handler_mock.assert_called_once()
