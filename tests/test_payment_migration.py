"""tests/test_payment_migration.py — Migration-path and concurrency tests for auto crypto payments.

Deterministic only: no real network access. Every chain call goes through a
monkeypatched `fetch_json` / plain async `http_get` fake.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import LATEST_VERSION, MIGRATIONS, run_migrations
from app.db.models import Base, Payment, User, UserVIPSubscription
from app.db.repositories import add_vip_plan, create_auto_payment_orders, upsert_user
from app.services.payments import (
    USDT_TRC20_CONTRACT,
    amount_to_units,
    check_bep20_payment,
    check_pending_auto_payments,
)

UTC = timezone.utc  # noqa: UP017

TEST_SETTINGS = Settings(bot_token="x" * 20, payment_expiry_grace_seconds=0)
GRACE_SETTINGS = Settings(bot_token="x" * 20, payment_expiry_grace_seconds=120)

BEP20_UNITS_10_148 = amount_to_units(10.148, 18)


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield session_factory
    engine.dispose()


def build_v8_db_and_migrate():
    """Build a DB upgraded only to version 8 (no v9 index) and return its engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    connection = engine.raw_connection()
    cursor = connection.cursor()
    for version in range(1, 9):
        cursor.execute("BEGIN TRANSACTION")
        MIGRATIONS[version](cursor)
        cursor.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    connection.close()
    return engine


@pytest.fixture
def v8_db():
    engine = build_v8_db_and_migrate()
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield session_factory, engine
    engine.dispose()


def make_v8_order(session, user, plan, status="pending", **kwargs):
    if status != "pending":
        kwargs["status"] = status
    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        amount=10.0,
        payment_method="crypto",
        status=kwargs.pop("status", "pending"),
        **kwargs,
    )
    session.add(payment)
    return payment


def trc_only_matching_fetch(trc_wallet: str, expected: float, tx_hash: str):
    """Return an http_get fake that matches ONLY the trc20 wallet, never BEP20."""

    async def fake(url, params=None, headers=None):
        if "trongrid" in url:
            units = amount_to_units(expected, 6)
            return {
                "success": True,
                "data": [
                    {
                        "transaction_id": tx_hash,
                        "type": "Transfer",
                        "to": trc_wallet,
                        "value": str(units),
                        "token_info": {"address": USDT_TRC20_CONTRACT},
                    }
                ],
            }
        return {"status": "1", "message": "OK", "result": []}

    return fake


