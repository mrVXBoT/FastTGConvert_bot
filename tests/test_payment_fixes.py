"""tests/test_payment_fixes.py — Regression tests for the hardened auto-payment fixes.

Deterministic only: no real network access. Covers:
1. Wallet address validation helpers (base58 TRON, EVM hex, Binance UID).
2. Etherscan V2 BEP20 scanning (chainid/endblock shape, pagination, window filters).
3. Atomic claim+activate single-winner semantics.
4. v10 migration: unique index on user_vip_subscriptions.payment_id + dedupe.
5. TRC20 fingerprint pagination cursor + until-window skip.
6. get_activated_subscription_since (the M2 "already activated" guard).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.db.migration import MIGRATIONS, run_migrations
from app.db.models import Base, Payment, UserVIPSubscription
from app.db.repositories import (
    add_vip_plan,
    claim_and_activate_vip_subscription,
    create_auto_payment_orders,
    get_activated_subscription_since,
    upsert_user,
)
from app.services.addresses import (
    is_valid_bep20_address,
    is_valid_binance_id,
    is_valid_trc20_address,
)
from app.services.payments import (
    BSC_CHAIN_ID,
    TRANSFER_EVENT_TOPIC,
    USDT_BEP20_CONTRACT,
    USDT_TRC20_CONTRACT,
    amount_to_units,
    check_bep20_payment,
    check_trc20_payment,
)

UTC = timezone.utc  # noqa: UP017

TRC20_UNITS_10_148 = amount_to_units(10.148, 6)
BEP20_UNITS_10_148 = amount_to_units(10.148, 18)
VALID_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
VALID_BEP20 = "0x55d398326f99059fF775485246999027B3197955"


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    yield sf
    engine.dispose()


def make_bep20_fake(pages: list[list[dict]]):
    """Fake Etherscan V2 handler that also asserts the request shape."""

    async def fake(url: str, params: dict | None = None, headers: dict | None = None):
        assert url == "https://api.etherscan.io/v2/api"
        assert params.get("chainid") == str(BSC_CHAIN_ID)
        assert params.get("module") == "account"
        assert params.get("action") == "tokentx"
        assert params.get("endblock") == "999999999"
        p = int((params or {}).get("page", "1")) - 1
        page = min(p, len(pages) - 1)
        return {"status": "1", "message": "OK", "result": pages[page]}

    return fake


def _pending_pair(sf, telegram_id, t_wallet, b_wallet):
    with sf() as session:
        user = upsert_user(session, telegram_id, "payer")
        plan = add_vip_plan(session, "Fix", 1, 10.0)
        orders = create_auto_payment_orders(
            session, user_id=user.id, plan_id=plan.id, amount=10.0,
            currency="USD", trc20_wallet=t_wallet, bep20_wallet=b_wallet,
            trc20_amount=10.148, bep20_amount=10.231, order_hours=2,
        )
        return user.id, plan.id, orders


# ============================================================
# 1. Address validation (CRITICAL: typo becomes permanent loss)
# ============================================================

async def test_address_validators_accept_valid_inputs() -> None:
    assert is_valid_trc20_address(VALID_TRC20)
    assert is_valid_bep20_address(VALID_BEP20)
    assert is_valid_binance_id("123456789")
    assert is_valid_binance_id(None)


async def test_address_validators_reject_garbage() -> None:
    assert not is_valid_trc20_address(None)
    assert not is_valid_trc20_address("")
    assert not is_valid_trc20_address("T" + "x" * 33)
    assert not is_valid_trc20_address("TRC20address")
    assert not is_valid_bep20_address(None)
    assert not is_valid_bep20_address("BEP20address")
    assert not is_valid_bep20_address("0x123")
    assert not is_valid_bep20_address("0x" + "z" * 40)
    assert not is_valid_binance_id("nope")
    assert not is_valid_binance_id("12")


async def test_trc20_checksum_rejects_mutated_address() -> None:
    # Mutate one base58 char mid-address → checksum must fail, not silently pass.
    mutated = VALID_TRC20[:10] + "y" + VALID_TRC20[11:]
    assert mutated != VALID_TRC20
    assert is_valid_trc20_address(mutated) is False
    assert is_valid_trc20_address(VALID_TRC20) is True


# ============================================================
# 2. Etherscan V2 endpoint (replaces decommissioned BscScan V1)
# ============================================================

async def test_bep20_uses_etherscan_v2_params() -> None:
    page = [{"hash": "BSC_TX", "to": "0xWALLET01", "value": str(BEP20_UNITS_10_148)}]
    assert await check_bep20_payment(make_bep20_fake([page]), "0xWALLET01", 10.148) == "BSC_TX"


async def test_bep20_until_filter_excludes_too_new_transfer() -> None:
    page = [
        {
            "hash": "BSC_LATE",
            "to": "0xWALLET01",
            "value": str(BEP20_UNITS_10_148),
            "timeStamp": "9999999999",
        }
    ]
    assert (
        await check_bep20_payment(
            make_bep20_fake([page]), "0xWALLET01", 10.148,
            until_ms=1_000_000_000_000,
        )
        is None
    )


async def test_bep20_free_plan_chain_unsupported_returns_none() -> None:
    async def fake(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "status": "0",
            "message": "NOTOK",
            "result": "Free API access is not supported for this chain",
        }

    assert await check_bep20_payment(fake, "0xWALLET01", 10.148, api_key="k1") is None


async def test_bep20_paginates_past_one_page() -> None:
    page1 = [
        {"hash": f"SPAM_{i}", "to": "0xWALLET01", "value": "123", "timeStamp": "1750000000"}
        for i in range(50)
    ]
    page2 = [
        {"hash": "BSC_DEEP", "to": "0xWALLET01", "value": str(BEP20_UNITS_10_148), "timeStamp": "1750000000"}
    ]
    assert (
        await check_bep20_payment(make_bep20_fake([page1, page2]), "0xWALLET01", 10.148)
        == "BSC_DEEP"
    )


# ============================================================
# 3. Atomic claim + activate
# ============================================================

async def test_claim_and_activate_is_single_winner(db_factory) -> None:
    _, _, orders = _pending_pair(db_factory, 33001, "TWALLET01", "BWALLET01")
    pay_id = orders[0].id

    with db_factory() as session:
        first = claim_and_activate_vip_subscription(session, pay_id, "TX1")
        assert first is not None
        # Re-claim of the same (already-paid) payment is a no-op, never a second grant.
        second = claim_and_activate_vip_subscription(session, pay_id, "TX1")
        assert second is None
        subs = session.scalars(
            select(UserVIPSubscription).where(UserVIPSubscription.payment_id == pay_id)
        ).all()
        assert len(subs) == 1
        refreshed = session.get(Payment, pay_id)
        assert refreshed.status == "paid"
        assert refreshed.transaction_id == "TX1"
        assert refreshed.confirmed_at is not None


async def test_claim_and_activate_after_expired_returns_none(db_factory) -> None:
    _user_id, _, orders = _pending_pair(db_factory, 876543, "TWALLET01", "BWALLET01")
    pay_id = orders[0].id
    with db_factory() as session:
        pay = session.get(Payment, pay_id)
        pay.status = "cancelled"
        session.commit()
        result = claim_and_activate_vip_subscription(session, pay_id, "TX_GHOST")
        assert result is None
        assert session.get(Payment, pay_id).status == "cancelled"


# ============================================================
# 4. v10 migration: single subscription per payment
# ============================================================

def test_v10_creates_unique_subscription_index(db_factory) -> None:
    with db_factory() as session:
        idx = session.execute(
            text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
                "AND name='ux_user_vip_subscriptions_payment'"
            )
        ).scalar()
    assert idx == 1


def test_v10_deduplicates_and_guards_duplicate_subs() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    conn = engine.raw_connection()
    cursor = conn.cursor()
    for v in range(1, 10):
        cursor.execute("BEGIN TRANSACTION")
        MIGRATIONS[v](cursor)
        cursor.execute(f"PRAGMA user_version = {v}")
        conn.commit()
    conn.close()

    sf = sessionmaker(bind=engine, expire_on_commit=False)
    with sf() as session:
        user = upsert_user(session, 90909, "dup")
        plan = add_vip_plan(session, "Dup", 1, 10.0)
        pay = Payment(
            user_id=user.id, plan_id=plan.id, amount=10.0, currency="USD",
            payment_method="trc20", status="paid", transaction_id="TX_DUP",
            network="trc20", wallet_address="TWALLET", expected_amount=10.148,
        )
        session.add(pay)
        session.flush()
        now_ms = datetime.now(UTC)
        for _i in range(3):
            session.add(
                UserVIPSubscription(
                    user_id=user.id, plan_id=plan.id, payment_id=pay.id,
                    started_at=now_ms, expires_at=now_ms + timedelta(days=30),
                    status="active",
                )
            )
        session.commit()
        pay_id = pay.id

    # v10 (fresh fish: user_version is still 9) dedupes the three rows into one
    # and adds the unique partial index.
    run_migrations(engine)
    with sf() as session:
        remaining = session.scalars(
            select(UserVIPSubscription).where(
                UserVIPSubscription.payment_id == pay_id
            )
        ).all()
        assert len(remaining) == 1
        idx = session.execute(
            text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
                "AND name='ux_user_vip_subscriptions_payment'"
            )
        ).scalar()
        assert idx == 1
    engine.dispose()


# ============================================================
# 5. TRC20 fingerprint pagination
# ============================================================

async def test_trc20_paginates_through_fingerprint() -> None:
    async def fake(url: str, params: dict | None = None, headers: dict | None = None):
        if (params or {}).get("fingerprint") is None:
            return {
                "success": True,
                "data": [
                    {
                        "transaction_id": "TX_P1",
                        "type": "Transfer",
                        "to": "TWALLET01",
                        "value": str(TRC20_UNITS_10_148 + 7),
                        "token_info": {"address": USDT_TRC20_CONTRACT},
                    }
                ],
                "meta": {"fingerprint": "fp1"},
            }
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_DEEP",
                    "type": "Transfer",
                    "to": "TWALLET01",
                    "value": str(TRC20_UNITS_10_148),
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                }
            ],
            "meta": {"fingerprint": None},
        }

    assert await check_trc20_payment(fake, "TWALLET01", 10.148, 0) == "TX_DEEP"


async def test_trc20_skips_transfer_after_until_window() -> None:
    too_new_ts = int((datetime.now(UTC) + timedelta(days=1)).timestamp() * 1000)

    async def fake(url: str, params: dict | None = None, headers: dict | None = None):
        return {
            "success": True,
            "data": [
                {
                    "transaction_id": "TX_TOO_NEW",
                    "type": "Transfer",
                    "to": "TWALLET01",
                    "value": str(TRC20_UNITS_10_148),
                    "block_timestamp": too_new_ts,
                    "token_info": {"address": USDT_TRC20_CONTRACT},
                }
            ],
            "meta": {"fingerprint": None},
        }

    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    assert (
        await check_trc20_payment(fake, "TWALLET01", 10.148, 0, until_ms=now_ms)
        is None
    )


# ============================================================
# 6. get_activated_subscription_since (M2 guard)
# ============================================================

async def test_helper_finds_auto_activated_subscription(db_factory) -> None:
    user_id, _, orders = _pending_pair(db_factory, 987654, "TWALLET", "BWALLET")
    pay_id = orders[0].id
    with db_factory() as session:
        sub = claim_and_activate_vip_subscription(session, pay_id, "M2TX")
        assert sub is not None
        found = get_activated_subscription_since(
            session, user_id, datetime.now(UTC) - timedelta(hours=3)
        )
        assert found is not None
        assert found.payment_id == pay_id
        # Future window → nothing activated yet.
        stale = get_activated_subscription_since(
            session, user_id, datetime.now(UTC) + timedelta(hours=3)
        )
        assert stale is None


async def test_unpaid_payment_is_not_reported_activated(db_factory) -> None:
    _user_id, _plan_id, _orders = _pending_pair(db_factory, 111222, "TWALLET", "BWALLET")
    with db_factory() as session:
        found = get_activated_subscription_since(
            session, 111222, datetime.now(UTC) - timedelta(hours=3)
        )
        assert found is None


# ============================================================
# 7. BSC RPC (eth_getLogs) — free keyless BEP20 detection
# ============================================================

VALID_BEP_WALLET = "0x55d398326f99059fF775485246999027B3197955"


def _rpc_post_fake(
    logs: list[dict] | None = None,
    latest_block: int = 1_000_000,
    error: bool = False,
) -> tuple:
    """Return (http_post, calls) where `calls` records every JSON-RPC request."""
    calls: list[dict] = []

    async def http_post(url, payload):
        calls.append(payload)
        method = payload["method"]
        if method == "eth_blockNumber":
            return {"result": hex(latest_block)}
        if method == "eth_getLogs":
            if error:
                return {"error": {"code": -32016, "message": "too many results"}}
            return {"result": logs or []}
        return {"result": None}

    return http_post, calls


async def test_bep20_rpc_matches_exact_value(monkeypatch) -> None:
    wallet = VALID_BEP20
    post, calls = _rpc_post_fake(
        logs=[
            {
                "transactionHash": "0xBSC_RPC_HASH",
                "data": hex(BEP20_UNITS_10_148),
            }
        ]
    )
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    assert (
        await check_bep20_payment(None, wallet, 10.148, rpc_urls=("https://node",))
        == "0xBSC_RPC_HASH"
    )
    methods = [c["method"] for c in calls]
    assert "eth_blockNumber" in methods and "eth_getLogs" in methods
    # The indexed `to` topic must be our wallet, ABI-padded to 32 bytes.
    log_params = next(c["params"][0] for c in calls if c["method"] == "eth_getLogs")
    assert log_params["address"].lower() == USDT_BEP20_CONTRACT.lower()
    expected_topic = "0x" + wallet[2:].lower().zfill(64)
    assert log_params["topics"] == [TRANSFER_EVENT_TOPIC, None, expected_topic]


async def test_bep20_rpc_no_transfer_returns_none(monkeypatch) -> None:
    post, _ = _rpc_post_fake(logs=[])
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    assert (
        await check_bep20_payment(
            None, VALID_BEP20, 10.148, since_ms=1_000, rpc_urls=("https://node",)
        )
        is None
    )


async def test_bep20_rpc_node_error_returns_none(monkeypatch) -> None:
    post, _ = _rpc_post_fake(error=True)
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    assert (
        await check_bep20_payment(None, VALID_BEP20, 10.148, rpc_urls=("https://node",))
        is None
    )


async def test_bep20_rpc_full_expiry_window_returns_none(monkeypatch) -> None:
    post, calls = _rpc_post_fake(
        logs=[
            {
                "transactionHash": "0xBSC_RPC_HASH",
                "data": hex(BEP20_UNITS_10_148),
            }
        ]
    )
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    since_ms = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    until_ms = int((datetime.now(UTC) - timedelta(hours=9)).timestamp() * 1000)
    # Payment window already fully in the past → end < start → no caches asked.
    assert (
        await check_bep20_payment(
            None,
            VALID_BEP20,
            10.148,
            since_ms=since_ms,
            until_ms=until_ms,
            rpc_urls=("https://node",),
        )
        is None
    )
    assert all(c["method"] != "eth_getLogs" for c in calls)


async def test_bep20_rpc_chunks_large_window(monkeypatch) -> None:
    # 10 days of blocks at 3s → ~288k blocks; must be sliced in chunks.
    since_ms = int((datetime.now(UTC) - timedelta(days=10)).timestamp() * 1000)
    post, calls = _rpc_post_fake(logs=[])
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    assert (
        await check_bep20_payment(
            None, VALID_BEP20, 10.148, since_ms=since_ms, rpc_urls=("https://node",)
        )
        is None
    )
    get_logs = [c for c in calls if c["method"] == "eth_getLogs"]
    assert len(get_logs) > 1


async def test_bep20_prefers_rpc_over_etherscan_when_configured(monkeypatch) -> None:
    post, calls = _rpc_post_fake(logs=[])
    monkeypatch.setattr("app.services.payments.bsc_rpc_post", post)
    # Even with an api_key present, configured RPC nodes take priority.
    assert (
        await check_bep20_payment(
            None, VALID_BEP20, 10.148, api_key="k", rpc_urls=("https://node",)
        )
        is None
    )
    assert any(c["method"] == "eth_getLogs" for c in calls)