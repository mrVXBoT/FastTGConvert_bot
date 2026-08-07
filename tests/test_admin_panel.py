"""tests/test_admin_panel.py — Comprehensive unit tests for Payments, VIP Subscriptions, Worker Broadcast, RBAC & User Ban Middleware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Message
from aiogram.types import User as TelegramUser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.admin.middlewares import AdminPermissionMiddleware
from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base
from app.db.repositories import (
    activate_vip_subscription_flow,
    add_admin_user,
    add_force_join_channel,
    add_vip_plan,
    cancel_sibling_auto_orders,
    create_auto_payment_orders,
    create_payment_order,
    expire_auto_payments,
    get_admin_role,
    get_dashboard_statistics,
    grant_user_vip,
    is_transaction_used,
    list_force_join_channels,
    list_pending_payments,
    list_vip_plans,
    reject_payment,
    set_user_ban_status,
    toggle_feature_access_level,
    toggle_force_join_channel,
    upsert_user,
)
from app.middlewares.user_status import UserStatusMiddleware
from app.services.broadcast import BroadcastQueueWorker
from app.services.feature_gate import is_feature_accessible


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_admin_rbac_roles(db_session) -> None:
    owner_id = 999999
    admin_id = 888888
    normal_id = 777777

    add_admin_user(db_session, admin_id, role="ADMIN")

    assert get_admin_role(db_session, owner_id, owner_id=owner_id) == "OWNER"
    assert get_admin_role(db_session, admin_id, owner_id=owner_id) == "ADMIN"
    assert get_admin_role(db_session, normal_id, owner_id=owner_id) is None


def test_feature_gate_and_vip_access(db_session) -> None:
    u = upsert_user(db_session, 123456, "testuser")

    accessible, reason = is_feature_accessible(db_session, u.telegram_id, "session_check")
    assert accessible is True

    toggle_feature_access_level(db_session, "session_check")

    accessible, reason = is_feature_accessible(db_session, u.telegram_id, "session_check")
    assert accessible is False
    assert reason == "feature_vip_only"

    grant_user_vip(db_session, u.telegram_id, months=1)

    accessible, reason = is_feature_accessible(db_session, u.telegram_id, "session_check")
    assert accessible is True
    assert reason == "ok"


def test_payment_and_vip_activation_pipeline(db_session) -> None:
    u = upsert_user(db_session, 987654, "buyer")
    plan = add_vip_plan(db_session, "Special 3 Months", months=3, price=30.0)

    # 1. Create Payment Order
    payment = create_payment_order(
        db_session,
        user_id=u.id,
        plan_id=plan.id,
        amount=30.0,
        payment_method="trc20",
        transaction_id="TX998877",
    )
    assert payment.id is not None
    assert payment.status == "pending"

    pending_list = list_pending_payments(db_session)
    assert len(pending_list) >= 1

    # 2. Activate VIP via Payment Approval
    sub = activate_vip_subscription_flow(db_session, payment.id)
    assert sub is not None
    assert sub.status == "active"
    assert sub.payment_id == payment.id

    # Verify user state updated
    db_session.refresh(u)
    assert u.is_vip is True
    assert u.vip_expires_at is not None

    # Verify Revenue calculated in Dashboard Stats
    now = datetime.now(UTC)
    stats = get_dashboard_statistics(db_session, since_time=now - timedelta(days=1))
    assert stats["revenue_total"] >= 30.0
    assert stats["vip_purchases"] >= 1


def test_payment_rejection(db_session) -> None:
    u = upsert_user(db_session, 112233, "reject_user")
    plan = list_vip_plans(db_session)[0]
    payment = create_payment_order(
        db_session, user_id=u.id, plan_id=plan.id, amount=10.0, payment_method="manual"
    )

    ok = reject_payment(db_session, payment.id)
    assert ok is True
    assert payment.status == "rejected"


def test_broadcast_queue_worker_cancel(db_session) -> None:
    worker = BroadcastQueueWorker()
    job = worker.create_job(session=db_session, message_type="custom", text="Hello All Users")
    assert job.status == "pending"

    canceled = worker.cancel_job(session=db_session, job_id=job.job_id)
    assert canceled is True
    assert job.status == "cancelled"
    assert job.cancel_requested is True


@pytest.mark.asyncio
async def test_broadcast_worker_persistence_and_restore(db_session) -> None:
    worker = BroadcastQueueWorker()
    job = worker.create_job(session=db_session, message_type="custom", text="Persistent Message")
    assert job.status == "pending"

    new_worker = BroadcastQueueWorker()
    restored = await new_worker.restore_unprocessed_jobs(db_session)
    assert len(restored) >= 1
    assert any(j.job_id == job.job_id for j in restored)


def test_system_settings_support_contact_persistence(db_session) -> None:
    from app.db.repositories import get_support_contact, set_support_contact

    set_support_contact(db_session, "@my_new_support")
    assert get_support_contact(db_session) == "@my_new_support"


@pytest.mark.asyncio
async def test_banned_user_cannot_use_bot() -> None:
    """Verify that a BANNED user update is stopped by UserStatusMiddleware."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    banned_user_id = 555444333

    with session_factory() as session:
        upsert_user(session, banned_user_id, "banneduser")
        set_user_ban_status(session, banned_user_id, banned=True)

    middleware = UserStatusMiddleware()
    handler_mock = AsyncMock()

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=banned_user_id, is_bot=False, first_name="Banned")
    msg.chat = Chat(id=banned_user_id, type="private")
    msg.answer = AsyncMock()

    settings_mock = MagicMock(spec=Settings)
    settings_mock.admin_id = 999999

    data = {
        "settings": settings_mock,
        "session_factory": session_factory,
    }

    result = await middleware(handler_mock, msg, data)

    # Verify execution was stopped and error message was sent
    assert result is None
    handler_mock.assert_not_called()
    msg.answer.assert_called_once()
    assert "suspended" in msg.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_admin_bypasses_ban_status() -> None:
    """Verify that Admins/Owners bypass the ban check and can still access bot handlers."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    admin_user_id = 777666555

    with session_factory() as session:
        upsert_user(session, admin_user_id, "adminuser")
        add_admin_user(session, admin_user_id, role="ADMIN")
        set_user_ban_status(session, admin_user_id, banned=True)

    middleware = UserStatusMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    msg = MagicMock(spec=Message)
    msg.from_user = TelegramUser(id=admin_user_id, is_bot=False, first_name="Admin")
    msg.chat = Chat(id=admin_user_id, type="private")

    settings_mock = MagicMock(spec=Settings)
    settings_mock.admin_id = 999999

    data = {
        "settings": settings_mock,
        "session_factory": session_factory,
    }

    result = await middleware(handler_mock, msg, data)

    # Verify admin bypasses ban check and handler executes
    assert result == "executed"
    handler_mock.assert_called_once()


@pytest.mark.asyncio
async def test_support_role_blocked_from_payment_callbacks() -> None:
    """SUPPORT must NOT be able to trigger payment (approve/reject) callbacks (C1)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    support_id = 111222333
    with session_factory() as session:
        add_admin_user(session, support_id, role="SUPPORT")

    middleware = AdminPermissionMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    from aiogram.types import CallbackQuery

    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = TelegramUser(id=support_id, is_bot=False, first_name="Support")
    callback.data = "adm_pay:approve:1"
    callback.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": session_factory,
    }

    result = await middleware(handler_mock, callback, data)

    assert result is None
    handler_mock.assert_not_called()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_role_allowed_into_payment_callbacks() -> None:
    """ADMIN must pass the middleware gate for payment callbacks (C1)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)

    admin_id = 444555666
    with session_factory() as session:
        add_admin_user(session, admin_id, role="ADMIN")

    middleware = AdminPermissionMiddleware()
    handler_mock = AsyncMock(return_value="executed")

    from aiogram.types import CallbackQuery

    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = TelegramUser(id=admin_id, is_bot=False, first_name="Admin")
    callback.data = "adm_plan:delete:3"
    callback.answer = AsyncMock()

    data = {
        "settings": MagicMock(spec=Settings, admin_id=999999),
        "session_factory": session_factory,
    }

    result = await middleware(handler_mock, callback, data)

    assert result == "executed"
    handler_mock.assert_awaited_once()
    assert handler_mock.await_args.args[1]["admin_role"] == "ADMIN"


def test_force_join_channel_toggle(db_session) -> None:
    """Toggle must flip is_active and persist (M3)."""
    add_force_join_channel(db_session, channel_id="-100123456789", title="Test Channel")
    assert toggle_force_join_channel(db_session, "-100123456789") is True
    channel = list_force_join_channels(db_session, active_only=False)[0]
    assert channel.is_active is False
    assert toggle_force_join_channel(db_session, "-100123456789") is True
    channel = list_force_join_channels(db_session, active_only=False)[0]
    assert channel.is_active is True
    assert toggle_force_join_channel(db_session, "-100missing") is False


@pytest.mark.asyncio
async def test_payment_wallet_wizard_input_validation() -> None:
    """Invalid wallet value must NOT be saved; only validated values persist."""
    from unittest.mock import patch

    from app.admin.handlers.vip import process_wallet_value_input

    VALID_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    VALID_BEP20 = "0x55d398326f99059fF775485246999027B3197955"

    message = MagicMock(spec=Message)
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    message.from_user = TelegramUser(id=999, is_bot=False, first_name="Admin")
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={"wallet_field": "trc20_address"})
    session = MagicMock()

    # Bogus TRC20 value → rejected, nothing saved, FSM kept for retry.
    message.text = "TRC20address"
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_not_called()
    state.clear.assert_not_called()
    message.reply.assert_awaited()
    reject_msg = message.reply.await_args.args[0]
    assert "invalid" in reject_msg.lower()

    # Empty value → rejected.
    message.text = ""
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_not_called()
    state.clear.assert_not_called()

    # Valid TRC20 → saved for exactly that field and FSM cleared.
    message.reply.reset_mock()
    message.text = VALID_TRC20
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_called_once_with(session, trc20_address=VALID_TRC20)
    state.clear.assert_awaited_once()

    # Same wizard for BEP20: invalid → rejected, valid → saved.
    state.get_data = AsyncMock(return_value={"wallet_field": "bep20_address"})
    state.clear.reset_mock()
    message.text = "not-a-bep20"
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_not_called()

    message.text = VALID_BEP20
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_called_once_with(session, bep20_address=VALID_BEP20)
    state.clear.assert_awaited_once()

    # Binance UID wizard: non-numeric → rejected.
    state.get_data = AsyncMock(return_value={"wallet_field": "binance_id"})
    state.clear.reset_mock()
    message.text = "abc123"
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_not_called()

    message.text = "12345678"
    with patch(
        "app.admin.handlers.vip.update_payment_settings"
    ) as update_settings:
        await process_wallet_value_input(message, state, session)
    update_settings.assert_called_once_with(session, binance_id="12345678")


def test_auto_payment_order_lifecycle(db_session) -> None:
    """Auto orders are created as a pair, one activation cancels the sibling."""
    u = upsert_user(db_session, 222333, "auto_buyer")
    plan = add_vip_plan(db_session, "Auto 1 Month", months=1, price=10.0)

    orders = create_auto_payment_orders(
        db_session,
        user_id=u.id,
        plan_id=plan.id,
        amount=10.0,
        currency="USD",
        trc20_wallet="T_WALLET",
        bep20_wallet="B_WALLET",
        trc20_amount=10.148,
        bep20_amount=10.231,
        order_hours=2,
    )
    assert len(orders) == 2
    assert {o.network for o in orders} == {"trc20", "bep20"}
    assert orders[0].payment_method == "trc20"
    assert orders[1].payment_method == "bep20"
    assert orders[0].wallet_address == "T_WALLET"
    assert orders[1].wallet_address == "B_WALLET"
    assert orders[0].expected_amount == 10.148
    assert orders[1].expected_amount == 10.231
    assert orders[0].order_code != orders[1].order_code
    assert len(orders[0].order_code) == 8
    assert all(o.status == "pending" for o in orders)
    assert all(o.expires_at > datetime.now(UTC).replace(tzinfo=None) for o in orders)

    sub = activate_vip_subscription_flow(db_session, orders[0].id)
    assert sub is not None
    db_session.refresh(orders[0])
    assert orders[0].status == "paid"
    db_session.refresh(u)
    assert u.is_vip is True

    cancelled = cancel_sibling_auto_orders(db_session, orders[0])
    assert cancelled == 1
    db_session.refresh(orders[1])
    assert orders[1].status == "cancelled"


def test_expire_auto_payments(db_session) -> None:
    """Expired auto orders are cancelled by expire_auto_payments."""
    u = upsert_user(db_session, 333444, "expire_buyer")
    plan = add_vip_plan(db_session, "Expire 1 Month", months=1, price=10.0)

    orders = create_auto_payment_orders(
        db_session,
        user_id=u.id,
        plan_id=plan.id,
        amount=10.0,
        trc20_wallet="T_WALLET",
        bep20_wallet="B_WALLET",
        order_hours=0,
    )
    assert all(o.status == "pending" for o in orders)

    expired = expire_auto_payments(db_session)
    assert expired == 2
    for o in orders:
        db_session.refresh(o)
        assert o.status == "cancelled"


def test_is_transaction_used(db_session) -> None:
    """A tx hash is used only when a paid payment references it."""
    u = upsert_user(db_session, 444555, "tx_buyer")
    plan = add_vip_plan(db_session, "TX 1 Month", months=1, price=10.0)

    payment = create_payment_order(
        db_session,
        user_id=u.id,
        plan_id=plan.id,
        amount=10.0,
        payment_method="trc20",
        transaction_id="TX-UNIQUE-HASH",
    )
    assert is_transaction_used(db_session, "TX-UNIQUE-HASH") is False

    activate_vip_subscription_flow(db_session, payment.id)
    assert is_transaction_used(db_session, "TX-UNIQUE-HASH") is True
    assert is_transaction_used(db_session, "TX-OTHER-HASH") is False