def seed_expired_order(session_factory, telegram_id: int) -> User:
    with session_factory() as session:
        user = upsert_user(session, telegram_id, "latepay")
        plan = add_vip_plan(session, "GracePlan", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TGRACELATE",
            bep20_wallet="0xBGRACELATE",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        for payment in session.scalars(select(Payment)).all():
            payment.expires_at = datetime.now(UTC) - timedelta(seconds=30)
        session.commit()
        return user


# ============================================================
# 1. Migration upgrade path v8 -> v9
# ============================================================

async def test_v9_migration_deduplicates_colliding_pending_orders(v8_db) -> None:
    session_factory, engine = v8_db

    with session_factory() as session:
        user = upsert_user(session, 720001, "migrator")
        plan = add_vip_plan(session, "MigrPlan", 1, 10.0)

        # (a) two LIVE pending colliding on the exact same (wallet, network, amount)
        # (a) two LIVE pending colliding on the exact same (wallet, network, amount)
        oldest = make_v8_order(
            session, user, plan,
            network="trc20", wallet_address="TCOL001", expected_amount=10.5,
        )
        newest = make_v8_order(
            session, user, plan,
            network="trc20", wallet_address="TCOL001", expected_amount=10.5,
        )
        # (b) a manual pending order (network NULL)
        manual = make_v8_order(session, user, plan)
        # (c) an already paid auto order (same triple — must stay paid)
        paid = make_v8_order(
            session, user, plan,
            status="paid",
            network="trc20", wallet_address="TCOL001", expected_amount=10.5,
        )
        # (d) a cancelled auto order with a higher id (same triple — must stay cancelled)
        cancelled = make_v8_order(
            session, user, plan,
            status="cancelled",
            network="trc20", wallet_address="TCOL001", expected_amount=10.5,
        )
        session.commit()
        oldest_id, newest_id = oldest.id, newest.id
        manual_id, paid_id, cancelled_id = manual.id, paid.id, cancelled.id

    run_migrations(engine)

    with session_factory() as session:
        rows = {p.id: p for p in session.scalars(select(Payment)).all()}

        # Only the oldest of the colliding pair stays pending; everyone else
        # in that group becomes cancelled. paid/cancelled/manual are untouched.
        assert rows[oldest_id].status == "pending"
        assert rows[newest_id].status == "cancelled"
        assert rows[manual_id].status == "pending"
        assert rows[paid_id].status == "paid"
        assert rows[cancelled_id].status == "cancelled"

        live = [
            p
            for p in rows.values()
            if p.status == "pending"
            and p.network == "trc20"
            and p.wallet_address == "TCOL001"
            and p.expected_amount == 10.5
        ]
        assert [p.id for p in live] == [oldest_id]

        index_name = session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='ux_payments_pending_auto_amount'"
            )
        ).scalar()
        assert index_name == "ux_payments_pending_auto_amount"

        # A new pending order with the SAME (wallet, network, amount) must raise.
        make_v8_order(
            session, user, plan,
            status="pending",
            network="trc20", wallet_address="TCOL001", expected_amount=10.5,
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Repeated pending orders with a NULL "manual" triple are still allowed.
        m1 = make_v8_order(session, user, plan)  # network/wallet/amount all NULL
        m2 = make_v8_order(session, user, plan)  # network/wallet/amount all NULL
        session.commit()
        assert m1.id is not None
        assert m2.id is not None


# ============================================================
# 2. Fresh-DB migrations end at user_version == LATEST_VERSION
# ============================================================

async def test_run_migrations_fresh_db_ends_at_latest_version() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    connection = engine.raw_connection()
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()
    assert version == LATEST_VERSION == 10
    engine.dispose()


# ============================================================
# 3. Allocation stress — amounts stay unique under load
# ============================================================

async def test_sequential_auto_orders_never_alias_amounts(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 720003, "stressy")
        plan = add_vip_plan(session, "Stress", 1, 10.0)
        user_id, plan_id = user.id, plan.id
        for _ in range(100):
            create_auto_payment_orders(
                session,
                user_id=user_id,
                plan_id=plan_id,
                amount=10.0,
                trc20_wallet="TSTRESS1",
                bep20_wallet="0xBSTRESS1",
                trc20_amount=10.148,
                bep20_amount=10.231,
            )

    with db_factory() as session:
        rows = list(
            session.scalars(select(Payment).where(Payment.user_id == user_id)).all()
        )
        assert len(rows) == 200
        assert all(p.status == "pending" for p in rows)

        by_key: dict[tuple[str, str], list[float]] = {}
        for p in rows:
            by_key.setdefault((p.wallet_address, p.network), []).append(
                p.expected_amount
            )
        for key, amounts in by_key.items():
            assert len(amounts) == len(set(amounts)), key


# ============================================================
# 4. E2E grace boundary — a late transfer inside grace claims
# ============================================================

async def test_grace_window_claims_past_expiry_transfer(db_factory) -> None:
    user = seed_expired_order(db_factory, 720004)

    bot = AsyncMock()
    http_get = trc_only_matching_fetch("TGRACELATE", 10.148, "HASH_LATE_XX")
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        result = await check_pending_auto_payments(
            db_factory, bot, GRACE_SETTINGS, only_user_id=user.telegram_id
        )

    assert result == {"checked": 2, "paid": 1}
    assert bot.send_message.await_count == 1

    with db_factory() as session:
        paid = session.scalar(
            select(Payment).where(Payment.transaction_id == "HASH_LATE_XX")
        )
        assert paid is not None
        assert paid.status == "paid"
        sub = session.scalar(select(UserVIPSubscription))
        assert sub is not None
        assert sub.status == "active"
        user_db = session.scalar(select(User).where(User.id == user.id))
        assert user_db is not None
        assert user_db.is_vip is True


async def test_grace_zero_skips_expired_transfer(db_factory) -> None:
    user = seed_expired_order(db_factory, 720005)

    bot = AsyncMock()
    http_get = trc_only_matching_fetch("TGRACELATE", 10.148, "HASH_LATE_XX")
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        result = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )

    assert result == {"checked": 2, "paid": 0}
    assert bot.send_message.await_count == 0

    with db_factory() as session:
        assert (
            session.scalar(select(UserVIPSubscription)) is None
        )
        user_db = session.scalar(select(User).where(User.id == user.id))
        assert user_db is not None
        assert user_db.is_vip is False


