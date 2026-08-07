"""tests/test_payment_security.py — Security and edge-case tests for the auto crypto payment pipeline.

Deterministic only: no real network access anywhere. Every chain call goes through a
monkeypatched `fetch_json` / plain async `http_get` fake that returns crafted payloads.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.migration import run_migrations
from app.db.models import Base, Payment, User, UserVIPSubscription
from app.db.repositories import (
    activate_vip_subscription_flow,
    add_vip_plan,
    create_auto_payment_orders,
    create_payment_order,
    expire_auto_payments,
    generate_unique_order_code,
    list_pending_auto_payments,
    upsert_user,
)
from app.services.payments import (
    USDT_TRC20_CONTRACT,
    amount_to_units,
    check_bep20_payment,
    check_pending_auto_payments,
    check_trc20_payment,
    generate_expected_amount,
)

UTC = timezone.utc  # noqa: UP017

TEST_SETTINGS = Settings(bot_token="x" * 20, payment_expiry_grace_seconds=0)

TRC20_UNITS_10_148 = amount_to_units(10.148, 6)
BEP20_UNITS_10_148 = amount_to_units(10.148, 18)


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield session_factory
    engine.dispose()


# ============================================================
# A. Numeric exactness — the precision bug class
# ============================================================

async def test_amount_to_units_trc20_6_decimals() -> None:
    assert amount_to_units(10.148, 6) == 10_148_000


async def test_amount_to_units_bep20_18_decimals() -> None:
    assert amount_to_units(10.148, 18) == 10_148_000_000_000_000_000


async def test_amount_to_units_large_18_decimals_exact() -> None:
    # round(999999.999 * 10**18) → 999999998999999981944832 (precision loss).
    # The decimal-string implementation must be exact.
    assert amount_to_units(999999.999, 18) == 999_999_999_000_000_000_000_000


async def test_amount_to_units_million_18_decimals_exact() -> None:
    assert amount_to_units(1000000.0, 18) == 1_000_000_000_000_000_000_000_000


# ============================================================
# B. TRC20 verification edge cases
# ============================================================

def make_trc20_get(entries: list[dict], success: bool = True):
    async def fake_http_get(
        url: str, params: dict | None = None, headers: dict | None = None
    ):
        return {"success": success, "data": entries}

    return fake_http_get


async def test_trc20_matches_exact_fee_case_insensitive() -> None:
    async def fake_http_get(
        url: str, params: dict | None = None, headers: dict | None = None
    ):
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_OK",
                    "type": "Transfer",
                    # wallet requested as lowercase; response `to` is uppercase.
                    "to": "TWALLET01",
                    "value": str(TRC20_UNITS_10_148),
                    # contract returned in lowercase; verification is case-insensitive.
                    "token_info": {"address": USDT_TRC20_CONTRACT.lower()},
                }
            ],
        }

    assert (
        await check_trc20_payment(fake_http_get, "twallet01", 10.148, 0) == "TX_OK"
    )


async def test_trc20_rejects_non_transfer_type() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_INCOMING",
                "type": "Incoming",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148),
                "token_info": {"address": USDT_TRC20_CONTRACT},
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_rejects_wrong_token_contract() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_WRONG_TOKEN",
                "type": "Transfer",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148),
                "token_info": {"address": "TQRETHconfirmx8q8ZY4pL8otSzgjLj6t"},
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_rejects_wrong_to() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_WRONG_TO",
                "type": "Transfer",
                "to": "TOTHERRECEIVER",
                "value": str(TRC20_UNITS_10_148),
                "token_info": {"address": USDT_TRC20_CONTRACT},
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_rejects_overpay_by_one_unit() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_OVERPAY",
                "type": "Transfer",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148 + 1),
                "token_info": {"address": USDT_TRC20_CONTRACT},
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_rejects_underpay_by_one_unit() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_UNDERPAY",
                "type": "Transfer",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148 - 1),
                "token_info": {"address": USDT_TRC20_CONTRACT},
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


@pytest.mark.parametrize(
    "value_payload",
    [
        {"omit": True},
        {"value": None},
        {"value": ""},
        {"value": "0x"},
        {"value": "abc"},
    ],
    ids=["missing", "none", "empty", "0x", "abc"],
)
async def test_trc20_bad_value_never_raises(value_payload: dict) -> None:
    entry: dict = {
        "transaction_id": "TX_BAD_VALUE",
        "type": "Transfer",
        "to": "TWALLET01",
        "token_info": {"address": USDT_TRC20_CONTRACT},
    }
    if value_payload.get("omit"):
        pass
    else:
        entry["value"] = value_payload["value"]
    fake = make_trc20_get([entry])
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_success_false_returns_none() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_UNCONFIRMED",
                "type": "Transfer",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148),
                "token_info": {"address": USDT_TRC20_CONTRACT},
            }
        ],
        success=False,
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


async def test_trc20_missing_data_key_returns_none() -> None:
    async def fake_http_get(
        url: str, params: dict | None = None, headers: dict | None = None
    ):
        return {"success": True}

    assert await check_trc20_payment(fake_http_get, "TWALLET01", 10.148, 0) is None


async def test_trc20_missing_token_info_returns_none() -> None:
    fake = make_trc20_get(
        [
            {
                "transaction_id": "TX_NO_TOKEN_INFO",
                "type": "Transfer",
                "to": "TWALLET01",
                "value": str(TRC20_UNITS_10_148),
            }
        ]
    )
    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) is None


# ============================================================
# C. BEP20 verification edge cases
# ============================================================

def bep20_get(response: dict):
    async def fake_http_get(
        url: str, params: dict | None = None, headers: dict | None = None
    ):
        return response

    return fake_http_get


async def test_bep20_matches_exact_amount() -> None:
    fake = bep20_get(
        {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "BSC_TX_1",
                    "to": "0xWALLET01",
                    "value": str(BEP20_UNITS_10_148),
                }
            ],
        }
    )
    assert await check_bep20_payment(fake, "0xwallet01", 10.148) == "BSC_TX_1"


async def test_bep20_rejects_wrong_to() -> None:
    fake = bep20_get(
        {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "BSC_TX_BAD_TO",
                    "to": "0xANOTHERWALLET",
                    "value": str(BEP20_UNITS_10_148),
                }
            ],
        }
    )
    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


async def test_bep20_rejects_overpay_by_one_unit() -> None:
    fake = bep20_get(
        {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "BSC_TX_OVER",
                    "to": "0xWALLET01",
                    "value": str(BEP20_UNITS_10_148 + 1),
                }
            ],
        }
    )
    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


async def test_bep20_rejects_underpay_by_one_unit() -> None:
    fake = bep20_get(
        {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "BSC_TX_UNDER",
                    "to": "0xWALLET01",
                    "value": str(BEP20_UNITS_10_148 - 1),
                }
            ],
        }
    )
    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


@pytest.mark.parametrize(
    "value_payload",
    [
        {"omit": True},
        {"value": None},
        {"value": ""},
        {"value": "0x"},
        {"value": "abc"},
    ],
    ids=["missing", "none", "empty", "0x", "abc"],
)
async def test_bep20_bad_value_never_raises(value_payload: dict) -> None:
    tx: dict = {"hash": "BSC_TX_BAD_VALUE", "to": "0xWALLET01"}
    if not value_payload.get("omit"):
        tx["value"] = value_payload["value"]
    fake = bep20_get({"status": "1", "message": "OK", "result": [tx]})
    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


async def test_bep20_status_not_one_returns_none() -> None:
    for status_value in ["0", "", "pending"]:
        fake = bep20_get({"status": status_value, "message": "NOTOK"})
        assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


@pytest.mark.parametrize(
    "result",
    [
        "No transactions found",
        {"message": "No transactions found"},
        None,
    ],
    ids=["plain-string", "dict", "missing"],
)
async def test_bep20_error_result_never_raises(result) -> None:
    payload: dict = {"status": "1", "message": "OK"}
    if result is not None:
        payload["result"] = result
    fake = bep20_get(payload)
    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) is None


async def test_bep20_large_amount_exact() -> None:
    large_units = amount_to_units(999999.999, 18)
    fake = bep20_get(
        {
            "status": "1",
            "message": "OK",
            "result": [
                {"hash": "BSC_TX_LARGE", "to": "0xWALLET01", "value": str(large_units)}
            ],
        }
    )
    assert await check_bep20_payment(fake, "0xWALLET01", 999999.999) == "BSC_TX_LARGE"


# ============================================================
# D. generate_expected_amount — 200-iteration uniqueness sweep
# ============================================================

async def test_generate_expected_amount_200_unique_bounded() -> None:
    random.seed(20260807)
    base = 10.148
    used: set[float] = set()
    candidates: list[float] = []
    for _ in range(200):
        candidate = generate_expected_amount(base, used)
        candidates.append(candidate)
        used.add(candidate)

    for candidate in candidates:
        assert base + 0.001 <= candidate <= base + 0.999
        assert candidate < base + 1.0
        assert round(candidate, 3) == candidate

    assert len(set(candidates)) == 200  # one shared "used" set → no duplicates

    thousandths = sorted(round(c * 1000) for c in candidates)
    for left, right in pairwise(thousandths):
        assert right - left >= 1  # monotone uniqueness at the 3-decimal grid


# ============================================================
# E. check_pending_auto_payments integration
# ============================================================

def build_wallet_map(session) -> dict[str, Payment]:
    wallet_map: dict[str, Payment] = {}
    for payment in list_pending_auto_payments(session):
        wallet_map[payment.wallet_address.upper()] = payment
        wallet_map[payment.wallet_address.lower()] = payment
    return wallet_map


def build_matching_http_get(wallet_map: dict[str, Payment], tx_hash: str):
    async def fake_http_get(
        url: str, params: dict | None = None, headers: dict | None = None
    ):
        if "trongrid" in url:
            wallet = url.split("/accounts/")[1].split("/")[0]
            payment = wallet_map[wallet.upper()]
            units = amount_to_units(payment.expected_amount, 6)
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
        units = amount_to_units(payment.expected_amount, 18)
        return {
            "status": "1",
            "message": "OK",
            "result": [
                {"hash": tx_hash, "to": payment.wallet_address, "value": str(units)}
            ],
        }

    return fake_http_get


def make_auto_orders(
    session,
    telegram_id: int,
    trc20_wallet: str,
    bep20_wallet: str,
) -> tuple[User, list[Payment], int]:
    user = upsert_user(session, telegram_id, f"user{telegram_id}")
    plan = add_vip_plan(session, "Security Plan", 1, 10.0)
    orders = create_auto_payment_orders(
        session,
        user_id=user.id,
        plan_id=plan.id,
        amount=10.0,
        trc20_wallet=trc20_wallet,
        bep20_wallet=bep20_wallet,
        trc20_amount=10.148,
        bep20_amount=10.231,
    )
    return user, orders


async def test_scan_activates_then_never_reactivates(db_factory) -> None:
    with db_factory() as session:
        user, _ = make_auto_orders(session, 710001, "TTRCSEC1", "0xBEPCSEC1")
        wallet_map = build_wallet_map(session)

    bot = AsyncMock()
    http_get = build_matching_http_get(wallet_map, "TX_SEC_HASH")
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        first = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )
        second = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )

    assert first == {"checked": 2, "paid": 1}
    assert second == {"checked": 0, "paid": 0}

    with db_factory() as session:
        trc = session.scalar(
            select(Payment).where(
                Payment.network == "trc20", Payment.user_id == user.id
            )
        )
        assert trc is not None
        assert trc.status == "paid"  # stays paid, never flipped back
        assert trc.transaction_id == "TX_SEC_HASH"
        assert len(list(session.scalars(select(Payment)).all())) == 2
        subs = list(session.scalars(select(UserVIPSubscription)).all())
        assert len(subs) == 1
        assert subs[0].status == "active"
        user_db = session.scalar(select(User).where(User.id == user.id))
        assert user_db is not None
        assert user_db.is_vip is True

    assert bot.send_message.await_count == 1


async def test_scan_skips_expired_schedule(db_factory) -> None:
    with db_factory() as session:
        user, orders = make_auto_orders(session, 700002, "T20SECEXP", "0xB20SECEXP")
        for order in orders:
            order.expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()

    bot = AsyncMock()
    hits: list[str] = []

    async def exploding_get(url, params=None, headers=None):
        hits.append(url)
        raise AssertionError("network must not be consulted for expired orders")

    with patch("app.services.payments.fetch_json", side_effect=exploding_get):
        result = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user.telegram_id
        )

    assert result == {"checked": 2, "paid": 0}
    assert hits == []
    assert bot.send_message.await_count == 0


async def test_scan_only_claims_specified_user(db_factory) -> None:
    with db_factory() as session:
        user_a, _ = make_auto_orders(session, 700003, "TTWALLA", "0xBWALLA")
        user_b, _ = make_auto_orders(session, 700004, "TTWALLB", "0xBWALLB")
        wallet_map = build_wallet_map(session)

    bot = AsyncMock()
    http_get = build_matching_http_get(wallet_map, "TX_USER_B")
    with patch("app.services.payments.fetch_json", side_effect=http_get):
        result = await check_pending_auto_payments(
            db_factory, bot, TEST_SETTINGS, only_user_id=user_b.telegram_id
        )

    assert result == {"checked": 2, "paid": 1}
    assert bot.send_message.await_count == 1

    with db_factory() as session:
        user_a_payments = list(
            session.scalars(select(Payment).where(Payment.user_id == user_a.id)).all()
        )
        assert len(user_a_payments) == 2
        assert all(p.status == "pending" for p in user_a_payments)
        user_b_trc = session.scalar(
            select(Payment).where(
                Payment.user_id == user_b.id, Payment.network == "trc20"
            )
        )
        assert user_b_trc is not None
        assert user_b_trc.status == "paid"


async def test_scan_unknown_only_user_returns_empty(db_factory) -> None:
    bot = AsyncMock()
    result = await check_pending_auto_payments(
        db_factory, bot, TEST_SETTINGS, only_user_id=999999
    )
    assert result == {"checked": 0, "paid": 0}
    assert bot.send_message.await_count == 0


# ============================================================
# F. Atomic claim — race / rowcount semantics
# ============================================================

async def test_atomic_claim_first_writer_wins(db_factory) -> None:
    with db_factory() as session:
        _, orders = make_auto_orders(session, 700005, "TTWALLC", "0xBWALLC")
        payment_id = orders[0].id

    with db_factory() as session:
        claimed = session.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="paid", transaction_id="TX_FIRST")
        )
        assert claimed.rowcount == 1
        session.commit()

    with db_factory() as session:
        row = session.scalar(select(Payment).where(Payment.id == payment_id))

        assert row is not None
        assert row.status == "paid"
        assert row.transaction_id == "TX_FIRST"

        claimed = session.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == "pending")
            .values(status="paid", transaction_id="TX_SECOND")
        )
        assert claimed.rowcount == 0
        session.commit()
        session.refresh(row)
        assert row.status == "paid"
        assert row.transaction_id == "TX_FIRST"


# ============================================================
# G. generate_unique_order_code — uniqueness and shape
# ============================================================

async def test_generate_unique_order_code_batch_unique_and_shape(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 700006, "codegen")
        plan = add_vip_plan(session, "Codes", 1, 1.0)
        codes: list[str] = []
        for _ in range(25):
            code = generate_unique_order_code(session)
            codes.append(code)
            session.add(
                Payment(
                    user_id=user.id,
                    plan_id=plan.id,
                    amount=1.0,
                    payment_method="trc20",
                    status="pending",
                    order_code=code,
                )
            )
            session.commit()

    assert len(set(codes)) == 25
    for code in codes:
        assert len(code) == 8
        assert code == code.upper()
        assert all(ch in string.hexdigits for ch in code)


# ============================================================
# H. Amount uniqueness — DB-backed collision avoidance (C1)
# ============================================================

async def test_auto_orders_regenerate_on_amount_collision_with_live_pending(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 711001, "nocollide")
        plan = add_vip_plan(session, "Collision", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRCCOLL",
            bep20_wallet="0xBEPCOLL",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        second = create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRCCOLL",
            bep20_wallet="0xBEPCOLL",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )

    amounts = {p.expected_amount for p in second}
    assert 10.148 not in amounts
    assert 10.231 not in amounts
    assert all(p.status == "pending" for p in second)


async def test_db_unique_index_blocks_duplicate_live_amount(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 711002, "dbidx")
        plan = add_vip_plan(session, "DbIdx", 1, 10.0)
        create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRCDBIDX",
            bep20_wallet="0xBEPDBIDX",
            trc20_amount=10.148,
            bep20_amount=10.231,
        )
        dup = Payment(
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            payment_method="trc20",
            status="pending",
            network="trc20",
            wallet_address="TTRCDBIDX",
            expected_amount=10.148,
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            session.commit()


async def test_migration_v9_unique_index_exists(db_factory) -> None:
    with db_factory() as session:
        index_name = session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='ux_payments_pending_auto_amount'"
            )
        ).scalar()
        assert index_name == "ux_payments_pending_auto_amount"


# ============================================================
# I. Expiry — atomic cancel + grace window (H3)
# ============================================================

async def test_expire_auto_payments_honors_grace_and_spares_paid(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 711003, "gracey")
        plan = add_vip_plan(session, "Grace", 1, 10.0)
        orders = create_auto_payment_orders(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            trc20_wallet="TTRCGRACE",
            bep20_wallet="0xBEPGRACE",
            trc20_amount=10.148,
            bep20_amount=10.231,
            order_hours=0,
        )
        orders[0].status = "paid"
        orders[0].transaction_id = "TX_PAID"
        session.commit()

    with db_factory() as session:
        assert expire_auto_payments(session, grace_seconds=3600) == 0
    with db_factory() as session:
        assert expire_auto_payments(session, grace_seconds=0) == 1
    with db_factory() as session:
        by_network = {p.network: p.status for p in session.scalars(select(Payment)).all()}
    assert by_network["trc20"] == "paid"
    assert by_network["bep20"] == "cancelled"


# ============================================================
# J. BEP20 pagination + payment-window bound (H2)
# ============================================================

async def test_bep20_pagination_finds_deep_transaction() -> None:
    units = amount_to_units(10.148, 18)
    page_calls: list[str] = []

    async def fake(url, params=None, headers=None):
        page = params.get("page", "1") if params else "1"
        page_calls.append(page)
        if page == "1":
            return {
                "status": "1",
                "message": "OK",
                "result": [
                    {
                        "hash": f"JUNK_{i}",
                        "to": "0xWALLET01",
                        "value": str(units + 100 + i),
                        "timeStamp": "9999999999",
                    }
                    for i in range(50)
                ],
            }
        return {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "BSC_DEEP",
                    "to": "0xWALLET01",
                    "value": str(units),
                    "timeStamp": "9999999999",
                }
            ],
        }

    assert await check_bep20_payment(fake, "0xWALLET01", 10.148) == "BSC_DEEP"
    assert page_calls == ["1", "2"]


async def test_bep20_since_ms_filters_old_transfer() -> None:
    units = amount_to_units(10.148, 18)

    async def fake(url, params=None, headers=None):
        return {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "OLD",
                    "to": "0xWALLET01",
                    "value": str(units),
                    "timeStamp": "100",
                },
                {
                    "hash": "NEW",
                    "to": "0xWALLET01",
                    "value": str(units),
                    "timeStamp": "200",
                },
            ],
        }

    # tx timestamp 100 (<150s) must be ignored, tx timestamp 200 must win.
    assert (
        await check_bep20_payment(fake, "0xWALLET01", 10.148, since_ms=150_000)
        == "NEW"
    )


# ============================================================
# K. Activation idempotency (H1)
# ============================================================

async def test_activate_flow_is_idempotent_per_payment(db_factory) -> None:
    with db_factory() as session:
        user = upsert_user(session, 711004, "IDEMP")
        plan = add_vip_plan(session, "Idem", 1, 10.0)
        payment = create_payment_order(
            session,
            user_id=user.id,
            plan_id=plan.id,
            amount=10.0,
            payment_method="manual",
        )

        sub_a = activate_vip_subscription_flow(session, payment.id)
        assert sub_a is not None
        sub_b = activate_vip_subscription_flow(session, payment.id)

        assert sub_b.id == sub_a.id
        assert sub_b.expires_at == sub_a.expires_at
        assert len(list(session.scalars(select(UserVIPSubscription)).all())) == 1
        user_db = session.scalar(select(User).where(User.id == user.id))
        assert user_db is not None
        assert (user_db.vip_expires_at.replace(tzinfo=UTC).timestamp() ==
                sub_a.expires_at.replace(tzinfo=UTC).timestamp())