"""app/services/payments.py — Automatic crypto payment detection (TRON TRC20 + BSC BEP20 USDT)."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017

from typing import Any

import aiohttp
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.models import User
from app.db.repositories import (
    cancel_sibling_auto_orders,
    claim_and_activate_vip_subscription,
    get_vip_plan,
    is_transaction_used,
    list_pending_auto_payments,
)
from app.locales import PAYMENT_CONFIRMED_MESSAGES

LOGGER = logging.getLogger(__name__)

USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

# Serialize all payment scans so the poll loop and a user's "Check Payment" button
# can never race each other (two concurrent scans must not both claim one transfer).
_SCAN_LOCK = asyncio.Lock()

# Max parallel chain-RPC scans inside one lock-held pass. DB writes stay on the
# single session afterwards, so SQLite sees no concurrent writers.
_SCAN_CONCURRENCY = 4

# BEP20 scans paginate through at most this many 50-tx pages so customers buried
# under spam (`> 50`) transfers to the shared wallet are still detected.
MAX_BEP20_PAGES = 5
# TRC20 scans page through the TronGrid `fingerprint` cursor, capped for safety
# (200 events per request; payments are further window-bound by min_timestamp).
MAX_TRC20_PAGES = 20

# Etherscan V2 is the only supported API for BSC token transfers: the legacy
# `api.bscscan.com` V1 endpoint was decommissioned in 2025 and now always returns
# "deprecated V1 endpoint". BNB Smart Chain (chainid 56) needs a PAID Etherscan
# plan — free keys are rejected for this chain, so BEP20 detection must be
# considered a paid capability.
BSC_SCAN_BASE = "https://api.etherscan.io/v2/api"
BSC_CHAIN_ID = 56
# Etherscan V2 requires an upper endblock; 9 nines is above the current BSC height
# (~114M) so the 8-nines "99999999" truncation bug can never exclude live transfers.
BSC_MAX_BLOCK = 999_999_999

HttpGetter = Callable[..., Awaitable[dict | None]]


def generate_expected_amount(
    base: float, used_amounts: set[float] | None = None
) -> float:
    """Generate a collision-free expected amount near *base*, rounded to 3 decimals."""
    used = used_amounts or set()
    for _ in range(100):
        candidate = round(base + random.uniform(0.001, 0.999), 3)
        if not any(abs(candidate - other) < 0.001 for other in used):
            return candidate
    return round(base + 0.001, 3)


def amount_to_units(amount: float, decimals: int) -> int:
    """Convert a 3-decimal *amount* to integer chain units without float rounding error.

    Float math (``round(amount * 10**decimals)``) loses precision above 2**53,
    which silently breaks detection for large 18-decimal (BEP20) amounts. Building
    the units from the decimal string is exact.
    """
    whole, _, frac = f"{amount:.3f}".partition(".")
    frac = (frac + "0" * decimals)[:decimals]
    return int(whole) * (10**decimals) + (int(frac) if frac else 0)


async def fetch_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 10.0,
) -> dict | None:
    """Perform a GET request and return the parsed JSON, or None on any failure."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session, session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                LOGGER.debug("HTTP %s from %s", resp.status, url)
                return None
            return await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Request to %s failed: %s", url, exc)
        return None


# --- BSC RPC (eth_getLogs) helpers for BEP20 detection -----------------------
#
# Free, keyless on-chain detection for BSC. `eth_getLogs` filters the USDT
# contract's Transfer events whose *indexed `to`* topic equals our wallet, so it
# uses no indexer API and no paid plan. Activation is explicit via BSC_RPC_URLS,
# otherwise the Etherscan V2 path (paid plan) is used.

# BEP20 / EVM Transfer(address indexed from, address indexed to, uint256 value)
TRANSFER_EVENT_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
BSC_BLOCK_SECONDS = 3.0  # BNB Smart Chain produces a block ~every 3s
# Timestamp→block mapping is drift-prone on a public node; scan this many extra
# blocks before/after the estimated boundaries so a payment is never missed.
BSC_BOUND_SLACK_BLOCKS = 300
# eth_getLogs is limited per-call on public RPCs; window is sliced into chunks.
BSC_LOG_CHUNK_BLOCKS = 1500
DEFAULT_BSC_RPC_URLS = (
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed1.ninicoin.io",
    "https://bsc-dataseed2.ninicoin.io",
    "https://bsc-dataseed3.ninicoin.io",
    "https://bsc-rpc.publicnode.com",
    "https://rpc.ankr.com/bsc",
)


