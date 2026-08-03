"""
Live OTP reading and session logout service using Telethon.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from contextlib import suppress
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from pathlib import Path

from app.otp_results import OTPCode

LOGGER = logging.getLogger(__name__)

_TELEGRAM_SERVICE_PEER = 777000


def format_time_ago(dt: datetime) -> str:
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    elapsed = max(0, int((now - dt).total_seconds()))
    if elapsed < 60:
        return f"{max(1, elapsed)}s ago"
    if elapsed < 3600:
        return f"{elapsed // 60}m ago"
    return f"{elapsed // 3600}h ago"


async def read_account_otps(
    session_path: Path,
    credentials: list[tuple[int, str]],
    max_age_hours: int = 2,
    since_dt: datetime | None = None,
    proxy: tuple | None = None,
) -> tuple[dict[str, str], list[OTPCode]]:
    """
    Connect to Telegram with session_path and read recent OTP messages from Telegram (peer 777000).
    Returns (user_info, list_of_OTPCode_objects).
    """
    default_user_info: dict[str, str] = {}
    if not credentials or not session_path.exists():
        return default_user_info, []

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("telethon is not installed; cannot read live OTPs")
        return default_user_info, []

    with tempfile.TemporaryDirectory(prefix="ftgc_otpread_") as tmp:
        tmp_session = Path(tmp) / "read.session"
        shutil.copy2(session_path, tmp_session)
        session_str = str(tmp_session.with_suffix(""))

        for api_id, api_hash in credentials:
            client = TelegramClient(
                session_str, api_id, api_hash, receive_updates=False, proxy=proxy
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    continue

                me = await client.get_me()
                user_info: dict[str, str] = {}
                if me:
                    full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                    user_info["user"] = full_name if full_name else "N/A"
                    user_info["phone"] = f"+{me.phone}" if me.phone else "N/A"
                    user_info["username"] = f"@{me.username}" if me.username else "N/A"

                cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
                if since_dt is not None:
                    if since_dt.tzinfo is None:
                        since_dt = since_dt.replace(tzinfo=UTC)
                    cutoff = max(cutoff, since_dt)

                codes: list[OTPCode] = []

                async for message in client.iter_messages(
                    _TELEGRAM_SERVICE_PEER, limit=10
                ):
                    if message.date and message.date <= cutoff:
                        continue
                    text = message.text or ""
                    if not text:
                        continue

                    match = re.search(r"\b(\d{5,6})\b", text)
                    if match:
                        code = match.group(1)
                        time_ago = (
                            format_time_ago(message.date)
                            if message.date
                            else "recently"
                        )
                        codes.append(
                            OTPCode(code=code, age=time_ago, source="Telegram")
                        )

                await client.disconnect()
                return user_info, codes

            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("OTP read attempt failed with api_id=%d: %s", api_id, exc)
                with suppress(Exception):
                    await client.disconnect()

    return default_user_info, []


async def logout_account_session(
    session_path: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
) -> bool:
    """
    Connect with session_path and execute client.log_out() to revoke session on Telegram servers.
    """
    if not credentials or not session_path.exists():
        return False

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return False

    for api_id, api_hash in credentials:
        client = TelegramClient(
            str(session_path.with_suffix("")),
            api_id,
            api_hash,
            receive_updates=False,
            proxy=proxy,
        )
        try:
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
                return True
            await client.disconnect()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Logout attempt failed with api_id=%d: %s", api_id, exc)
            with suppress(Exception):
                await client.disconnect()

    return False
