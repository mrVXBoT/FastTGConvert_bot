"""tests/test_vip_flow.py — Unit tests for the user-side VIP buy flow (manual + auto payment)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base, Payment, User
from app.db.repositories import add_vip_plan, update_payment_settings
from app.handlers.vip import (
    UserVIPState,
    callback_auto_check,
    callback_auto_payment,
    callback_buy_plan,
    callback_manual_payment,
    process_user_receipt_submission,
)

TEST_SETTINGS = Settings(bot_token="x" * 20, admin_id=0)


@pytest.fixture
def sf():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory


@pytest.fixture
def settings():
    return TEST_SETTINGS


def make_state() -> FSMContext:
    storage = MemoryStorage()
    key = MagicMock()
    return FSMContext(storage, key)


def make_query(data: str = "") -> CallbackQuery:
    query = AsyncMock(spec=CallbackQuery)
    query.data = data
    query.from_user = SimpleNamespace(id=123, username="u")
    query.message = AsyncMock(spec=Message)
    query.message.edit_text = AsyncMock()
    query.bot = AsyncMock()
    query.answer = AsyncMock()
    return query


def button_callbacks(query: CallbackQuery) -> list[str]:
    markup = query.message.edit_text.await_args.kwargs["reply_markup"]
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


async def test_buy_plan_renders_both_payment_methods(sf) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=9.99)
        update_payment_settings(
            session,
            trc20_address="TRC20WALLET",
            auto_trc20_address="TTRONWALLET",
            auto_bep20_address="0xBEP20",
            auto_enabled=True,
        )

    query = make_query(f"buy_plan:{plan.id}")
    state = make_state()

    await callback_buy_plan(query, state, session_factory=sf)

    text = query.message.edit_text.await_args.args[0]
    assert "Pro 1 Month" in text
    data = button_callbacks(query)
    assert "pay_method:manual" in data
    assert "pay_method:auto" in data
    assert await state.get_state() == UserVIPState.waiting_payment_method


async def test_buy_plan_with_auto_disabled_hides_auto_button(sf) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=9.99)
        update_payment_settings(
            session,
            trc20_address="TRC20WALLET",
            auto_trc20_address="TTRONWALLET",
            auto_bep20_address="0xBEP20",
            auto_enabled=False,
        )

    query = make_query(f"buy_plan:{plan.id}")
    state = make_state()

    await callback_buy_plan(query, state, session_factory=sf)

    data = button_callbacks(query)
    assert "pay_method:manual" in data
    assert "pay_method:auto" not in data


async def test_manual_payment_shows_wallet_details(sf) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=19.99)
        update_payment_settings(
            session,
            binance_id="BINANCE123",
            trc20_address="TRC20WALLET",
            bep20_address="BEP20WALLET",
        )

    state = make_state()
    await state.update_data(plan_id=plan.id, amount=plan.price)
    await state.set_state(UserVIPState.waiting_for_receipt)

    query = make_query("pay_method:manual")
    await callback_manual_payment(query, state, session_factory=sf)

    text = query.message.edit_text.await_args.args[0]
    assert "BINANCE123" in text
    assert "TRC20WALLET" in text
    assert "BEP20WALLET" in text
    assert "pay:manual_screenshot" in button_callbacks(query)
    assert await state.get_state() == UserVIPState.waiting_for_receipt


async def test_receipt_text_rejected_keeps_state(sf) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=9.99)

    state = make_state()
    await state.update_data(plan_id=plan.id, amount=9.99)
    await state.set_state(UserVIPState.waiting_for_receipt)

    message = AsyncMock(spec=Message)
    message.photo = None
    message.from_user = SimpleNamespace(id=123, username="u")
    message.reply = AsyncMock()

    await process_user_receipt_submission(message, state, TEST_SETTINGS, session_factory=sf)

    message.reply.assert_awaited()
    assert await state.get_state() == UserVIPState.waiting_for_receipt
    data = await state.get_data()
    assert data.get("plan_id") == plan.id


async def test_receipt_photo_creates_pending_manual_order(sf) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=9.99)

    state = make_state()
    await state.update_data(plan_id=plan.id, amount=plan.price)
    await state.set_state(UserVIPState.waiting_for_receipt)

    message = AsyncMock(spec=Message)
    message.photo = [SimpleNamespace(file_id="FILE1")]
    message.from_user = SimpleNamespace(id=123, username="u")
    message.reply = AsyncMock()

    await process_user_receipt_submission(
        message, state, TEST_SETTINGS, session_factory=sf
    )

    with sf() as session:
        payment = session.scalar(
            select(Payment).where(Payment.receipt_file_id == "FILE1")
        )
        assert payment is not None
        assert payment.payment_method == "manual"
        assert payment.status == "pending"
        assert payment.transaction_id is None

    assert await state.get_state() is None


async def test_auto_payment_creates_two_orders_and_renders(sf, settings) -> None:
    with sf() as session:
        plan = add_vip_plan(session, "Pro 1 Month", months=1, price=9.99)
        update_payment_settings(
            session,
            auto_trc20_address="TAUTO_WALLET",
            auto_bep20_address="BEAUTO_WALLET",
            auto_enabled=True,
        )

    state = make_state()
    await state.update_data(plan_id=plan.id, amount=plan.price)

    query = make_query("pay_method:auto")
    await callback_auto_payment(query, state, settings, session_factory=sf)

    with sf() as session:
        user = session.scalar(select(User).where(User.telegram_id == 123))
        assert user is not None
        orders = list(session.scalars(select(Payment).where(Payment.user_id == user.id)).all())
        assert len(orders) == 2
        assert {o.network for o in orders} == {"trc20", "bep20"}
        codes = [o.order_code for o in orders]
        assert len(set(codes)) == 2

    text = query.message.edit_text.await_args.args[0]
    assert codes[0] in text
    assert codes[1] in text
    assert await state.get_state() == UserVIPState.waiting_payment_method


async def test_auto_check_not_detected_alerts(sf, settings) -> None:
    query = make_query("pay:auto_check")
    state = make_state()

    with patch(
        "app.handlers.vip.check_pending_auto_payments",
        AsyncMock(return_value={"checked": 1, "paid": 0}),
    ):
        await callback_auto_check(query, state, settings, session_factory=sf)

    calls = query.answer.await_args_list
    assert len(calls) >= 1
    assert calls[-1].kwargs.get("show_alert") is True


async def test_auto_check_detected_confirms_and_clears(sf, settings) -> None:
    query = make_query("pay:auto_check")
    state = make_state()

    with patch(
        "app.handlers.vip.check_pending_auto_payments",
        AsyncMock(return_value={"checked": 1, "paid": 1}),
    ):
        await callback_auto_check(query, state, settings, session_factory=sf)

    assert await state.get_state() is None
    query.message.edit_text.assert_awaited()