async def bsc_rpc_post(url: str, payload: dict, timeout: float = 10.0) -> dict | None:
    """POST a JSON-RPC request to a BSC RPC node; returns its parsed result dict."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session, session.post(url, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("BSC RPC %s failed: %s", url, exc)
        return None
    if not isinstance(data, dict) or "result" not in data:
        LOGGER.debug("BSC RPC %s returned a non-JSON-RPC response", url)
        return None
    return data


async def bsc_rpc_request(
    rpc_urls: tuple[str, ...],
    rpc_post: Callable[..., Awaitable[dict | None]],
    method: str,
    params: list,
) -> object | None:
    """Call a JSON-RPC method across the given RPC nodes until one answers."""
    for node in rpc_urls:
        resp = await rpc_post(node, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if resp is None:
            continue
        if "error" in resp:
            LOGGER.debug("BSC RPC error on %s for %s: %s", node, method, resp.get("error"))
            continue
        return resp.get("result")
    return None


def _bsc_transfer_topic(wallet: str) -> str:
    """ABI-encode the `to` address as an indexed log topic (32-byte left-padded)."""
    return "0x" + wallet[2:].lower().zfill(64)


async def _check_bep20_via_rpc(
    rpc_urls: tuple[str, ...],
    rpc_post: Callable[..., Awaitable[dict | None]],
    wallet: str,
    expected_units: int,
    since_ms: int,
    until_ms: int,
) -> str | None:
    """Scan BSC `eth_getLogs` for a USDT Transfer to *wallet* of *expected_units*."""
    latest_raw = await bsc_rpc_request(rpc_urls, rpc_post, "eth_blockNumber", [])
    if latest_raw is None:
        return None
    if not isinstance(latest_raw, (str, bytes, bytearray)):
        return None
    try:
        latest_block = int(latest_raw, 16)
    except (TypeError, ValueError):
        return None

    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    if since_ms > 0:
        start = latest_block - int((now_ms - since_ms) / (BSC_BLOCK_SECONDS * 1000)) - BSC_BOUND_SLACK_BLOCKS
        start = max(0, start)
    else:
        start = 0
    end = latest_block
    if until_ms > 0 and until_ms < now_ms:
        end = latest_block - int((now_ms - until_ms) / (BSC_BLOCK_SECONDS * 1000)) + BSC_BOUND_SLACK_BLOCKS
        end = min(end, latest_block)
    if end < start:
        return None
    start = min(start, end)

    topic_to = _bsc_transfer_topic(wallet)
    for chunk_start in range(start, end + 1, BSC_LOG_CHUNK_BLOCKS):
        chunk_end = min(chunk_start + BSC_LOG_CHUNK_BLOCKS - 1, end)
        logs = await bsc_rpc_request(
            rpc_urls,
            rpc_post,
            "eth_getLogs",
            [
                {
                    "address": USDT_BEP20_CONTRACT,
                    "fromBlock": hex(chunk_start),
                    "toBlock": hex(chunk_end),
                    "topics": [TRANSFER_EVENT_TOPIC, None, topic_to],
                }
            ],
        )
        if not isinstance(logs, list):
            return None
        for log in logs:
            data = log.get("data")
            if not isinstance(data, str):
                continue
            try:
                value = int(data, 16)
            except ValueError:
                continue
            if value == expected_units:
                return log.get("transactionHash")
    return None


async def check_trc20_payment(
    http_get: HttpGetter,
    wallet: str,
    expected_amount: float,
    since_ms: int,
    api_key: str = "",
    until_ms: int = 0,
) -> str | None:
    """Return the TRC20 USDT transfer hash matching the expected payment, if any.

    Pages through TronGrid's ``fingerprint`` cursor (max ``MAX_TRC20_PAGES`` pages
    of 200 events) so an exact-amount transfer buried under newer spam is still
    found. ``since_ms``/``until_ms`` bound the accepted timestamp window: the
    ``min_timestamp`` query param narrows the request, and ``until_ms`` skips any
    transfer confirmed after the payment window (+ grace) expired.
    """
    headers = {"TRON-PRO-API-KEY": api_key} if api_key else None
    fingerprint: str | None = None
    expected_units = amount_to_units(expected_amount, 6)
    for _ in range(MAX_TRC20_PAGES):
        params: dict[str, str] = {
            "only_confirmed": "true",
            "limit": "200",
            "min_timestamp": str(since_ms),
            "order_by": "block_timestamp,desc",
        }
        if fingerprint:
            params["fingerprint"] = fingerprint
        data = await http_get(
            f"https://api.trongrid.io/v1/accounts/{wallet}/transactions/trc20",
            params=params,
            headers=headers,
        )
        if not data or not data.get("success"):
            return None
        for entry in data.get("data", []):
            token_info = entry.get("token_info") or {}
            if entry.get("type") != "Transfer":
                continue
            if str(token_info.get("address", "")).upper() != USDT_TRC20_CONTRACT.upper():
                continue
            if str(entry.get("to", "")).upper() != wallet.upper():
                continue
            raw_ts = entry.get("block_timestamp")
            if until_ms and raw_ts is not None:
                try:
                    if int(raw_ts) > until_ms:
                        continue
                except (TypeError, ValueError):
                    pass
            try:
                value = int(entry.get("value"))
            except (TypeError, ValueError):
                continue
            if value != expected_units:
                continue
            return entry.get("transaction_id")
        meta = data.get("meta") or {}
        fingerprint = meta.get("fingerprint") if isinstance(meta, dict) else None
        if not fingerprint:
            break
    return None


async def check_bep20_payment(
    http_get: HttpGetter,
    wallet: str,
    expected_amount: float,
    api_key: str = "",
    since_ms: int = 0,
    until_ms: int = 0,
    rpc_urls: tuple[str, ...] = (),
) -> str | None:
    """Return the BEP20 USDT transfer hash matching the expected payment, if any.

    Two detection backends, selected automatically:

    - When ``rpc_urls`` is non-empty (configured via ``BSC_RPC_URLS``), the scan
      runs keyless on BSC public RPC nodes with ``eth_getLogs``, filtering the USDT
      contract's Transfer events to our wallet (indexed ``to`` topic). This needs
      no API key and no paid Etherscan plan.
    - Otherwise it uses the Etherscan V2 endpoint (``api.etherscan.io/v2/api``),
      which is the only *indexed* API for BNB Smart Chain after the legacy
      ``bscscan.com`` V1 endpoint was decommissioned. ``endblock=BSC_MAX_BLOCK``:
      the previous 8-nines cutoff silently truncates pages once the BSC chain
      exceeds 99,999,999 blocks (~2028), which would hide live transfers.

    Both scan window-bounded via ``since_ms``/``until_ms``.
    """
    if rpc_urls:
        return await _check_bep20_via_rpc(
            rpc_urls,
            bsc_rpc_post,
            wallet,
            amount_to_units(expected_amount, 18),
            since_ms,
            until_ms,
        )
    if not api_key:
        LOGGER.debug("No BSC API key; requesting Etherscan V2 anonymously for %s", wallet)
    expected_units = amount_to_units(expected_amount, 18)

    params: dict[str, str] = {
        "chainid": str(BSC_CHAIN_ID),
        "module": "account",
        "action": "tokentx",
        "address": wallet,
        "contractaddress": USDT_BEP20_CONTRACT,
        "offset": "50",
        "sort": "desc",
        "startblock": "0",
        "endblock": str(BSC_MAX_BLOCK),
        "apikey": api_key,
    }

    for page in range(1, MAX_BEP20_PAGES + 1):
        params["page"] = str(page)
        data = await http_get(BSC_SCAN_BASE, params=params)
        if not data:
            return None
        status = str(data.get("status"))
        result = data.get("result")
        if status != "1" or not isinstance(result, list):
            if status not in ("0", "1"):
                LOGGER.warning("Unexpected BSC response status %r", status)
            return None
        for tx in result:
            if str(tx.get("to", "")).lower() != wallet.lower():
                continue
            raw_ts = tx.get("timeStamp")
            if raw_ts is not None:
                try:
                    ts = int(raw_ts) * 1000
                except (TypeError, ValueError):
                    ts = 0
                if since_ms and ts < since_ms:
                    continue
                if until_ms and ts > until_ms:
                    continue
            try:
                value = int(tx.get("value"))
            except (TypeError, ValueError):
                continue
            if value != expected_units:
                continue
            return tx.get("hash")
        if len(result) < 50:
            break
    return None


async def notify_payment_confirmed(
    bot: Bot,
    telegram_id: int,
    language: str,
    plan_name: str,
    expires_at: datetime,
) -> None:
    """Notify the user that their payment was confirmed, ignoring delivery errors."""
    template = PAYMENT_CONFIRMED_MESSAGES.get(
        language, PAYMENT_CONFIRMED_MESSAGES["en"]
    )
    text = template.format(plan=plan_name, date=expires_at.strftime("%Y-%m-%d"))
    try:
        await bot.send_message(
            chat_id=telegram_id, text=text, parse_mode="HTML"
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Failed to notify user %s about payment: %s", telegram_id, exc)


async def check_pending_auto_payments(
    session_factory: sessionmaker[Session],
    bot: Bot,
    settings: Settings,
    only_user_id: int | None = None,
) -> dict[str, int]:
    """Scan pending auto payments once and activate VIP for confirmed transfers.

    Serialized behind a process-wide lock so the background poll loop and a user's
    "Check Payment" button can never run overlapping scans concurrently.
    """
    async with _SCAN_LOCK:
        return await _scan_pending_payments(session_factory, bot, settings, only_user_id)


async def _scan_pending_payments(
    session_factory: sessionmaker[Session],
    bot: Bot,
    settings: Settings,
    only_user_id: int | None,
) -> dict[str, int]:
    """Single (lock-held) scan over pending auto payments."""
    result = {"checked": 0, "paid": 0}
    grace = max(0, settings.payment_expiry_grace_seconds)
    with session_factory() as session:
        payments = list_pending_auto_payments(session)
        if only_user_id is not None:
            target = session.scalar(
                select(User).where(User.telegram_id == only_user_id)
            )
            if target is None:
                return result
            payments = [p for p in payments if p.user_id == target.id]

        # Pre-compute scan params on the shared session, then run the SLOW
        # chain RPC scans in bounded parallel. All DB reads/writes stay on
        # this single session sequentially afterwards (SQLite-safe), while
        # the network waits no longer serialize one payment after another.
        items: list[tuple[Any, Any, Any, tuple]] = []
        for payment in payments:
            result["checked"] += 1
            expires_at = payment.expires_at
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at <= datetime.now(UTC) - timedelta(seconds=grace):
                    continue
            if payment.expected_amount is None or not payment.wallet_address:
                continue
            user = session.scalar(select(User).where(User.id == payment.user_id))
            if user is None:
                continue
            plan = get_vip_plan(session, payment.plan_id)
            created_at = payment.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            since_ms = int(created_at.timestamp() * 1000)
            # Transfers are only accepted inside [created_at, expires_at + grace];
            # bounding `until_ms` skips pre-sent/duplicate transfers that arrived
            # after the order already expired.
            until_ms = 0
            if expires_at is not None:
                window_end = expires_at + timedelta(seconds=grace)
                if window_end.tzinfo is None:
                    window_end = window_end.replace(tzinfo=UTC)
                until_ms = int(window_end.timestamp() * 1000)
            if payment.network == "trc20":
                args: tuple = (
                    "trc20",
                    payment.wallet_address,
                    payment.expected_amount,
                    since_ms,
                    settings.tron_api_key,
                    until_ms,
                )
            elif payment.network == "bep20":
                rpc_urls = tuple(
                    u.strip()
                    for u in (settings.bsc_rpc_urls or "").split(",")
                    if u.strip()
                )
                args = (
                    "bep20",
                    payment.wallet_address,
                    payment.expected_amount,
                    since_ms,
                    settings.bsc_api_key,
                    until_ms,
                    rpc_urls,
                )
            else:
                continue
            items.append((payment, user, plan, args))

        scan_semaphore = asyncio.Semaphore(min(_SCAN_CONCURRENCY, len(items) or 1))

        async def scan_one(
            args: tuple,
        ) -> str | None:
            async with scan_semaphore:
                if args[0] == "trc20":
                    _, wallet, expected, since_ms, api_key, until_ms = args
                    return await check_trc20_payment(
                        fetch_json,
                        wallet,
                        expected,
                        since_ms,
                        api_key,
                        until_ms,
                    )
                _, wallet, expected, since_ms, api_key, until_ms, rpc_urls = args
                return await check_bep20_payment(
                    fetch_json,
                    wallet,
                    expected,
                    api_key,
                    since_ms,
                    until_ms,
                    rpc_urls=rpc_urls,
                )

        txs = await asyncio.gather(*(scan_one(args) for _, _, _, args in items))

        for (payment, user, plan, _args), tx in zip(items, txs):
            if not tx:
                continue
            if is_transaction_used(session, tx):
                continue
            # Atomic claim + activate: the rowcount guard makes the pending->paid
            # transition single-winner, so an expiry sweep running from ANOTHER
            # process cannot both mark this payment paid and void it.
            sub = claim_and_activate_vip_subscription(session, payment.id, tx)
            if not sub:
                LOGGER.warning(
                    "Matched transfer %s for payment %s but claim failed "
                    "(already processed/expired); leaving it unclaimed.",
                    tx,
                    payment.id,
                )
                continue
            cancel_sibling_auto_orders(session, payment)
            result["paid"] += 1
            try:
                await notify_payment_confirmed(
                    bot,
                    user.telegram_id,
                    user.language or "en",
                    plan.name if plan else "VIP",
                    sub.expires_at,
                )
            except Exception:
                LOGGER.exception(
                    "Failed to notify payment confirmation for payment %s",
                    payment.id,
                )
    return result


async def payment_polling_loop(
    session_factory: sessionmaker[Session], bot: Bot, settings: Settings
) -> None:
    """Continuously poll pending auto payments for confirmed on-chain transfers."""
    while True:
        try:
            await check_pending_auto_payments(session_factory, bot, settings)
        except Exception:
            LOGGER.exception("Auto-payment scan failed")
        await asyncio.sleep(settings.payment_check_interval_seconds)
