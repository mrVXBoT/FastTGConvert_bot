"""tests/test_payment_auto.py — Unit tests for the automatic crypto payment detection service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base, Payment, User, UserVIPSubscription
from app.db.repositories import (
    add_vip_plan,
    create_auto_payment_orders,
    create_payment_order,
    expire_auto_payments,
    list_pending_auto_payments,
    upsert_user,
)
from app.services.payments import (
    USDT_TRC20_CONTRACT,
    check_bep20_payment,
    check_pending_auto_payments,
    check_trc20_payment,
    generate_expected_amount,
)

TEST_SETTINGS = Settings(bot_token="x" * 20, payment_expiry_grace_seconds=0)


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield session_factory
    engine.dispose()


def build_matching_http_get(
    wallet_map: dict[str, Payment], tx_hash: str = "TX_AUTO_HASH"
):
    """Return an async http_get fake that matches each wallet's expected amount."""

    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        if "trongrid" in url:
            wallet = url.split("/accounts/")[1].split("/")[0]
            payment = wallet_map[wallet.upper()]
            units = round(payment.expected_amount * 1_000_000)
            return {
                "success": True,
                "data": [
                    {
                        "transaction_id": tx_hash,
                        "type": "Transfer",
                        "to": payment.wallet_address,
                        "value": str(units),
                        "token_info": {"address": USDT_TRC20_CONTRACT},
                    }
                ],
            }
        payment = wallet_map[params["address"].lower()]
        units = round(payment.expected_amount * 10**18)
        return {
            "status": "1",
            "message": "OK",
            "result": [
                {"hash": tx_hash, "to": payment.wallet_address, "value": str(units)}
            ],
        }

    return fake_http_get


def build_trc20_only_http_get(wallet_map: dict[str, Payment]):
    """Return an async http_get fake that only matches TRC20 transfers."""

    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        if "trongrid" not in url:
            return {"status": "1", "message": "OK", "result": []}
        wallet = url.split("/accounts/")[1].split("/")[0]
        payment = wallet_map[wallet.upper()]
        units = round(payment.expected_amount * 1_000_000)
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_TRC20_HASH",
                    "type": "Transfer",
                    "to": payment.wallet_address,
                    "value": str(units),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                }
            ],
        }

    return fake_http_get


def build_wallet_map(session) -> dict[str, Payment]:
    wallet_map: dict[str, Payment] = {}
    for payment in list_pending_auto_payments(session):
        wallet_map[payment.wallet_address.upper()] = payment
        wallet_map[payment.wallet_address.lower()] = payment
    return wallet_map


def test_generate_expected_amount_unique_and_bounded() -> None:
    base = 10.148
    used: set[float] = set()
    amounts = []
    for _ in range(20):
        amount = generate_expected_amount(base, used)
        amounts.append(amount)
        used.add(amount)
    for amount in amounts:
        assert base + 0.001 <= amount <= base + 0.999
        assert round(amount, 3) == amount
    for i, left in enumerate(amounts):
        for right in amounts[i + 1 :]:
            assert abs(left - right) >= 0.001


@pytest.mark.asyncio
async def test_check_trc20_found() -> None:
    expected_units = round(10.148 * 1_000_000)

    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TRX_TX_1",
                    "type": "Transfer",
                    "to": "TWALLET01",
                    "value": str(expected_units),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                }
            ],
        }

    assert await check_trc20_payment(fake_http_get, "twallet01", 10.148, 0) == "TRX_TX_1"


@pytest.mark.asyncio
async def test_check_trc20_ignores_wrong_amount_wrong_recipient_other_token() -> None:
    expected_units = round(10.148 * 1_000_000)

    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_BAD_VALUE",
                    "type": "Transfer",
                    "to": "TWALLET01",
                    "value": str(expected_units + 1),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                },
                {
                    "transaction_id": "TX_BAD_TO",
                    "type": "Transfer",
                    "to": "TOTHERTR",
                    "value": str(expected_units),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                },
                {
                    "transaction_id": "TX_BAD_TOKEN",
                    "type": "Transfer",
                    "to": "TWALLET01",
                    "value": str(expected_units),
                    "token_info": {"address": "TOTHERTOKEN"},
                },
            ],
        }

    assert await check_trc20_payment(fake_http_get, "TWALLET01", 10.148, 0) is None


@pytest.mark.asyncio
async def test_check_trc20_ignores_unconfirmed() -> None:
    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        return {"success": False, "data": []}

    assert await check_trc20_payment(fake_http_get, "TWALLET01", 10.148, 0) is None


@pytest.mark.asyncio
async def test_check_bep20_found_and_rate_limited() -> None:
    expected_units = round(10.148 * 10**18)

    async def fake_ok(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "status": "1",
            "message": "OK",
            "result": [
                {"hash": "BSC_TX_1", "to": "0xwallet01", "value": str(expected_units)}
            ],
        }

    assert await check_bep20_payment(fake_ok, "0xWALLET01", 10.148) == "BSC_TX_1"

    async def fake_notok(url: str, params: dict | None = None, headers: dict | None = None):
        return {"status": "0", "message": "NOTOK"}

    assert await check_bep20_payment(fake_notok, "0xwallet01", 10.148) is None

    async def fake_limited(url: str, params: dict | None = None, headers: dict | None = None):
        return {"status": "0", "message": "Max rate limit reached"}

    assert await check_bep20_payment(fake_limited, "0xwallet01", 10.148) is None


