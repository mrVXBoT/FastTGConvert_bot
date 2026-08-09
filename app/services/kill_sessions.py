from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import _is_valid_sqlite_session
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)


def _mask_api_id(api_id: int) -> str:
    """Mask an API credential id for log safety."""
    s = str(api_id)
    return f"{s[:3]}***" if len(s) > 3 else "***"


# Max concurrent kill operations (shared api credentials / IP flood ceiling).
_KILL_CONCURRENCY = 8


@dataclass(frozen=True)
class SessionKillDetail:
    session_name: str
    status: str  # 'ok' | 'fresh_forbidden' | 'unauthorized' | 'invalid_sqlite' | 'error'
    message: str


@dataclass(frozen=True)
class KillSessionsResult:
    total: int
    killed: int
    fresh_forbidden: int
    failed: int
    details: tuple[SessionKillDetail, ...]


async def kill_single_session_others(
    session_file: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
) -> tuple[str, str]:
    """Execute ResetAuthorizationsRequest for a single session file.

    Returns (status, message).
    Possible status: 'ok', 'fresh_forbidden', 'unauthorized', 'error'
    """
    if not _is_valid_sqlite_session(session_file):
        return "invalid_sqlite", "Invalid SQLite database or missing auth_key"

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyUnregisteredError,
            FreshResetAuthorisationForbiddenError,
            RPCError,
            SessionRevokedError,
            SessionTooFreshError,
            UserDeactivatedError,
        )
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for kill session")
        return "error", "Telethon library missing"

    last_err: str | None = None
    for api_id, api_hash in credentials:
        with tempfile.TemporaryDirectory(prefix="ftgc_kill_sess_") as tmp:
            run_sess = Path(tmp) / "account.session"
            shutil.copy2(session_file, run_sess)
            stem = str(run_sess.with_suffix(""))

            from app.services.device_params import get_stable_device_params
            device_kwargs = get_stable_device_params(session_file)
            client = TelegramClient(
                stem, api_id, api_hash, receive_updates=False, proxy=proxy, **device_kwargs
            )
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    return "unauthorized", "Session unauthorized or revoked"

                await client(functions.auth.ResetAuthorizationsRequest())
                return "ok", "Successfully logged out all other sessions"
            except (FreshResetAuthorisationForbiddenError, SessionTooFreshError):
                LOGGER.info("Session %s is fresh (<24h); cannot reset authorizations yet", session_file.name)
                return "fresh_forbidden", "Account session is < 24h old; Telegram requires 24h before resetting other sessions"
            except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedError):
                return "unauthorized", "Session revoked or deactivated"
            except RPCError as exc:
                if "FRESH_RESET_AUTHORISATION_FORBIDDEN" in str(exc) or "SESSION_TOO_FRESH" in str(exc):
                    return "fresh_forbidden", "Account session is < 24h old; Telegram requires 24h before resetting other sessions"
                LOGGER.debug("Kill session RPC error (api_id=%s): %s", _mask_api_id(api_id), exc)
                last_err = f"RPCError: {exc}"
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Kill session error (api_id=%s): %s", _mask_api_id(api_id), exc)
                last_err = f"Error: {exc}"
                continue
            finally:
                with suppress(Exception):
                    await client.disconnect()

    return "error", last_err or "Connection failed across all credentials"


async def process_kill_sessions(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    proxy: tuple | None = None,
) -> KillSessionsResult:
    """Extract sessions from ZIP or single .session and terminate all other active sessions."""
    _ensure_opentele_patched()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_kill_zip_")
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_kill_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        killed = 0
        fresh_forbidden = 0
        failed = 0
        details: list[SessionKillDetail] = []

        # Each kill is a connect + ResetAuthorizationsRequest chain. Sequential
        # execution made large batches slow; a bounded semaphore (shared api
        # credentials / IP) keeps the flood risk in check while parallelizing.
        kill_semaphore = asyncio.Semaphore(min(_KILL_CONCURRENCY, total or 1))

        async def kill_one(index: int) -> tuple[str, str]:
            async with kill_semaphore:
                return await kill_single_session_others(
                    session_files[index], credentials, proxy=proxy
                )

        outcomes = await asyncio.gather(*(kill_one(i) for i in range(total)))
        for sess_file, (st, msg) in zip(session_files, outcomes):
            if st == "ok":
                killed += 1
            elif st == "fresh_forbidden":
                fresh_forbidden += 1
            else:
                failed += 1

            details.append(
                SessionKillDetail(
                    session_name=sess_file.name,
                    status=st,
                    message=msg,
                )
            )

        return KillSessionsResult(
            total=total,
            killed=killed,
            fresh_forbidden=fresh_forbidden,
            failed=failed,
            details=tuple(details),
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
