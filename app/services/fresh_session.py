"""fresh_session.py — Fresh Session migration service.

Logic:
1. Connect old session (proxy → local fallback) → get phone number.
2. Register OTP listener on old session for messages from Telegram (777000).
3. Send a code-request on a *new* Telethon client (random device, proxy → fallback).
4. Wait for the OTP to arrive on the old session via event.
5. Sign in the new client with that OTP (+ optional 2FA password).
6. [Optional] Change / remove 2FA password on the new session.
7. Kick ALL other authorizations (ResetAuthorizationsRequest) — invalidates old session.
8. Verify new session → store result.
9. Return FreshSessionResult with ZIP paths for new sessions and failed originals.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import shutil
import tempfile
import time
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import _is_valid_sqlite_session
from app.services.jobs import JobCancelled, JobProgress
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)

OTP_WAIT_SECONDS = 25   # how long to wait for OTP from Telegram (normally arrives in 2-5s)
TELETHON_TIMEOUT = 30   # connection / RPC timeout
PROXY_TIMEOUT = 10      # timeout used when trying proxy; falls back to direct

# Max concurrent migrations.
_FRESH_CONCURRENCY = 10

# ── Device / client fingerprints ──────────────────────────────────────────────
from app.services.device_params import get_stable_device_params



def _mask_phone(phone: str) -> str:
    """Mask the middle digits of a phone number for log safety (PII)."""
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if len(digits) < 6:
        return "***"
    return f"{digits[:3]}...{digits[-2:]}"


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionFreshDetail:
    session_name: str
    status: str   # 'ok' | 'otp_timeout' | 'unauthorized' | '2fa_required' | 'error'
    phone: str
    message: str
    kicked: bool = False   # True if ResetAuthorizations succeeded


@dataclass
class FreshSessionResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    kicked: int = 0        # number of sessions where kick succeeded
    details: list[SessionFreshDetail] = field(default_factory=list)
    new_sessions_zip: Path | None = None   # ZIP of newly created sessions
    failed_zip: Path | None = None         # ZIP of originals that failed


# ── Proxy-aware connect helper ────────────────────────────────────────────────

async def _connect_with_proxy_fallback(
    client: object,
    proxy: tuple | None,
    timeout: float = TELETHON_TIMEOUT,
) -> bool:
    """Connect *client* using *proxy*; fall back to direct on timeout/error.

    Returns True if connected via proxy, False if connected directly.
    The client object is mutated in place (its ``_proxy`` attribute is set).
    """
    from telethon import TelegramClient  # type: ignore[import-untyped]

    if proxy is not None:
        try:
            client._proxy = proxy  # type: ignore[attr-defined]
            await asyncio.wait_for(client.connect(), timeout=PROXY_TIMEOUT)  # type: ignore[attr-defined]
            return True
        except Exception:
            # Proxy failed — disconnect silently and retry without proxy
            with suppress(Exception):
                await client.disconnect()  # type: ignore[attr-defined]
            client._proxy = None  # type: ignore[attr-defined]

    # Direct (local) connection
    await asyncio.wait_for(client.connect(), timeout=timeout)  # type: ignore[attr-defined]
    return False


# ── Core single-session migration ─────────────────────────────────────────────

async def freshen_single_session(
    session_file: Path,
    credentials: list[tuple[int, str]],
    output_dir: Path,
    *,
    password_2fa: str | None = None,
    new_password: str | None = None,
    remove_password: bool = False,
    proxy: tuple | None = None,
) -> SessionFreshDetail:
    """Migrate one old .session to a brand-new .session file.

    Steps:
      1. Connect old session (proxy → local fallback) → read phone.
      2. Install OTP listener on old session.
      3. Connect new client (random device, proxy → local fallback).
      4. Send code-request via new_client.
      5. Await OTP from event queue.
      6. Sign-in new_client with OTP (+ optional 2FA password).
      7. [Optional] Change / remove 2FA on new session.
      8. Kick ALL other authorizations (invalidates old session + other devices).
      9. Verify & disconnect both.
    """
    session_name = session_file.name

    if not _is_valid_sqlite_session(session_file):
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone="",
            message="Invalid SQLite session (missing auth_key)",
        )

    try:
        from telethon import TelegramClient, events, functions  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyDuplicatedError,
            AuthKeyUnregisteredError,
            PasswordHashInvalidError,
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            PhoneNumberBannedError,
            SessionExpiredError,
            SessionPasswordNeededError,
            SessionRevokedError,
            UserDeactivatedBanError,
            UserDeactivatedError,
        )

    except ModuleNotFoundError:
        return SessionFreshDetail(
            session_name=session_name,
            status="error",
            phone="",
            message="Telethon library missing",
        )

    phone = ""

    for api_id, api_hash in credentials:
        old_client = None
        new_client = None

        with tempfile.TemporaryDirectory(prefix="ftgc_fresh_") as tmp:
            tmp_path = Path(tmp)
            old_sess_path = tmp_path / "old_account.session"
            shutil.copy2(session_file, old_sess_path)
            old_stem = str(old_sess_path.with_suffix(""))

            try:
                # ── Step 1: connect old session (proxy → local fallback) ───
                old_device_kwargs = get_stable_device_params(session_file)
                old_client = TelegramClient(
                    old_stem,
                    api_id,
                    api_hash,
                    receive_updates=True,
                    **old_device_kwargs,
                )
                await _connect_with_proxy_fallback(old_client, proxy)

                if not await old_client.is_user_authorized():
                    LOGGER.info(
                        "Fresh session: session unauthorized/expired (%s)",
                        session_name,
                    )
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="unauthorized",
                        phone="",
                        message="Session unauthorized or expired",
                    )

                me = await asyncio.wait_for(old_client.get_me(), timeout=30)
                phone = me.phone or str(me.id)
                if not phone.startswith("+"):
                    phone = "+" + phone

                LOGGER.info(
                    "Fresh session: old session authorised (%s)",
                    session_name,
                )

                # ── Step 3: Create new client with stable device params ────
                new_sess_path = output_dir / f"{phone}.session"
                new_stem = str(new_sess_path.with_suffix(""))
                new_device_kwargs = get_stable_device_params(new_sess_path)

                new_client = TelegramClient(
                    new_stem,
                    api_id,
                    api_hash,
                    receive_updates=False,
                    **new_device_kwargs,
                )
                await _connect_with_proxy_fallback(new_client, proxy)

                # ── Step 4: Send code request ─────────────────────────────
                code_sent_at_ts = time.time()
                sent = await asyncio.wait_for(
                    new_client.send_code_request(phone), timeout=60
                )
                phone_code_hash = sent.phone_code_hash
                LOGGER.info("Code request sent for %s", session_name)

                # ── Step 5: Poll 777000 for OTP code via direct RPC ───────
                otp_code: str | None = None
                poll_deadline = time.time() + OTP_WAIT_SECONDS
                while time.time() < poll_deadline:
                    await asyncio.sleep(1.0)
                    try:
                        msgs = await old_client.get_messages(777000, limit=3)
                        for m in msgs:
                            if m and m.date and m.date.timestamp() >= (code_sent_at_ts - 5):
                                codes = re.findall(r"\b\d{5,6}\b", m.message or "")
                                if codes:
                                    otp_code = codes[0]
                                    LOGGER.info(
                                        "OTP code %s retrieved for %s",
                                        otp_code,
                                        session_name,
                                    )
                                    break
                        if otp_code:
                            break
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning(
                            "OTP fetch polling error for %s: %s", session_name, exc
                        )

                if not otp_code:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="otp_timeout",
                        phone=phone,
                        message=f"OTP not received within {OTP_WAIT_SECONDS}s",
                    )

                # ── Step 6: Sign in new client ────────────────────────────
                try:
                    await asyncio.wait_for(
                        new_client.sign_in(
                            phone, otp_code, phone_code_hash=phone_code_hash
                        ),
                        timeout=60,
                    )
                except SessionPasswordNeededError:
                    if not password_2fa:
                        return SessionFreshDetail(
                            session_name=session_name,
                            status="2fa_required",
                            phone=phone,
                            message="2FA password required but not provided",
                        )
                    try:
                        await asyncio.wait_for(
                            new_client.sign_in(password=password_2fa), timeout=60
                        )
                    except PasswordHashInvalidError:
                        return SessionFreshDetail(
                            session_name=session_name,
                            status="2fa_required",
                            phone=phone,
                            message="Invalid 2FA password",
                        )
                except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
                    return SessionFreshDetail(
                        session_name=session_name,
                        status="error",
                        phone=phone,
                        message=f"OTP error: {exc}",
                    )

                # ── Step 7: Verify new session ────────────────────────────
                # ── Step 8: Update / Remove 2FA on new session ────────────
                if new_password is not None or remove_password:
                    try:
                        cur_pwd = password_2fa if password_2fa else ""
                        if remove_password:
                            await new_client.edit_2fa(
                                current_password=cur_pwd, new_password=None
                            )
                        elif new_password:
                            await new_client.edit_2fa(
                                current_password=cur_pwd, new_password=new_password
                            )
                        LOGGER.info(
                            "Fresh session: 2FA updated for %s (remove=%s)",
                            session_name,
                            remove_password,
                        )
                    except Exception as exc:  # noqa: BLE001
                        # Non-fatal: session was created, just log the 2FA failure
                        LOGGER.warning(
                            "Fresh session: 2FA edit failed for %s: %s",
                            session_name,
                            exc,
                        )

                # ── Step 9: Kick ALL other authorizations ─────────────────
                kicked = False
                try:
                    await asyncio.wait_for(
                        new_client(functions.auth.ResetAuthorizationsRequest()),
                        timeout=30,
                    )
                    kicked = True
                    LOGGER.info(
                        "Fresh session: kicked all other sessions for %s",
                        session_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    # Non-fatal: session was still successfully created
                    LOGGER.warning(
                        "Fresh session: kick failed for %s: %s",
                        session_name,
                        exc,
                    )

                LOGGER.info(
                    "Fresh session success: %s (%s) → %s",
                    session_name, _mask_phone(phone), new_sess_path.name,
                )
                return SessionFreshDetail(
                    session_name=session_name,
                    status="ok",
                    phone=phone,
                    message=f"New session created: {new_sess_path.name}",
                    kicked=kicked,
                )

            except (
                AuthKeyDuplicatedError,
                AuthKeyUnregisteredError,
                SessionExpiredError,
                SessionRevokedError,
                UserDeactivatedBanError,
                UserDeactivatedError,
                PhoneNumberBannedError,
            ):
                return SessionFreshDetail(
                    session_name=session_name,
                    status="unauthorized",
                    phone=phone,
                    message="Session revoked or account deactivated",
                )

            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Fresh session error (api_id=%d) %s: %s",
                    api_id, session_name, exc,
                    exc_info=True,
                )
                continue
            finally:
                if old_client is not None:
                    with suppress(Exception):
                        await old_client.disconnect()
                if new_client is not None:
                    with suppress(Exception):
                        await new_client.disconnect()

    return SessionFreshDetail(
        session_name=session_name,
        status="unauthorized",
        phone=phone or "",
        message="Session unauthorized or expired across all credentials",
    )


# ── Batch orchestrator ────────────────────────────────────────────────────────

async def process_fresh_sessions(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    password_2fa: str | None = None,
    new_password: str | None = None,
    remove_password: bool = False,
    proxy: tuple | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> FreshSessionResult:
    """Extract sessions from ZIP or single .session and re-authenticate each one.

    Args:
        input_path:      Path to the uploaded file.
        credentials:     List of (api_id, api_hash) pairs to try.
        original_name:   Original filename (used to determine ZIP vs. .session).
        password_2fa:    Existing 2FA password (used for sign-in).
        new_password:    New 2FA password to set after migration (None = keep old).
        remove_password: If True, 2FA is disabled on the new session.
        proxy:           Telethon proxy tuple; falls back to direct on timeout.
        progress:        JobProgress instance for live progress reporting.
        cancel_event:    asyncio.Event; set to cancel the batch.

    Returns:
        FreshSessionResult with ZIPs and per-session details.
    """
    _ensure_opentele_patched()

    input_tmp: tempfile.TemporaryDirectory[str] | None = None
    new_dir: tempfile.TemporaryDirectory[str] | None = None
    failed_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    result = FreshSessionResult()

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()

        # ── Unpack input ──────────────────────────────────────────────────
        if suffix == ".zip":
            input_tmp = tempfile.TemporaryDirectory(prefix="ftgc_fresh_zip_")
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(input_tmp.name)
            )
        elif suffix == ".session":
            if original_name:
                input_tmp = tempfile.TemporaryDirectory(prefix="ftgc_fresh_one_")
                copied = Path(input_tmp.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        result.total = len(session_files)
        if result.total == 0:
            return result

        # ── Output directories ────────────────────────────────────────────
        new_dir = tempfile.TemporaryDirectory(prefix="ftgc_fresh_new_")
        failed_dir = tempfile.TemporaryDirectory(prefix="ftgc_fresh_fail_")

        new_dir_path = Path(new_dir.name)
        failed_dir_path = Path(failed_dir.name)

        if progress is not None:
            progress.total = len(session_files)

        fresh_semaphore = asyncio.Semaphore(
            min(_FRESH_CONCURRENCY, len(session_files) or 1)
        )

        async def freshen_one(index: int) -> SessionFreshDetail:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            async with fresh_semaphore:
                return await freshen_single_session(
                    session_files[index],
                    credentials,
                    new_dir_path,
                    password_2fa=password_2fa,
                    new_password=new_password,
                    remove_password=remove_password,
                    proxy=proxy,
                )

        async def tracked_freshen(index: int) -> SessionFreshDetail:
            detail = await freshen_one(index)
            if progress is not None:
                progress.done += 1
            return detail

        details = await asyncio.gather(
            *(tracked_freshen(index) for index in range(len(session_files)))
        )

        for index, detail in enumerate(details):
            result.details.append(detail)

            if detail.status == "ok":
                result.succeeded += 1
                if detail.kicked:
                    result.kicked += 1
            else:
                result.failed += 1
                # Copy original to failed dir for user to download
                dest = failed_dir_path / session_files[index].name
                with suppress(Exception):
                    shutil.copy2(session_files[index], dest)

        # ── Pack new sessions ZIP ─────────────────────────────────────────
        new_sess_files = list(new_dir_path.glob("*.session"))
        if new_sess_files:
            new_zip_path = (
                Path(tempfile.gettempdir()) / f"ftgc_fresh_new_{uuid4().hex}.zip"
            )
            with zipfile.ZipFile(new_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in new_sess_files:
                    zf.write(f, f.name)
            result.new_sessions_zip = new_zip_path

        # ── Pack failed sessions ZIP ──────────────────────────────────────
        failed_files = list(failed_dir_path.glob("*.session"))
        if failed_files:
            fail_zip_path = (
                Path(tempfile.gettempdir()) / f"ftgc_fresh_fail_{uuid4().hex}.zip"
            )
            with zipfile.ZipFile(fail_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in failed_files:
                    zf.write(f, f.name)
            result.failed_zip = fail_zip_path

        return result

    finally:
        for td in (input_tmp, new_dir, failed_dir):
            if td is not None:
                with suppress(Exception):
                    td.cleanup()