# ============================================================
# 5. BEP20 time-window guard
# ============================================================

def bep20_ok(result: list[dict]):
    async def fake(url: str, params: dict | None = None, headers: dict | None = None):
        return {"status": "1", "message": "OK", "result": result}

    return fake


async def test_bep20_missing_timestamp_still_matches() -> None:
    tx = {"hash": "BSC_LATE", "to": "0xWALLET01", "value": str(BEP20_UNITS_10_148)}
    fake = bep20_ok([tx])
    assert (
        await check_bep20_payment(fake, "0xWALLET01", 10.148, since_ms=1_750_000_000_000)
        == "BSC_LATE"
    )


async def test_bep20_future_timestamp_matches() -> None:
    tx = {
        "hash": "BSC_FUTURE",
        "to": "0xWALLET01",
        "value": str(BEP20_UNITS_10_148),
        "timeStamp": "2000000000",
    }
    fake = bep20_ok([tx])
    assert (
        await check_bep20_payment(fake, "0xWALLET01", 10.148, since_ms=1_750_000_000_000)
        == "BSC_FUTURE"
    )


async def test_bep20_past_timestamp_before_order_skipped() -> None:
    tx = {
        "hash": "BSC_OLD",
        "to": "0xWALLET01",
        "value": str(BEP20_UNITS_10_148),
        "timeStamp": "1700000000",  # before the order creation window
    }
    fake = bep20_ok([tx])
    assert (
        await check_bep20_payment(fake, "0xWALLET01", 10.148, since_ms=1_750_000_000_000)
        is None
    )


# ============================================================
# 6. _SCAN_LOCK serialization — one claim, one notification
# ============================================================

async def test_scan_lock_serializes_concurrent_claims(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 720006, "locky")
        plan = add_vip_plan(session, "LockPlan", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TLOCK1",
            bep20_wallet="0xBLOCK1",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )

    calls: list[str] = []

    async def slow_fetch(url, params=None, headers=None):
        calls.append(url)
        await asyncio.sleep(0.05)
        if "trongrid" in url:
            units = amount_to_units(10.148, 6)
            return {
                "success": True,
                "data": [
                    {
                        "transaction_id": "TX_LOCKED",
                        "type": "Transfer",
                        "to": "TLOCK1",
                        "value": str(units),
                        "token_info": {"address": USDT_TRC20_CONTRACT},
                    }
                ],
            }
        return {"status": "1", "message": "OK", "result": []}

    bot = AsyncMock()
    with patch("app.services.payments.fetch_json", side_effect=slow_fetch):
        first, second = await asyncio.gather(
            check_pending_auto_payments(db_factory, bot, TEST_SETTINGS),
            check_pending_auto_payments(db_factory, bot, TEST_SETTINGS),
        )

    assert first == {"checked": 2, "paid": 1}
    assert second == {"checked": 0, "paid": 0}
    assert bot.send_message.await_count == 1

    with db_factory() as session:
        subs = list(session.scalars(select(UserVIPSubscription)).all())
        assert len(subs) == 1
        assert subs[0].status == "active"
        paid = list(
            session.scalars(select(Payment).where(Payment.status == "paid")).all()
        )
        assert len(paid) == 1