"""tests/test_admin_panel.py — Comprehensive unit tests for Payments, VIP Subscriptions, Worker Broadcast, RBAC & User Ban Middleware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message
from aiogram.types import User as TelegramUser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base
from app.db.repositories import (
    activate_vip_subscription_flow,
    add_admin_user,
    add_vip_plan,
    create_payment_order,
    get_admin_role,
    get_dashboard_statistics,
    grant_user_vip,
    list_pending_payments,
    list_vip_plans,
    reject_payment,
    set_user_ban_status,
    toggle_feature_access_level,
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