@pytest.mark.asyncio
async def test_check_trc20_unconfirmed_transaction_not_matched() -> None:
    expected_units = round(10.148 * 1_000_000)

    async def fake_http_get(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_UNCONFIRMED",
                    "type": "Incoming",
                    "to": "TWALLET01",
                    "value": str(expected_units),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                }
            ],
        }

    assert await check_trc20_payment(fake_http_get, "TWALLET01", 10.148, 0) is None


@pytest.mark.asyncio
async def test_polling_activates_vip_on_detected_payment(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 700001, "autobuyer")
        plan = add_vip_plan(session, "Auto Test Plan", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRC20WALLET",
            bep20_wallet="0xBEP20WALLET",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        wallet_map = build_wallet_map(session)

    bot = AsyncMock()
    http_get = build_trc20_only_http_get(wallet_map)
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        result = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )
    assert result == {"checked": 2, "paid": 1}
    assert bot.send_message.await_count == 1

    with db_factory() as session:
        payments = list(session.scalars(select(Payment)).all())
        trc = next(p for p in payments if p.network == "trc20")
        bep = next(p for p in payments if p.network == "bep20")
        assert trc.status == "paid"
        assert trc.transaction_id == "TX_TRC20_HASH"
        assert bep.status == "cancelled"
        assert bep.transaction_id is None
        user_db = session.scalar(select(User).where(User.id == trc.user_id))
        assert user_db is not None
        assert user_db.is_vip is True


@pytest.mark.asyncio
async def test_polling_skips_expired_orders(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 700002, "latepay")
        plan = add_vip_plan(session, "Auto Test Plan", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_amount=10.148,
            bep20_amount=10.231,
            order_hours=0,
        )

    bot = AsyncMock()
    result = await check_pending_auto_payments(
        db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
    )
    assert result["paid"] == 0

    with db_factory() as session:
        payments = list(session.scalars(select(Payment)).all())
        assert all(p.status == "pending" for p in payments)
        assert expire_auto_payments(session) == 2
    with db_factory() as session:
        payments = list(session.scalars(select(Payment)).all())
        assert all(p.status == "cancelled" for p in payments)


@pytest.mark.asyncio
async def test_polling_ignores_reused_transaction(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 700004, "reuser")
        plan_a = add_vip_plan(session, "Plan A", 1, 10.0)
        plan_b = add_vip_plan(session, "Plan B", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan_a.id,
            amount=10.0,
            trc20_wallet="TTRC_A1",
            bep20_wallet="0xBEP_A1",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan_b.id,
            amount=10.0,
            trc20_wallet="TTRC_B1",
            bep20_wallet="0xBEP_B1",
            trc20_amount=11.333,
            bep20_amount=11.444,
        )
        wallet_map = build_wallet_map(session)

    bot = AsyncMock()
    http_get = build_matching_http_get(wallet_map, tx_hash="TX_SHARED_HASH")
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        result = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )
    assert result["paid"] == 1

    with db_factory() as session:
        payments = list(session.scalars(select(Payment)).all())
        paid = [p for p in payments if p.status == "paid"]
        assert len(paid) == 1
        assert paid[0].transaction_id == "TX_SHARED_HASH"
        pending = [
            p for p in payments if p.status == "pending" and p.plan_id == plan_b.id
        ]
        assert len(pending) >= 1
        assert all(p.transaction_id is None for p in pending)


@pytest.mark.asyncio
async def test_polling_skips_payments_without_expected_amount(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 700003, "noamount")
        plan = add_vip_plan(session, "Auto Test Plan", 1, 10.0)
        payment = create_payment_order(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            payment_method="trc20",
        )
        payment.network = "trc20"
        payment.wallet_address = "TNOAMOUNTWALLET"
        payment.expires_at = None
        session.commit()

    bot = AsyncMock()
    result = await check_pending_auto_payments(
        db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
    )
    assert result == {"checked": 1, "paid": 0}
    assert bot.send_message.await_count == 0

    with db_factory() as session:
        payment = session.scalar(select(Payment))
        assert payment.status == "pending"
        assert payment.transaction_id is None


@pytest.mark.asyncio
async def test_repeated_scan_never_double_activates(db_factory) -> None:
    """Scanning twice (e.g. polling loop + Check Payment) must not extend VIP twice."""
    with db_factory() as session:
        user = upsert_user(session, 700005, "twicechk")
        plan = add_vip_plan(session, "Twice Plan", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRC_ONCE",
            bep20_wallet="0xBEP_ONCE",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        wallet_map = build_wallet_map(session)

    bot = AsyncMock()
    http_get = build_trc20_only_http_get(wallet_map)
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        first = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )
        second = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )
    assert first["paid"] == 1
    assert second["paid"] == 0
    assert bot.send_message.await_count == 1

    with db_factory() as session:
        payments = list(session.scalars(select(Payment)).all())
        assert len([p for p in payments if p.status == "paid"]) == 1
        subs = list(session.scalars(select(UserVIPSubscription)).all())
        assert len(subs) == 1
        user_db = session.scalar(select(User).where(User.id == subs[0].user_id))
        assert user_db is not None
        assert user_db.is_vip is True
        assert user_db.vip_expires_at is not None
